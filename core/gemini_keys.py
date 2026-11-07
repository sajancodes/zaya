"""Gemini credential failover with provider-directed cooldowns, by Sajan Rai."""
import re
import threading
import time
from email.utils import parsedate_to_datetime


# Live resumption handles are provider-owned checkpoints.  A 1008 saying that a
# BidiGenerateContent session is gone means the *checkpoint* is stale, not that
# the model or API key is unavailable.  main.py already rebuilds a session when
# its resume scope changes, so keep a tiny in-process generation counter here.
# error_text() bumps it only for that exact provider failure; conversation_store
# includes the generation in its scope and the next reconnect therefore drops
# the dead handle while keeping the locally archived conversation intact.
_resume_epoch = 0
_resume_epoch_lock = threading.Lock()


def resume_epoch() -> int:
    with _resume_epoch_lock:
        return _resume_epoch


def _invalidate_resume_checkpoint() -> None:
    global _resume_epoch
    with _resume_epoch_lock:
        _resume_epoch += 1


def _expired_live_session(error) -> bool:
    low = str(error).lower()
    return (
        "bidigeneratecontent session not found or expired" in low
        or ("session not found" in low and "expired" in low)
        or ("session expired" in low and "bidigeneratecontent" in low)
    )


def parse_keys(value):
    values = value if isinstance(value, (tuple, list)) else [value]
    return list(dict.fromkeys(part.strip() for item in values if isinstance(item, str)
                             for part in re.split(r'[,\r\n]+', item) if part.strip()))


def configured_keys():
    from memory.config_manager import load_api_keys
    data = load_api_keys()
    return parse_keys(data.get('gemini_api_keys') or data.get('gemini_api_key', ''))


def retry_delay(error):
    headers = getattr(getattr(error, 'response', None), 'headers', {}) or {}
    try:
        return max(1.0, float(headers.get('Retry-After') or headers.get('retry-after')))
    except (TypeError, ValueError):
        try:
            stamp = parsedate_to_datetime(headers.get('Retry-After') or headers.get('retry-after'))
            return max(1.0, stamp.timestamp() - time.time())
        except (TypeError, ValueError, AttributeError):
            pass
    err_msg = str(error).lower()
    if 'inactivity' in err_msg or 'client inactivity' in err_msg:
        return 0.0
    if re.search(r'\b1008\b|denied access|PERMISSION_DENIED', str(error), re.I):
        return 3600.0
    if re.search(r'\b1011\b|quota|exceeded.*quota', str(error), re.I):
        return 60.0
    match = re.search(r"(?:retry\s+in|retry[_\s]?delay[\s'\":=]+)\s*(\d+(?:\.\d+)?)\s*s?", str(error), re.I)
    if match:
        return max(1.0, float(match.group(1)))
    return 60.0


def quota_failure(error):
    for child in getattr(error, 'exceptions', ()):
        found = quota_failure(child)
        if found is not None:
            return found
    err_msg = str(error).lower()
    if 'inactivity' in err_msg or 'client inactivity' in err_msg:
        return None
    if re.search(r'\b429\b|RESOURCE_EXHAUSTED|\b1008\b|\b1011\b|quota|exceeded.*quota|denied access|PERMISSION_DENIED', str(error), re.I):
        return error
    return None

def error_text(error):
    children = getattr(error, 'exceptions', ())
    if children:
        return '\n'.join(error_text(child) for child in children)
    if _expired_live_session(error):
        # Do not return "not found": core.gemini deliberately interprets that
        # phrase as "this model does not exist for this key" and would cool the
        # model for hours.  Here only the resumable checkpoint has expired.
        _invalidate_resume_checkpoint()
        return 'LiveSessionExpired: provider checkpoint expired; reconnect fresh'
    return f'{type(error).__name__}: {error}'


class KeysCooling(RuntimeError):
    def __init__(self, seconds):
        self.retry_after = max(1.0, seconds)
        super().__init__('Configured Gemini keys are cooling down.')


class KeyPool:
    def __init__(self, loader=configured_keys, clock=time.monotonic):
        self.loader, self.clock = loader, clock
        self.lock = threading.Lock()
        self.blocked, self.active = {}, {}

    def keys(self):
        return parse_keys(self.loader())

    def select(self, resource='live'):
        keys = self.keys()
        if not keys:
            raise ValueError('No Gemini API keys configured. Open Gemini API keys in Settings.')
        with self.lock:
            current = self.active.get(resource)
            ordered = ([current] if current in keys else []) + [key for key in keys if key != current]
            for key in ordered:
                if self.blocked.get((key, resource), 0) <= self.clock():
                    self.active[resource] = key
                    return key
            raise KeysCooling(min(self.blocked.get((key, resource), self.clock()) for key in keys) - self.clock())

    def limited(self, key, error, resource='live'):
        with self.lock:
            self.blocked[(key, resource)] = self.clock() + retry_delay(error)

    def ready(self, resource='live'):
        try:
            self.select(resource)
            return True
        except (KeysCooling, ValueError):
            return False


pool = KeyPool()
