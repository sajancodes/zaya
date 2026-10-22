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


def get_db_path() -> Path:
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


def init_db(db_path: Optional[Path] = None) -> None:
    """Initialize SQLite tables and default release metadata."""
    conn = get_connection(db_path)
    try:
        with conn:
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
    now = int(time.time())
    conn = get_connection()
    try:
        with conn:
            cursor = conn.execute(
                "SELECT installation_id FROM installations WHERE installation_id = ?;",
                (installation_id,)
            )
            existing = cursor.fetchone()
            if existing:
                conn.execute("""
                    UPDATE installations
                    SET current_version = ?, last_seen = ?
                    WHERE installation_id = ?;
                """, (version, now, installation_id))
                return False
            else:
                conn.execute("""
                    INSERT INTO installations (installation_id, platform, installed_version, current_version, first_seen, last_seen)
                    VALUES (?, ?, ?, ?, ?, ?);
                """, (installation_id, platform.lower(), version, version, now, now))
                return True
    finally:
        conn.close()


def record_heartbeat(installation_id: str, platform: str, version: str) -> bool:
    """Update last_seen timestamp for an active installation."""
    now = int(time.time())
    conn = get_connection()
    try:
        with conn:
            cursor = conn.execute(
                "SELECT installation_id FROM installations WHERE installation_id = ?;",
                (installation_id,)
            )
            if cursor.fetchone():
                conn.execute("""
                    UPDATE installations
                    SET current_version = ?, last_seen = ?, platform = ?
                    WHERE installation_id = ?;
                """, (version, now, platform.lower(), installation_id))
                return True
            else:
                # If installation record missing, create it
                conn.execute("""
                    INSERT INTO installations (installation_id, platform, installed_version, current_version, first_seen, last_seen)
                    VALUES (?, ?, ?, ?, ?, ?);
                """, (installation_id, platform.lower(), version, version, now, now))
                return True
    finally:
        conn.close()


def record_download(platform: str, version: str, client_ip: Optional[str] = None) -> None:
    """Record a platform download event with an anonymized hashed IP."""
    now = int(time.time())
    ip_hash = None
    if client_ip:
        ip_hash = hashlib.sha256(f"salt_{client_ip}".encode("utf-8")).hexdigest()[:16]

    conn = get_connection()
    try:
        with conn:
            conn.execute("""
                INSERT INTO downloads (platform, version, ip_hash, created_at)
                VALUES (?, ?, ?, ?);
            """, (platform.lower(), version, ip_hash, now))
    finally:
        conn.close()


def get_latest_release(platform: str = "windows") -> Optional[Dict[str, Any]]:
    """Retrieve the latest release metadata for a given platform."""
    conn = get_connection()
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
) -> None:
    """Insert or update a release manifest row."""
    now = published_at or int(time.time())
    conn = get_connection()
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


def sync_releases_from_github() -> None:
    """Synchronize official release metadata from published GitHub release manifests."""
    import json
    import urllib.request

    # Windows manifest
    win_url = "https://github.com/sajancodes/zaya-companion-releases/releases/latest/download/desktop-update.json"
    try:
        req = urllib.request.Request(win_url, headers={"User-Agent": "Zaya-Web-Sync"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.load(resp)
            if isinstance(data, dict) and "version" in data and "sha256" in data:
                upsert_release(
                    version=str(data["version"]),
                    platform="windows",
                    filename=str(data.get("filename", "ZayaSetup.exe")),
                    url=str(data.get("url", f"https://github.com/sajancodes/zaya-companion-releases/releases/latest/download/{data.get('filename', 'ZayaSetup.exe')}")),
                    sha256=str(data["sha256"]),
                    size=int(data.get("size", 0)),
                    release_notes=f"Zaya v{data['version']} Windows Production Release",
                )
    except Exception as e:
        logger.debug(f"Could not sync Windows releases from GitHub: {e}")

    # Android manifest
    droid_url = "https://github.com/sajancodes/zaya-companion-releases/releases/latest/download/update.json"
    try:
        req = urllib.request.Request(droid_url, headers={"User-Agent": "Zaya-Web-Sync"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.load(resp)
            if isinstance(data, dict) and "version_name" in data and "sha256" in data:
                upsert_release(
                    version=str(data["version_name"]),
                    platform="android",
                    filename="Zaya-Companion.apk",
                    url=str(data.get("download_url", "https://github.com/sajancodes/zaya-companion-releases/releases/latest/download/Zaya-Companion.apk")),
                    sha256=str(data["sha256"]),
                    size=int(data.get("size_bytes", 0)),
                    release_notes=str(data.get("release_notes", f"Zaya Companion v{data['version_name']}")),
                )
    except Exception as e:
        logger.debug(f"Could not sync Android releases from GitHub: {e}")


def get_all_releases() -> List[Dict[str, Any]]:
    """Retrieve all release manifests ordered newest first."""
    conn = get_connection()
    try:
        cursor = conn.execute("""
            SELECT * FROM releases
            ORDER BY published_at DESC, version DESC;
        """)
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def get_analytics_metrics() -> Dict[str, Any]:
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
            "daily_installs": daily_installs,
            "daily_downloads": daily_downloads,
            "updated_at": now,
        }
    finally:
        conn.close()
