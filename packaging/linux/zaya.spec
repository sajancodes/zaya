"""Native Linux candidate using the shared, private-data-safe desktop spec."""
import sys
from pathlib import Path

if sys.platform != 'linux':
    raise SystemExit('Build Linux packages on Linux; cross-platform PyInstaller builds are unsupported.')
shared = Path(SPECPATH).parent / 'windows' / 'zaya.spec'
exec(compile(shared.read_text(encoding='utf-8'), str(shared), 'exec'), globals())
