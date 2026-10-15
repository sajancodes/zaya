"""Gemini credential failover with provider-directed cooldowns, by Sajan Rai."""
import re
import threading
import time
from email.utils import parsedate_to_datetime


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
    match = re.search(r"(?:retry\s+in|retry[_\s]?delay[\s'\":=]+)\s*(\d+(?:\.\d+)?)\s*s?", str(error), re.I)
    if match:
        return max(1.0, float(match.group(1)))
    return 60.0


def quota_failure(error):
    for child in getattr(error, 'exceptions', ()):
        found = quota_failure(child)
        if found is not None:
            return found
    if re.search(r'\b429\b|RESOURCE_EXHAUSTED', str(error), re.I):
        return error
    return None


def error_text(error):
    children = getattr(error, 'exceptions', ())
    return '\n'.join(error_text(child) for child in children) if children else f'{type(error).__name__}: {error}'


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
            raise KeysCooling(min(self.blocked[(key, resource)] for key in keys) - self.clock())

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
