"""Local structured audit logs with recursive secret redaction."""
from __future__ import annotations
import json
import os
import re
import threading
from pathlib import Path
from core.runtime_paths import get_user_data_dir

ROOT = get_user_data_dir()
_lock = threading.Lock()
_secret_name = re.compile(r'key|token|secret|password|authorization|cookie|credential', re.I)


def redact(value):
    if isinstance(value, dict):
        return {k: '[REDACTED]' if _secret_name.search(str(k)) else redact(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(v) for v in value]
    if isinstance(value, str):
        value = re.sub(r'(?:AIza[\w-]{25,}|gh[pousr]_[\w]{20,}|sk-[\w-]{20,})', '[REDACTED]', value)
        value = re.sub(r'(?i)(bearer\s+|(?:api[_-]?key|token|password|secret|cookie)\s*[:=]\s*)[^\s,;]+', r'\1[REDACTED]', value)
        for key, secret in os.environ.items():
            if _secret_name.search(key) and len(secret) >= 6:
                value = value.replace(secret, '[REDACTED]')
    return value


def write(event: dict, path: Path | None = None) -> None:
    target = path or ROOT / 'logs' / 'runtime' / 'events.jsonl'
    target.parent.mkdir(parents=True, exist_ok=True)
    with _lock, target.open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(redact(event), ensure_ascii=False, default=str) + '\n')
