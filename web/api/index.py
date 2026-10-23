"""Vercel entry point when the project root is web/."""
import sys
import types
from pathlib import Path

root = Path(__file__).resolve().parents[1]
if 'web' not in sys.modules:
    package = types.ModuleType('web')
    package.__path__ = [str(root)]
    sys.modules['web'] = package

from web.server import app  # noqa: E402,F401
