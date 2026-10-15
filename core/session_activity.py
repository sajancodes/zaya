"""Expiring owner-authorized activity for contextual WhatsApp replies.

No chat history, profile, command arguments, files or credentials are exported.
State is in memory and vanishes when Zaya exits.
"""
import re
import threading
import time
from core.audit import redact
from core.execution_policy import require_owner


class SessionActivity:
    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.lock = threading.RLock()
        self.items = {}

    def set(self, kind, summary, seconds=1200):
        require_owner()
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

    def clear(self, kind=None):
        require_owner()
        with self.lock:
            if kind is None:
                self.items.clear()
            else:
                self.items.pop(kind, None)

    def snapshot(self):
        with self.lock:
            now = self.clock()
            return [{'kind': item['kind'], 'summary': item['summary'], 'age_seconds': round(max(0, now - item['at']))}
                    for item in self.items.values() if item['expires'] is None or now < item['expires']]

    def media(self, title, playing):
        if not playing:
            self.clear('media')
            return
        try:
            self.set('media', f'Sajan is currently playing {str(title).strip()[:160] or "media"} on his display.', seconds=None)
        except ValueError:
            self.set('media', 'Sajan is currently playing media on his display.', seconds=None)


activity = SessionActivity()
