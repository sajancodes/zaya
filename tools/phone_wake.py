"""Windowless logon entry point for Zaya's paired-phone launcher."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import os
from core.phone_wake import install, serve
from core.desktop_lifecycle import spawn_fixed

if __name__ == '__main__':
    if '--install' in sys.argv:
        install()
    elif os.name == 'nt' and Path(sys.executable).name.lower() == 'pythonw.exe':
        # Hidden bootstrap, then the same Python executable already used by
        # the dashboard's firewall permission. CREATE_NO_WINDOW stays set.
        spawn_fixed([str(Path(__file__).resolve()), '--serve'], windowless=False)
    else:
        serve()
