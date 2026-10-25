"""Explicit private profile import. Never scrape or seed sensitive historical facts."""
from __future__ import annotations
from datetime import datetime, timezone
import json
from pathlib import Path
from core.runtime_paths import mutable_path
import re
from memory.memory_manager import update_memory

PROFILE_PATH = mutable_path(Path(__file__).resolve().parent / 'profile.json')
CATEGORIES = {'identity', 'preferences', 'projects', 'device', 'notes'}
SENSITIVE_KEY = re.compile(r'password|secret|token|api.?key|credential|bank|wallet|phone|address|national.?id|medical', re.I)


def bootstrap(source: Path, destination: Path = PROFILE_PATH) -> dict:
    if source.stat().st_size > 100000:
        raise ValueError('Profile file is too large.')
    data = json.loads(source.read_text(encoding='utf-8-sig'))
    if not isinstance(data, dict) or not set(data).issubset(CATEGORIES):
        raise ValueError('Profile must contain identity, preferences, projects, device or notes categories.')
    records = {}
    for category, facts in data.items():
        if not isinstance(facts, dict):
            raise ValueError('Each category must contain named facts.')
        records[category] = {}
        for key, value in facts.items():
            if SENSITIVE_KEY.search(key):
                raise ValueError(f'Sensitive profile field requires a separate private-memory policy: {key}')
            if not isinstance(value, (str, int, float)):
                raise ValueError('Profile facts must be scalar values.')
            records[category][key] = {'value': str(value), 'source': 'user_profile_import', 'confidence': 1.0}
    # Import only explicitly supplied source data, never fields extracted from
    # the implementation plan or previous unrelated conversations.
    update_memory(records)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps({'imported_at': datetime.now(timezone.utc).isoformat(), 'facts': records}, ensure_ascii=False, indent=2), encoding='utf-8')
    return {'categories': list(records), 'fact_count': sum(len(v) for v in records.values())}
