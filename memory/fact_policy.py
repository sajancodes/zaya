"""Shared acceptance and expiry rules for local factual memory."""
from datetime import datetime, timezone
import math
import time


def confidence(value=1.0):
    try:
        result = float(value)
        return min(1.0, max(0.0, result)) if math.isfinite(result) else 0.0
    except (TypeError, ValueError):
        return 0.0


def expiry(value):
    if value is None or value == '':
        return None
    parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


def active(entry, now=None):
    if not isinstance(entry, dict):
        return True
    if confidence(entry.get('confidence', 1.0)) < .7:
        return False
    try:
        until = expiry(entry.get('expires_at'))
        return until is None or datetime.fromisoformat(until.replace('Z', '+00:00')).timestamp() > (time.time() if now is None else now)
    except (TypeError, ValueError, OverflowError):
        return False
