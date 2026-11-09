"""Platform Adapter Factory for Zaya.
Created and developed by Sajan Rai for Zaya.
"""
from __future__ import annotations

import sys
from core.platform.base import PlatformAdapter
from core.platform.windows import WindowsAdapter
from core.platform.macos import MacOSAdapter
from core.platform.linux import LinuxAdapter

_adapter: PlatformAdapter | None = None


def get_platform_adapter() -> PlatformAdapter:
    """Return the singleton platform adapter for the current host OS."""
    global _adapter
    if _adapter is None:
        if sys.platform == "win32":
            _adapter = WindowsAdapter()
        elif sys.platform == "darwin":
            _adapter = MacOSAdapter()
        else:
            _adapter = LinuxAdapter()
    return _adapter
