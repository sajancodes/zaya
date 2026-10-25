"""Zaya application version definitions.
Created and developed by Sajan Rai for Zaya.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

def semver_key(version: str) -> tuple:
    """Strict SemVer precedence, including numeric prerelease identifiers."""
    match = re.fullmatch(r'(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?', version)
    if not match:
        raise ValueError('Expected a semantic version such as 1.0.0 or 1.1.0-beta.1.')
    pre = match[4]
    identifiers = []
    for item in pre.split('.') if pre else []:
        if item.isdigit() and len(item) > 1 and item[0] == '0':
            raise ValueError('Numeric prerelease identifiers cannot have leading zeros.')
        identifiers.append((0, int(item)) if item.isdigit() else (1, item))
    return (*map(int, match.group(1, 2, 3)), not bool(pre), tuple(identifiers))


def _load_embedded_version() -> dict:
    version_file = Path(__file__).resolve().parent.parent / "version.json"
    if version_file.is_file():
        try:
            return json.loads(version_file.read_text(encoding="utf-8"))
        except Exception:
            pass
    raise RuntimeError('Canonical version.json is missing or invalid.')


_embedded = _load_embedded_version()

VERSION: str = _embedded['version']
BUILD: int = int(_embedded['build'])
CHANNEL: str = _embedded['channel']
semver_key(VERSION)
if CHANNEL not in ('stable', 'beta') or BUILD <= 0 or (CHANNEL == 'stable' and not semver_key(VERSION)[3]):
    raise ValueError('Invalid canonical release channel/build.')


def version_string() -> str:
    """Return friendly user-facing version description."""
    return f"Zaya v{VERSION} (build {BUILD}, {CHANNEL})"


def as_dict() -> dict:
    """Return version metadata dictionary."""
    return {
        "version": VERSION,
        "build": BUILD,
        "channel": CHANNEL,
        "display": version_string()
    }


def write_version_file(destination: Path, version: str = VERSION, build: int = BUILD, channel: str = CHANNEL) -> Path:
    """Write embedded version.json for packaging."""
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    content = {
        "version": version,
        "build": build,
        "channel": channel,
        "display": f"Zaya v{version} (build {build}, {channel})"
    }
    destination.write_text(json.dumps(content, indent=2) + "\n", encoding="utf-8")
    return destination
