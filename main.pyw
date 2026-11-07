"""Zaya windowless entry point for Windows desktop.
Created and developed by Sajan Rai for Zaya.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure repo root is on sys.path
_REPO_ROOT = Path(__file__).resolve().parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# Ensure working directory is repo root
os.chdir(_REPO_ROOT)

from main import main

if __name__ == "__main__":
    main()
