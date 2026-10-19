"""Local rotating diagnostics for the log terminal; secrets are redacted."""
from __future__ import annotations

import io
import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import re
import sys
import threading

from core.audit import redact

LOG_PATH = Path(__file__).resolve().parent.parent / 'logs' / 'runtime' / 'zaya.log'
_lock = threading.RLock()
_loggers = {}
_enabled = False


class DiagnosticFileHandler(RotatingFileHandler):
    def handleError(self, record):
        # stderr is also captured. Reporting a disk error through stderr here
        # would recurse into this same failing handler.
        pass


def log_line(value, *, source='runtime', path=None):
    """Diagnostics must never break the application they are observing."""
    if path is None and not _enabled:
        return  # Imported tools/tests must not write into the owner's live log.
    target = Path(path or LOG_PATH)
    try:
        text = value if isinstance(value, str) else json.dumps(redact(value), ensure_ascii=False, default=str)
        text = redact(text)
        text = re.sub(r'''(?i)(["']?(?:api[_-]?key|token|password|secret|cookie|authorization)["']?\s*[:=]\s*["']?)[^\s,;"']+''',
                      r'\1[REDACTED]', text)
        with _lock:
            logger = _loggers.get(target)
            if logger is None:
                target.parent.mkdir(parents=True, exist_ok=True)
                logger = logging.Logger('zaya-runtime', level=logging.INFO)
                logger.propagate = False
                handler = DiagnosticFileHandler(target, maxBytes=2_000_000, backupCount=3, encoding='utf-8')
                handler.setFormatter(logging.Formatter('%(asctime)s [%(source)s] %(message)s'))
                logger.addHandler(handler)
                _loggers[target] = logger
            for line in text.splitlines():
                logger.info(line, extra={'source': source})
    except (OSError, ValueError):
        pass


class DiagnosticStream(io.TextIOBase):
    """Keep console output while buffering whole lines for secret redaction."""
    def __init__(self, original, source, path=None):
        self.original, self.source, self.path = original, source, path
        self.local = threading.local()

    @property
    def encoding(self):
        return getattr(self.original, 'encoding', None) or 'utf-8'

    def write(self, text):
        if self.original is not None:
            try:
                self.original.write(text)
            except (OSError, ValueError, UnicodeError):
                pass
        pending = getattr(self.local, 'pending', '') + text
        lines = pending.split('\n')
        dropping = getattr(self.local, 'dropping', False)
        for line in lines[:-1]:
            if not dropping:
                log_line(line if len(line) <= 16384 else '[oversized diagnostic line omitted]', source=self.source, path=self.path)
            dropping = False
        self.local.pending = lines[-1]
        if len(self.local.pending) > 16384:
            self.local.pending = ''
            if not dropping:
                log_line('[oversized diagnostic line omitted]', source=self.source, path=self.path)
            dropping = True
        self.local.dropping = dropping
        return len(text)

    def flush(self):
        if self.original is not None:
            try:
                self.original.flush()
            except (OSError, ValueError):
                pass

    def isatty(self):
        return self.original is not None and self.original.isatty()


def install_runtime_logging():
    global _enabled
    _enabled = True
    for name in ('stdout', 'stderr'):
        original = getattr(sys, name)
        if not isinstance(original, DiagnosticStream):
            setattr(sys, name, DiagnosticStream(original, name))
    log_line('Zaya started. This local log contains runtime output, UI activity and OpenCode evidence.')
