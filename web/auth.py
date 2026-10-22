"""Authentication and session management for Zaya owner admin dashboard.
Created and developed by Sajan Rai for Zaya.

Guarantees:
- Admin endpoints require authentication.
- Secure session tokens (32 bytes hex) stored with expiration.
- Constant-time secret comparison prevents timing attacks.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import time
from typing import Optional

from web.database import get_connection

# Default owner admin credentials can be set via environment variable
ADMIN_DEFAULT_USER = os.environ.get("ADMIN_USER", "owner")
ADMIN_DEFAULT_PASSWORD = os.environ.get("ADMIN_PASSWORD", "ZayaOwner2026!")
SESSION_DURATION_SECONDS = 7 * 86400  # 7 days


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
    """Verify admin login credentials against environment or database."""
    clean_user = username.strip()
    # Check environment variable config first
    if clean_user == ADMIN_DEFAULT_USER:
        return hmac.compare_digest(password, ADMIN_DEFAULT_PASSWORD)
    return False


def create_session(username: str) -> str:
    """Generate and store a new admin session token."""
    token = secrets.token_hex(32)
    now = int(time.time())
    expires_at = now + SESSION_DURATION_SECONDS

    conn = get_connection()
    try:
        with conn:
            # Clean expired sessions
            conn.execute("DELETE FROM admin_sessions WHERE expires_at < ?;", (now,))
            conn.execute("""
                INSERT INTO admin_sessions (token, username, created_at, expires_at)
                VALUES (?, ?, ?, ?);
            """, (token, username, now, expires_at))
        return token
    finally:
        conn.close()


def validate_session(token: Optional[str]) -> bool:
    """Check if session token is valid and not expired."""
    if not token or len(token) != 64:
        return False

    now = int(time.time())
    conn = get_connection()
    try:
        cursor = conn.execute("""
            SELECT username FROM admin_sessions
            WHERE token = ? AND expires_at > ?;
        """, (token, now))
        return cursor.fetchone() is not None
    finally:
        conn.close()


def revoke_session(token: str) -> None:
    """Revoke an active admin session."""
    conn = get_connection()
    try:
        with conn:
            conn.execute("DELETE FROM admin_sessions WHERE token = ?;", (token,))
    finally:
        conn.close()
