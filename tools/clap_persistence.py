"""
Windows startup persistence manager for Zaya and Double-Clap listener.
Ensures Zaya can resume listening or running automatically when the PC restarts.
"""
import os
import sys
from pathlib import Path

def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

def get_startup_dir() -> Path:
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
    return Path.home()

def install_startup_launcher() -> tuple[bool, str]:
    """Creates a lightweight batch/cmd script in Windows Startup directory."""
    try:
        startup_dir = get_startup_dir()
        if not startup_dir.exists():
            return False, f"Startup directory not found: {startup_dir}"

        base_dir = get_base_dir()
        python_exe = base_dir / ".venv" / "Scripts" / "python.exe"
        if not python_exe.exists():
            python_exe = Path(sys.executable)

        target_cmd = startup_dir / "Zaya_AutoStart.cmd"
        content = (
            f"@echo off\r\n"
            f"cd /d \"{base_dir}\"\r\n"
            f"start \"Zaya\" \"{python_exe}\" main.py --headless\r\n"
        )
        target_cmd.write_text(content, encoding="utf-8")
        return True, f"Installed startup launcher at {target_cmd}"
    except Exception as e:
        return False, f"Failed to install startup launcher: {e}"

def remove_startup_launcher() -> tuple[bool, str]:
    """Removes the startup launcher if present."""
    try:
        startup_dir = get_startup_dir()
        target_cmd = startup_dir / "Zaya_AutoStart.cmd"
        if target_cmd.exists():
            target_cmd.unlink()
            return True, "Removed startup launcher."
        return True, "No startup launcher found."
    except Exception as e:
        return False, f"Failed to remove startup launcher: {e}"

if __name__ == "__main__":
    ok, msg = install_startup_launcher()
    print(f"[{'OK' if ok else 'FAIL'}] {msg}")
