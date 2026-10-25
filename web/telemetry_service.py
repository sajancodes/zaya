"""Telemetry validation, sanitization, and rate-limiting service.
Created and developed by Sajan Rai for Zaya.

Protects backend from invalid payloads and rate-limits spam submissions.
"""
from __future__ import annotations

import re
import threading
import time
from typing import Dict, List, Optional, Tuple

# Standard UUIDv4 pattern (hex characters, version 4)
UUID_PATTERN = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$", re.IGNORECASE)
VERSION_PATTERN = re.compile(r"^[0-9]+\.[0-9]+(\.[0-9]+)?(-[0-9A-Za-z.]+)?$")
ALLOWED_PLATFORMS = {"windows", "android", "linux"}

# Simple sliding window rate limiter: max 30 requests per 60 seconds per IP
_RATE_LIMIT_MAX = 30
_RATE_LIMIT_WINDOW_SECONDS = 60
_ip_request_history: Dict[str, List[float]] = {}
_lock = threading.Lock()


def is_rate_limited(client_ip: str) -> bool:
    """Check if the requesting client IP has exceeded the telemetry rate limit."""
    from web.database import firebase_enabled
    if firebase_enabled():
        from web.shared_limits import consume
        return consume(client_ip, 'telemetry', _RATE_LIMIT_MAX, _RATE_LIMIT_WINDOW_SECONDS)
    if not client_ip:
        return False

    now = time.monotonic()
    with _lock:
        timestamps = _ip_request_history.get(client_ip, [])
        # Prune old timestamps
        recent = [t for t in timestamps if now - t < _RATE_LIMIT_WINDOW_SECONDS]
        if len(recent) >= _RATE_LIMIT_MAX:
            _ip_request_history[client_ip] = recent
            return True
        recent.append(now)
        _ip_request_history[client_ip] = recent

        # Periodically clean up stale IPs if map grows large
        if len(_ip_request_history) > 10000:
            stale_threshold = now - _RATE_LIMIT_WINDOW_SECONDS
            stale_keys = [k for k, v in _ip_request_history.items() if not v or v[-1] < stale_threshold]
            for k in stale_keys:
                del _ip_request_history[k]

        return False


def validate_telemetry_payload(data: dict) -> Tuple[bool, str]:
    """Validate and sanitize an incoming telemetry payload."""
    if not isinstance(data, dict):
        return False, "Payload must be a JSON object."

    installation_id = str(data.get("installation_id", "")).strip()
    if not UUID_PATTERN.match(installation_id):
        return False, f"Invalid installation_id format: must be standard UUIDv4."

    platform = str(data.get("platform", "")).strip().lower()
    if platform not in ALLOWED_PLATFORMS:
        return False, f"Unsupported platform: '{platform}'."

    version = str(data.get("version", "")).strip()
    if not VERSION_PATTERN.match(version):
        return False, f"Invalid version string format: '{version}'."

    return True, "Valid"
