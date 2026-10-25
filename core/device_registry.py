"""Durable pairing records for remote devices (the Android companion, browsers).

Device sessions used to live in a Python dict, so every Zaya restart silently
unpaired every phone and forced a fresh QR scan. Records now live in the existing
local SQLite store (`memory/zaya_runtime.db`, the same file the task runtime and
the WhatsApp store use), which means a paired phone reconnects by itself after a
restart, a crash or a laptop reboot.

What is stored, and what is not:

    device_id          opaque random identifier handed to the phone
    device_name        whatever the phone called itself ("Pixel 8 · Zaya")
    credential_hash    pbkdf2-sha256 of the device secret. The secret itself is
                       returned exactly once, at pairing time, and never stored.
    session_key        transport key for the *browser* dashboard only. Android
                       never uses it. It is recoverable by design, because the
                       dashboard client has to re-derive its AES layer from it.
    created_at / last_seen / revoked / app_version / platform / last_ip

Revocation is a flag, not a delete: a revoked phone must keep being rejected even
if it presents a credential that was valid yesterday.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
import sqlite3
import threading
import time
from pathlib import Path
from core.runtime_paths import mutable_path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATH = mutable_path(ROOT / 'memory' / 'zaya_runtime.db')

_ITERATIONS = 120_000
_LOCKOUT_THRESHOLD = 5
_LOCKOUT_SECONDS = 300.0
_FAILURE_WINDOW = 300.0

_SCHEMA = """
CREATE TABLE IF NOT EXISTS paired_devices (
    device_id       TEXT PRIMARY KEY,
    device_name     TEXT NOT NULL,
    credential_hash TEXT NOT NULL,
    session_key     TEXT NOT NULL DEFAULT '',
    created_at      REAL NOT NULL,
    last_seen       REAL NOT NULL,
    revoked         INTEGER NOT NULL DEFAULT 0,
    app_version     TEXT NOT NULL DEFAULT '',
    platform        TEXT NOT NULL DEFAULT '',
    last_ip         TEXT NOT NULL DEFAULT '',
    fail_count      INTEGER NOT NULL DEFAULT 0,
    fail_at         REAL NOT NULL DEFAULT 0
)
"""


def _hash_secret(secret: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac('sha256', secret.encode('utf-8'), salt, _ITERATIONS)
    return f'pbkdf2_sha256${_ITERATIONS}${salt.hex()}${digest.hex()}'


def _verify_secret(secret: str, stored: str) -> bool:
    try:
        scheme, iterations, salt_hex, digest_hex = str(stored).split('$')
        if scheme != 'pbkdf2_sha256':
            return False
        digest = hashlib.pbkdf2_hmac('sha256', secret.encode('utf-8'),
                                     bytes.fromhex(salt_hex), int(iterations))
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (TypeError, ValueError):
        return False


def _public(record: sqlite3.Row | dict) -> dict:
    """A device record as it may leave the laptop: never the credential or key."""
    row = dict(record)
    return {
        'device_id': row.get('device_id', ''),
        'device_name': row.get('device_name', ''),
        'created_at': float(row.get('created_at') or 0.0),
        'last_seen': float(row.get('last_seen') or 0.0),
        'revoked': bool(row.get('revoked', 0)),
        'app_version': row.get('app_version', ''),
        'platform': row.get('platform', ''),
        'last_ip': row.get('last_ip', ''),
    }


class DeviceRegistry:
    def __init__(self, path: Path | str = DEFAULT_PATH) -> None:
        self._lock = threading.RLock()
        self._path = str(path)
        if self._path != ':memory:':
            Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self._path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute(_SCHEMA)
        self._migrate()
        self.db.commit()

    def _migrate(self) -> None:
        """Add columns that older databases lack. Ignores duplicates."""
        existing = {row['name'] for row in self.db.execute('PRAGMA table_info(paired_devices)')}
        for column, ddl in (('last_ip', "TEXT NOT NULL DEFAULT ''"),
                            ('fail_count', 'INTEGER NOT NULL DEFAULT 0'),
                            ('fail_at', 'REAL NOT NULL DEFAULT 0')):
            if column not in existing:
                self.db.execute(f'ALTER TABLE paired_devices ADD COLUMN {column} {ddl}')

    # ── pairing ───────────────────────────────────────────────────────────────

    def pair(self, name: str, *, app_version: str = '', platform: str = '',
             session_key: str = '', ip: str = '', secret: str | None = None) -> tuple[dict, str]:
        """Create a new paired device. Returns (public_record, secret).

        The secret is the only copy that will ever exist; the caller hands it to
        the device and stores only its hash. A caller that already owns a
        credential (the browser flow mints its own device token) may supply it.
        """
        now = time.time()
        device_id = secrets.token_urlsafe(16)
        secret = secret or secrets.token_urlsafe(32)
        label = (name or '').strip()[:80] or 'Remote device'
        with self._lock, self.db:
            self.db.execute(
                'INSERT INTO paired_devices (device_id, device_name, credential_hash, session_key,'
                ' created_at, last_seen, revoked, app_version, platform, last_ip, fail_count, fail_at)'
                ' VALUES (?,?,?,?,?,?,0,?,?,?,0,0)',
                (device_id, label, _hash_secret(secret), str(session_key or ''),
                 now, now, (app_version or '')[:40], (platform or '')[:40], (ip or '')[:64]),
            )
            row = self.db.execute('SELECT * FROM paired_devices WHERE device_id=?', (device_id,)).fetchone()
        return _public(row), secret

    # ── authentication ────────────────────────────────────────────────────────

    def locked(self, device_id: str) -> float:
        """Seconds remaining before this device may try again (0.0 when free)."""
        row = self._row(device_id)
        if not row:
            return 0.0
        if int(row['fail_count'] or 0) < _LOCKOUT_THRESHOLD:
            return 0.0
        remaining = float(row['fail_at'] or 0.0) + _LOCKOUT_SECONDS - time.time()
        return remaining if remaining > 0 else 0.0

    def authenticate(self, device_id: str, secret: str) -> dict | None:
        """Return the public device record on success, else None.

        A revoked device, a wrong secret and an unknown device are deliberately
        indistinguishable to the caller. Repeated failures lock the device out so
        a paired device ID is not a free oracle for brute-forcing the secret.
        """
        if not device_id or not secret:
            return None
        if self.locked(device_id) > 0:
            return None
        row = self._row(device_id)
        if not row:
            return None
        if bool(row['revoked']):
            return None
        if not _verify_secret(secret, row['credential_hash']):
            self._register_failure(device_id, row)
            return None
        self._clear_failures(device_id)
        return _public(row)

    def session_key_for(self, device_id: str, secret: str) -> str | None:
        """Browser transport key, released only to a device that re-authenticated."""
        if not self.authenticate(device_id, secret):
            return None
        row = self._row(device_id)
        return str(row['session_key'] or '') if row else None

    def _register_failure(self, device_id: str, row: sqlite3.Row) -> None:
        now = time.time()
        count = int(row['fail_count'] or 0)
        if now - float(row['fail_at'] or 0.0) > _FAILURE_WINDOW:
            count = 0
        count += 1
        with self._lock, self.db:
            self.db.execute('UPDATE paired_devices SET fail_count=?, fail_at=? WHERE device_id=?',
                            (count, now, device_id))

    def _clear_failures(self, device_id: str) -> None:
        with self._lock, self.db:
            self.db.execute('UPDATE paired_devices SET fail_count=0, fail_at=0 WHERE device_id=?',
                            (device_id,))

    # ── lifecycle ─────────────────────────────────────────────────────────────

    def touch(self, device_id: str, *, app_version: str | None = None,
              platform: str | None = None, ip: str | None = None) -> None:
        sets, values = ['last_seen=?'], [time.time()]
        if app_version is not None:
            sets.append('app_version=?')
            values.append(str(app_version)[:40])
        if platform is not None:
            sets.append('platform=?')
            values.append(str(platform)[:40])
        if ip is not None:
            sets.append('last_ip=?')
            values.append(str(ip)[:64])
        values.append(device_id)
        with self._lock, self.db:
            self.db.execute(f'UPDATE paired_devices SET {", ".join(sets)} WHERE device_id=?', tuple(values))

    def set_session_key(self, device_id: str, session_key: str) -> None:
        with self._lock, self.db:
            self.db.execute('UPDATE paired_devices SET session_key=? WHERE device_id=?',
                            (str(session_key or ''), device_id))

    def revoke(self, device_id: str) -> bool:
        with self._lock, self.db:
            cursor = self.db.execute('UPDATE paired_devices SET revoked=1 WHERE device_id=? AND revoked=0',
                                     (device_id,))
        return bool(cursor.rowcount)

    def revoke_all(self) -> int:
        with self._lock, self.db:
            cursor = self.db.execute('UPDATE paired_devices SET revoked=1 WHERE revoked=0')
        return int(cursor.rowcount)

    def forget(self, device_id: str) -> bool:
        with self._lock, self.db:
            cursor = self.db.execute('DELETE FROM paired_devices WHERE device_id=?', (device_id,))
        return bool(cursor.rowcount)

    def _row(self, device_id: str) -> sqlite3.Row | None:
        if not device_id:
            return None
        with self._lock:
            return self.db.execute('SELECT * FROM paired_devices WHERE device_id=?',
                                   (str(device_id)[:80],)).fetchone()

    def get(self, device_id: str) -> dict | None:
        row = self._row(device_id)
        return _public(row) if row else None

    def list(self, *, include_revoked: bool = False) -> list[dict]:
        query = 'SELECT * FROM paired_devices'
        if not include_revoked:
            query += ' WHERE revoked=0'
        query += ' ORDER BY created_at DESC LIMIT 200'
        with self._lock:
            rows = self.db.execute(query).fetchall()
        return [_public(row) for row in rows]


_registry: DeviceRegistry | None = None
_registry_lock = threading.Lock()


def get_registry(path: Path | str | None = None) -> DeviceRegistry:
    """Process-wide registry. Tests pass their own path to stay isolated."""
    if path is not None:
        return DeviceRegistry(path)
    global _registry
    with _registry_lock:
        if _registry is None:
            _registry = DeviceRegistry(DEFAULT_PATH)
        return _registry
