"""Native Linux hand worker using the shared worker packaging spec."""
import sys
from pathlib import Path

if sys.platform != 'linux':
    raise SystemExit('Build the Linux hand worker on Linux.')
shared = Path(SPECPATH).parent / 'windows' / 'zaya-hand-worker.spec'
exec(compile(shared.read_text(encoding='utf-8'), str(shared), 'exec'), globals())
