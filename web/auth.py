"""Authentication and session management for Zaya owner admin dashboard.
Created and developed by Sajan Rai for Zaya.

Guarantees:
- Admin endpoints require authentication.
- Production refuses to enable /admin without an explicit, strong ADMIN_PASSWORD (min 12 chars).
- Public default passwords (e.g. ZayaOwner2026!) are strictly rejected.
- Rate-limiting prevents brute-force login attempts (max 5 per 5 minutes per IP).
- Secure session tokens (32 bytes hex) stored with expiration.
- Constant-time secret comparison prevents timing attacks.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import threading
import time
from typing import Dict, List, Optional

from web.database import get_connection

ADMIN_USER = os.environ.get("ADMIN_USER", "owner")
SESSION_DURATION_SECONDS = 7 * 86400  # 7 days

# Brute-force rate limiting: max 5 login attempts per 300 seconds (5 mins) per client IP
_LOGIN_RATE_LIMIT_MAX = 5
_LOGIN_RATE_LIMIT_WINDOW = 300
_login_attempts: Dict[str, List[float]] = {}
_login_lock = threading.Lock()

DISALLOWED_PASSWORDS = {
    "zayaowner2026!",
    "password",
    "admin",
    "changeme",
    "12345678",
    "1234567890",
    "secret",
}


def is_admin_enabled() -> bool:
    """Check if the admin dashboard is safely enabled with a strong configured secret."""
    admin_pw = os.environ.get("ADMIN_PASSWORD", "").strip()
    if not admin_pw:
        return False
    if admin_pw.lower() in DISALLOWED_PASSWORDS:
        return False
    if len(admin_pw) < 12:
        return False
    return True


def is_login_rate_limited(client_ip: str) -> bool:
    """Check if the requesting client IP has exceeded the failed login threshold."""
    if not client_ip:
        return False
    now = time.monotonic()
    with _login_lock:
        attempts = _login_attempts.get(client_ip, [])
        recent = [t for t in attempts if now - t < _LOGIN_RATE_LIMIT_WINDOW]
        _login_attempts[client_ip] = recent
        return len(recent) >= _LOGIN_RATE_LIMIT_MAX


def record_login_failure(client_ip: str) -> None:
    """Record a failed login attempt for the client IP."""
    if not client_ip:
        return
    now = time.monotonic()
    with _login_lock:
        attempts = _login_attempts.get(client_ip, [])
        recent = [t for t in attempts if now - t < _LOGIN_RATE_LIMIT_WINDOW]
        recent.append(now)
        _login_attempts[client_ip] = recent


def clear_login_failures(client_ip: str) -> None:
    """Reset failed login attempts for client IP upon successful authentication."""
    if not client_ip:
        return
    with _login_lock:
        _login_attempts.pop(client_ip, None)


def hash_password(password: str, salt: Optional[bytes] = None) -> str:
    """Hash password using PBKDF2-HMAC-SHA256."""
    if salt is None:
        salt = secrets.token_bytes(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000)
    return f"{salt.hex()}:{key.hex()}"


def verify_password(provided_password: str, stored_hash: str) -> bool:
    """Verify password against stored salt:key hash in constant time."""
    try:
        salt_hex, key_hex = stored_hash.split(":")
        salt = bytes.fromhex(salt_hex)
        expected_key = bytes.fromhex(key_hex)
        candidate_key = hashlib.pbkdf2_hmac("sha256", provided_password.encode("utf-8"), salt, 100000)
        return hmac.compare_digest(candidate_key, expected_key)
    except Exception:
        return False


def verify_admin_credentials(username: str, password: str) -> bool:
    """Verify admin login credentials against environment or database.

    Strictly refuses if ADMIN_PASSWORD is not configured or uses a weak default.
    """
    if not is_admin_enabled():
        return False

    clean_user = username.strip()
    target_user = os.environ.get("ADMIN_USER", "owner").strip()
    target_pw = os.environ.get("ADMIN_PASSWORD", "").strip()

    if hmac.compare_digest(clean_user, target_user):
        return hmac.compare_digest(password, target_pw)
    return False


def create_session(username: str) -> str:
    """Generate and store a new admin session token."""
    token = secrets.token_hex(32)
    now = int(time.time())
    expires_at = now + SESSION_DURATION_SECONDS

    conn = get_connection()
    try:
        with conn:
            conn.execute("""
                INSERT INTO admin_sessions (token, username, created_at, expires_at)
                VALUES (?, ?, ?, ?);
            """, (token, username, now, expires_at))
    finally:
        conn.close()
    return token


def validate_session(token: Optional[str]) -> bool:
    """Validate an active admin session token."""
    if not token or len(token) != 64:
        return False

    now = int(time.time())
    conn = get_connection()
    try:
        cursor = conn.execute("""
            SELECT username, expires_at FROM admin_sessions
            WHERE token = ?;
        """, (token,))
        row = cursor.fetchone()
        if not row:
            return False
        if row["expires_at"] < now:
            # Clean expired token
            with conn:
                conn.execute("DELETE FROM admin_sessions WHERE token = ?;", (token,))
            return False
        return True
    finally:
        conn.close()


def revoke_session(token: str) -> None:
    """Revoke an active admin session token."""
    if not token:
        return
    conn = get_connection()
    try:
        with conn:
            conn.execute("DELETE FROM admin_sessions WHERE token = ?;", (token,))
    finally:
        conn.close()
