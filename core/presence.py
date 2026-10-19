"""Whether the owner is actually sitting at this machine.

Presence changes *how* something is delivered, never *whether*: finished work is
worth a phone call when the owner is out, and worth nothing more than a line on
the desktop he is already looking at.

Windows exposes the last keyboard/mouse input time, which is the honest signal
available without extra permissions. Anywhere else the answer is "unknown", and
unknown deliberately falls back to the quieter path — ringing a phone on a guess
is exactly the habit the call policy exists to prevent.
"""
from __future__ import annotations

import ctypes
import logging
import sys

log = logging.getLogger(__name__)

DEFAULT_AWAY_SECONDS = 600.0
_MIN_AWAY_SECONDS = 60.0


def desktop_idle_seconds() -> float | None:
    """Seconds since the last keyboard or mouse input, or None when unknown."""
    if sys.platform != 'win32':
        return None
    try:
        class _LastInput(ctypes.Structure):
            _fields_ = [('cbSize', ctypes.c_uint), ('dwTime', ctypes.c_uint)]

        info = _LastInput()
        info.cbSize = ctypes.sizeof(_LastInput)
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
            return None
        # GetTickCount wraps every ~49 days. The subtraction is kept in 32-bit
        # arithmetic so a wrap cancels out instead of reporting a huge idle time.
        now = ctypes.windll.kernel32.GetTickCount()
        elapsed_ms = (int(now) - int(info.dwTime)) & 0xFFFFFFFF
        return elapsed_ms / 1000.0
    except Exception:
        log.debug('Desktop idle time unavailable', exc_info=True)
        return None


def owner_is_away(idle_seconds: float = DEFAULT_AWAY_SECONDS) -> bool:
    """True only when we can prove the owner has been gone for a while."""
    idle = desktop_idle_seconds()
    if idle is None:
        return False
    try:
        threshold = max(_MIN_AWAY_SECONDS, float(idle_seconds))
    except (TypeError, ValueError):
        threshold = DEFAULT_AWAY_SECONDS
    return idle >= threshold
