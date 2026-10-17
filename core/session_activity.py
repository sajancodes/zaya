"""Expiring owner-authorized activity for contextual WhatsApp replies.

No chat history, profile, command arguments, files or credentials are exported.
State is in memory and vanishes when Zaya exits.
"""
import re
import threading
import time
from core.audit import redact
from core.execution_policy import (
    TRUST_AUTHENTICATED_REMOTE_OWNER,
    TRUST_LOCAL_OWNER,
    TRUST_SYSTEM_EVENT,
    TRUST_UNKNOWN,
    get_trust,
    require_owner,
)


_RUNTIME_MEDIA_TRUST = {
    TRUST_LOCAL_OWNER,
    TRUST_AUTHENTICATED_REMOTE_OWNER,
    TRUST_SYSTEM_EVENT,
    TRUST_UNKNOWN,
}


def _require_runtime_media_update():
    """Allow local runtime media callbacks without widening privileged tool access.

    Qt playback signals can fire after the owner tool-call context has ended, so
    production sees them as ``unknown``.  Media activity is only contextual,
    in-memory bookkeeping; external/web/document/tool-output trust levels remain
    unable to mutate it.
    """
    if get_trust() not in _RUNTIME_MEDIA_TRUST:
        require_owner()


class SessionActivity:
    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.lock = threading.RLock()
        self.items = {}

    def _set(self, kind, summary, seconds=1200):
        if kind not in {'media', 'project', 'other'}:
            raise ValueError('Activity kind must be media, project or other.')
        summary = str(summary).strip()
        if (not summary or len(summary) > 220 or '\n' in summary or '\r' in summary
                or redact(summary) != summary
                or re.search(r'https?://|[A-Za-z]:[\\/]|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}', summary)):
            raise ValueError('Use a short activity description without secrets, links, email addresses or local paths.')
        with self.lock:
            self.items[kind] = {'kind': kind, 'summary': summary, 'at': self.clock(),
                                'expires': None if seconds is None else self.clock() + max(1, min(seconds, 3600))}

    def set(self, kind, summary, seconds=1200):
        require_owner()
        self._set(kind, summary, seconds)

    def _clear(self, kind=None):
        with self.lock:
            if kind is None:
                self.items.clear()
            else:
                self.items.pop(kind, None)

    def clear(self, kind=None):
        # Qt's media-close callback runs outside the originating owner context.
        # Permit that one non-privileged bookkeeping operation, but keep every
        # other activity mutation owner-only.
        if kind == 'media':
            _require_runtime_media_update()
        else:
            require_owner()
        self._clear(kind)

    def snapshot(self):
        with self.lock:
            now = self.clock()
            return [{'kind': item['kind'], 'summary': item['summary'], 'age_seconds': round(max(0, now - item['at']))}
                    for item in self.items.values() if item['expires'] is None or now < item['expires']]

    def media(self, title, playing):
        # QMediaPlayer playback-state signals are asynchronous and commonly run
        # with TRUST_UNKNOWN after the owner-authorized video tool has returned.
        _require_runtime_media_update()
        if not playing:
            self._clear('media')
            return
        try:
            self._set('media', f'Sajan is currently playing {str(title).strip()[:160] or "media"} on his display.', seconds=None)
        except ValueError:
            self._set('media', 'Sajan is currently playing media on his display.', seconds=None)


activity = SessionActivity()
