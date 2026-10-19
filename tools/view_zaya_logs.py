"""Read-only Zaya diagnostic terminal. Does not start an agent or run jobs."""
import argparse
from collections import deque
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.runtime_logging import LOG_PATH
from core.audit import redact


def saved_status(path=None):
    """A persisted job is history, never evidence that its process is alive."""
    try:
        data = json.loads(Path(path or ROOT / 'memory' / 'coding_jobs.json').read_text(encoding='utf-8'))
        job = max(data.get('jobs', []), key=lambda row: row.get('updated_at', 0), default=None)
        if job:
            return redact({key: job.get(key) for key in ('id', 'phase', 'project', 'session_id', 'error')})
    except (OSError, ValueError, TypeError):
        pass
    return None


def show(path=LOG_PATH, *, once=False):
    print('Zaya terminal logs — created by Sajan Rai', flush=True)
    print('Local diagnostics only. This viewer does not start or resume OpenCode.', flush=True)
    print('Last saved job (history; not proof a process is running):', saved_status(), flush=True)
    print('Log:', path, '\nPress Ctrl+C to close this viewer.\n', flush=True)
    position, identity, first = 0, None, True
    while True:
        try:
            state = path.stat()
            if identity != state.st_ino or state.st_size < position:
                position = 0
            identity = state.st_ino
            with path.open(encoding='utf-8', errors='replace') as stream:
                if first:
                    print(''.join(deque(stream, maxlen=120)), end='', flush=True)
                else:
                    stream.seek(position)
                    print(stream.read(), end='', flush=True)
                position = stream.tell()
            first = False
        except FileNotFoundError:
            if first:
                print('Waiting for runtime logs. Restart Zaya once to enable logging.', flush=True)
                first = False
        if once:
            return
        time.sleep(1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--once', action='store_true', help='Print recent diagnostics and exit.')
    try:
        show(once=parser.parse_args().once)
    except KeyboardInterrupt:
        pass
