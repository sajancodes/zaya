"""Windows startup registration helper.
Created and developed by Sajan Rai for Zaya.

Uses standard, transparent user-level Windows Run key:
HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run
Zero persistence trickery, full user control, easily enabled/disabled anytime.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

RUN_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_VALUE_NAME = "Zaya"


def is_startup_supported() -> bool:
    """Return True if running on Windows."""
    return sys.platform == "win32"


def get_target_executable_path() -> Optional[Path]:
    """Return the executable path to launch on Windows sign-in."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve()
    # In development mode, locate pythonw or repo entry
    repo_root = Path(__file__).resolve().parent.parent
    candidate_bat = repo_root / "zaya.cmd"
    if candidate_bat.is_file():
        return candidate_bat.resolve()
    return Path(sys.executable).resolve()


def is_startup_enabled() -> bool:
    """Check if Zaya is currently registered to run at Windows sign-in."""
    if not is_startup_supported():
        return False

    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0, winreg.KEY_READ) as key:
            try:
                val, _ = winreg.QueryValueEx(key, APP_VALUE_NAME)
                return bool(val)
            except FileNotFoundError:
                return False
    except Exception as e:
        logger.debug(f"Could not read Windows startup registry key: {e}")
        return False


def set_startup_enabled(enabled: bool) -> bool:
    """Enable or disable starting Zaya automatically at Windows sign-in."""
    if not is_startup_supported():
        return False

    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0, winreg.KEY_SET_VALUE | winreg.KEY_READ) as key:
            if enabled:
                exe_path = get_target_executable_path()
                if not exe_path or not exe_path.exists():
                    logger.warning("Cannot enable startup: application executable not found.")
                    return False
                # Quote path to handle spaces in Program Files / AppData
                cmd = f'"{exe_path}"'
                winreg.SetValueEx(key, APP_VALUE_NAME, 0, winreg.REG_SZ, cmd)
                return True
            else:
                try:
                    winreg.DeleteValue(key, APP_VALUE_NAME)
                except FileNotFoundError:
                    pass
                return True
    except Exception as e:
        logger.error(f"Failed to update Windows startup registry key: {e}")
        return False
