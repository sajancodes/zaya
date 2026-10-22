"""Zaya application version definitions.
Created and developed by Sajan Rai for Zaya.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

_DEFAULT_VERSION = "0.5.0"
_DEFAULT_BUILD = 10007
_DEFAULT_CHANNEL = "stable"


def _load_embedded_version() -> dict:
    version_file = Path(__file__).resolve().parent.parent / "version.json"
    if version_file.is_file():
        try:
            return json.loads(version_file.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


_embedded = _load_embedded_version()

VERSION: str = os.environ.get("ZAYA_VERSION") or _embedded.get("version") or _DEFAULT_VERSION
BUILD: int = int(os.environ.get("ZAYA_BUILD") or os.environ.get("ZAYA_VERSION_CODE") or _embedded.get("build") or _DEFAULT_BUILD)
CHANNEL: str = os.environ.get("ZAYA_CHANNEL") or _embedded.get("channel") or _DEFAULT_CHANNEL


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
