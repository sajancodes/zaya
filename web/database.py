"""Database layer for Zaya public website and telemetry backend.
Created and developed by Sajan Rai.

Uses SQLite with WAL mode for high concurrency and zero external dependencies.
Tracks:
- Anonymous unique installations (UUIDv4)
- Daily active heartbeats
- Download events
- Release manifests
- Admin analytics aggregations
"""
from __future__ import annotations

import hashlib
import logging
import os
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

DEFAULT_DB_DIR = Path(__file__).resolve().parent / "data"
DEFAULT_DB_PATH = DEFAULT_DB_DIR / "zaya_analytics.db"


def firebase_enabled():
    return os.environ.get('ZAYA_DATABASE_BACKEND', 'firebase' if os.environ.get('VERCEL') else 'sqlite') == 'firebase'


def get_db_path() -> Path:
    if os.environ.get('VERCEL'):
        raise RuntimeError('SQLite is disabled on Vercel. Configure the Firebase backend.')
    override = os.environ.get("DATABASE_URL")
    if override and override.startswith("sqlite:///"):
        return Path(override.replace("sqlite:///", "")).resolve()
    path = Path(os.environ.get("ZAYA_DB_PATH", DEFAULT_DB_PATH)).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def get_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    target = db_path or get_db_path()
    conn = sqlite3.connect(str(target), timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def _migrate_releases_table_if_needed(conn: sqlite3.Connection) -> None:
    """Migrate legacy releases table (version as single PK) to composite (version, platform) schema."""
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='releases';")
    if not cursor.fetchone():
        return

    columns = [row[1] for row in conn.execute("PRAGMA table_info(releases);").fetchall()]
    if "id" not in columns:
        logger.info("Migrating legacy releases table to composite (version, platform) schema...")
        conn.execute("""
            CREATE TABLE releases_v2 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                version TEXT NOT NULL,
                platform TEXT NOT NULL,
                filename TEXT NOT NULL,
                url TEXT NOT NULL,
                sha256 TEXT NOT NULL,
                size INTEGER NOT NULL,
                release_notes TEXT,
                published_at INTEGER NOT NULL,
                UNIQUE(version, platform)
            );
        """)
        conn.execute("""
            INSERT OR IGNORE INTO releases_v2 (version, platform, filename, url, sha256, size, release_notes, published_at)
            SELECT version, platform, filename, url, sha256, size, release_notes, published_at
            FROM releases;
        """)
        conn.execute("DROP TABLE releases;")
        conn.execute("ALTER TABLE releases_v2 RENAME TO releases;")
        logger.info("Releases table migration complete.")


def init_db(db_path: Optional[Path] = None) -> None:
    """Initialize SQLite tables and default release metadata."""
    if firebase_enabled() and db_path is None:
        from web.firebase_store import client
        client()
        return
    conn = get_connection(db_path)
    try:
        with conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS daily_activity (
                installation_id TEXT NOT NULL, day TEXT NOT NULL,
                PRIMARY KEY (installation_id, day));""")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS installations (
                    installation_id TEXT PRIMARY KEY,
                    platform TEXT NOT NULL,
                    installed_version TEXT NOT NULL,
                    current_version TEXT NOT NULL,
                    first_seen INTEGER NOT NULL,
                    last_seen INTEGER NOT NULL
                );
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_installations_last_seen
                ON installations(last_seen);
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_installations_platform
                ON installations(platform);
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS downloads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    platform TEXT NOT NULL,
                    version TEXT NOT NULL,
                    ip_hash TEXT,
                    created_at INTEGER NOT NULL
                );
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_downloads_created_at
                ON downloads(created_at);
            """)

            _migrate_releases_table_if_needed(conn)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS releases (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    version TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    url TEXT NOT NULL,
                    sha256 TEXT NOT NULL,
                    size INTEGER NOT NULL,
                    release_notes TEXT,
                    published_at INTEGER NOT NULL,
                    UNIQUE(version, platform)
                );
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS admin_sessions (
                    token TEXT PRIMARY KEY,
                    username TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    expires_at INTEGER NOT NULL
                );
            """)
    finally:
        conn.close()


def record_install(installation_id: str, platform: str, version: str) -> bool:
    """Record an anonymous installation.

    Returns True if this is a newly recorded unique installation,
    or False if it was already known (updates don't inflate unique user counts).
    """
    if firebase_enabled():
        from web import firebase_store
        return firebase_store.record_install(installation_id, platform, version)
    now = int(time.time())
    from datetime import datetime, timezone
    day = datetime.fromtimestamp(now, timezone.utc).date().isoformat()
    conn = get_connection()
    try:
        with conn:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute("SELECT installation_id FROM installations WHERE installation_id = ?", (installation_id,)).fetchone()
            conn.execute("""INSERT INTO installations
                (installation_id, platform, installed_version, current_version, first_seen, last_seen)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(installation_id) DO UPDATE SET
                platform=excluded.platform, current_version=excluded.current_version, last_seen=excluded.last_seen""",
                (installation_id, platform.lower(), version, version, now, now))
            conn.execute("INSERT OR IGNORE INTO daily_activity VALUES (?, ?)", (installation_id, day))
            conn.execute("DELETE FROM daily_activity WHERE day < date(?, 'unixepoch', '-90 days')", (now,))
            return existing is None
    finally:
        conn.close()


def record_heartbeat(installation_id: str, platform: str, version: str) -> bool:
    return record_install(installation_id, platform, version)


def record_download(platform: str, version: str, client_ip: Optional[str] = None) -> None:
    if firebase_enabled():
        from web import firebase_store
        return firebase_store.record_download(platform, version)
    """Record a platform download event with an anonymized hashed IP."""
    now = int(time.time())
    ip_hash = None  # No raw or deterministically hashed IP in product analytics.

    conn = get_connection()
    try:
        with conn:
            conn.execute("""
                INSERT INTO downloads (platform, version, ip_hash, created_at)
                VALUES (?, ?, ?, ?);
            """, (platform.lower(), version, ip_hash, now))
    finally:
        conn.close()


def get_latest_release(platform: str = "windows", db_path: Optional[Path] = None, channel: str = 'stable') -> Optional[Dict[str, Any]]:
    """Retrieve the latest release metadata for a given platform."""
    if firebase_enabled() and db_path is None:
        from web import firebase_store
        return firebase_store.get_latest_release(platform, channel=channel)
    if channel != 'stable':
        return None
    conn = get_connection(db_path)
    try:
        cursor = conn.execute("""
            SELECT * FROM releases
            WHERE platform = ?
            ORDER BY published_at DESC, version DESC
            LIMIT 1;
        """, (platform.lower(),))
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def upsert_release(
    version: str,
    platform: str,
    filename: str,
    url: str,
    sha256: str,
    size: int,
    release_notes: str = "",
    published_at: Optional[int] = None,
    db_path: Optional[Path] = None,
    channel: str = 'stable',
    build: int = 0,
) -> None:
    """Insert or update a release manifest row."""
    if firebase_enabled() and db_path is None:
        from web import firebase_store
        return firebase_store.upsert_release(version, platform, filename, url, sha256, size, release_notes, published_at, channel=channel, build=build)
    now = published_at or int(time.time())
    conn = get_connection(db_path)
    try:
        with conn:
            conn.execute("""
                INSERT INTO releases (version, platform, filename, url, sha256, size, release_notes, published_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(version, platform) DO UPDATE SET
                    filename = excluded.filename,
                    url = excluded.url,
                    sha256 = excluded.sha256,
                    size = excluded.size,
                    release_notes = excluded.release_notes,
                    published_at = excluded.published_at;
            """, (version, platform.lower(), filename, url, sha256, int(size), release_notes, now))
    finally:
        conn.close()


def sync_releases_from_github(strict=False, tag=None):
    """Sync bounded official stable/beta platform manifests, preserving pulled releases."""
    import json
    import urllib.request
    from datetime import datetime
    from web.release_validation import validate_release
    def read(url):
        request = urllib.request.Request(url, headers={'User-Agent': 'Zaya-Release-Sync'})
        with urllib.request.urlopen(request, timeout=10) as response:
            raw = response.read(1_000_001)
            if len(raw) > 1_000_000:
                raise ValueError('Release metadata is too large.')
            return json.loads(raw)
    try:
        base = 'https://api.github.com/repos/sajancodes/zaya-companion-releases/releases'
        if tag is not None:
            from web.release_identity import TAG
            if not isinstance(tag, str) or not TAG.fullmatch(tag):
                raise ValueError('Invalid release tag')
        rows = [read(base + '/tags/' + tag)] if tag else read(base + '?per_page=15')
        seen = set()
        processed = []
        for release in rows:
            if release.get('draft'):
                continue
            channel = 'beta' if release.get('prerelease') else 'stable'
            assets = {asset['name']: asset for asset in release.get('assets', [])}
            for platform, manifest_name in [('windows', 'desktop-update.json'), ('android', 'update.json'), ('linux', 'linux-update.json')]:
                if (platform, channel) in seen or manifest_name not in assets:
                    continue
                data = read(assets[manifest_name]['browser_download_url'])
                if platform == 'linux' and data.get('public_release_verified') is not True:
                    raise ValueError('Unverified Linux candidates cannot enter the public catalog')
                version = data.get('version_name') if platform == 'android' else data.get('version')
                filename = 'Zaya-Companion.apk' if platform == 'android' else data.get('filename', 'ZayaSetup.exe' if platform == 'windows' else 'Zaya.deb')
                artifact = assets.get(filename)
                if not artifact:
                    continue
                item = {'version': version, 'platform': platform, 'filename': filename,
                        'url': artifact['browser_download_url'], 'sha256': data['sha256'],
                        'size': int(data['size']), 'channel': channel}
                validate_release(item)
                if artifact['size'] != item['size'] or artifact.get('digest') != 'sha256:' + item['sha256']:
                    raise ValueError('Release manifest differs from published asset integrity metadata.')
                upsert_release(**item, build=int(data.get('build', data.get('version_code', 0))),
                               published_at=int(datetime.fromisoformat(release['published_at'].replace('Z', '+00:00')).timestamp()),
                               release_notes=(release.get('body') or '')[:8000])
                seen.add((platform, channel))
                processed.append({'platform':platform, 'version':version, 'channel':channel})
        if tag and not processed:
            raise ValueError('No verified platform manifests found for this release')
        return {'status':'ok', 'releases':processed}
    except Exception as error:
        logger.warning('Release sync unavailable (%s); retaining verified catalog.', type(error).__name__)
        if strict:
            raise RuntimeError('Verified release synchronization failed') from None


def get_all_releases(db_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    if firebase_enabled() and db_path is None:
        from web import firebase_store
        return firebase_store.get_all_releases()
    """Retrieve all release manifests ordered newest first."""
    conn = get_connection(db_path)
    try:
        cursor = conn.execute("""
            SELECT * FROM releases
            ORDER BY published_at DESC, version DESC;
        """)
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def get_analytics_metrics() -> Dict[str, Any]:
    if firebase_enabled():
        from web import firebase_store
        return firebase_store.get_analytics_metrics()
    """Calculate aggregated metrics for the owner admin dashboard."""
    now = int(time.time())
    t_24h = now - 86400
    t_7d = now - (7 * 86400)
    t_30d = now - (30 * 86400)

    conn = get_connection()
    try:
        # Download metrics
        c = conn.cursor()
        total_downloads = c.execute("SELECT COUNT(*) FROM downloads;").fetchone()[0]
        windows_downloads = c.execute("SELECT COUNT(*) FROM downloads WHERE platform = 'windows';").fetchone()[0]
        android_downloads = c.execute("SELECT COUNT(*) FROM downloads WHERE platform = 'android';").fetchone()[0]

        # Installation metrics
        total_installs = c.execute("SELECT COUNT(*) FROM installations;").fetchone()[0]
        windows_installs = c.execute("SELECT COUNT(*) FROM installations WHERE platform = 'windows';").fetchone()[0]
        android_installs = c.execute("SELECT COUNT(*) FROM installations WHERE platform = 'android';").fetchone()[0]

        # Active users
        active_24h = c.execute("SELECT COUNT(*) FROM installations WHERE last_seen >= ?;", (t_24h,)).fetchone()[0]
        active_7d = c.execute("SELECT COUNT(*) FROM installations WHERE last_seen >= ?;", (t_7d,)).fetchone()[0]
        active_30d = c.execute("SELECT COUNT(*) FROM installations WHERE last_seen >= ?;", (t_30d,)).fetchone()[0]

        # Version distribution
        version_rows = c.execute("""
            SELECT current_version, COUNT(*) AS count
            FROM installations
            GROUP BY current_version
            ORDER BY count DESC;
        """).fetchall()
        version_distribution = {row["current_version"]: row["count"] for row in version_rows}

        # Daily new installs (last 14 days)
        timeline_rows = c.execute("""
            SELECT strftime('%Y-%m-%d', datetime(first_seen, 'unixepoch')) AS day, COUNT(*) AS count
            FROM installations
            WHERE first_seen >= ?
            GROUP BY day
            ORDER BY day ASC;
        """, (now - 14 * 86400,)).fetchall()
        daily_installs = [{"day": r["day"], "count": r["count"]} for r in timeline_rows]

        # Daily downloads (last 14 days)
        dl_timeline_rows = c.execute("""
            SELECT strftime('%Y-%m-%d', datetime(created_at, 'unixepoch')) AS day, COUNT(*) AS count
            FROM downloads
            WHERE created_at >= ?
            GROUP BY day
            ORDER BY day ASC;
        """, (now - 14 * 86400,)).fetchall()
        daily_downloads = [{"day": r["day"], "count": r["count"]} for r in dl_timeline_rows]

        return {
            "downloads": {
                "total": total_downloads,
                "windows": windows_downloads,
                "android": android_downloads,
            },
            "installations": {
                "total": total_installs,
                "windows": windows_installs,
                "android": android_installs,
            },
            "active": {
                "last_24h": active_24h,
                "last_7d": active_7d,
                "last_30d": active_30d,
            },
            "version_distribution": version_distribution,
            "daily_actives": [dict(row) for row in c.execute("SELECT day, COUNT(*) AS count FROM daily_activity GROUP BY day ORDER BY day DESC LIMIT 14").fetchall()][::-1],
            "daily_installs": daily_installs,
            "daily_downloads": daily_downloads,
            "updated_at": now,
        }
    finally:
        conn.close()
