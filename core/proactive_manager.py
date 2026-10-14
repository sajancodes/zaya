"""Selective, deterministic notifications; never promote contact text to commands."""
from __future__ import annotations
from collections import deque
import threading
import time
from core.event_bus import bus


class ProactiveManager:
    def __init__(self, store, clock=time.time) -> None:
        self.store, self.clock = store, clock
        self.lock = threading.Lock()
        self.queue = deque(maxlen=100)
        self.last_spoken = 0.0
        self.unsubscribe = bus.subscribe('task.failed', self.on_failure)

    def close(self) -> None:
        self.unsubscribe()

    def on_failure(self, event: dict) -> None:
        with self.lock:
            self.queue.append({'kind': 'task', 'summary': 'Sir, an operator task failed. Its error and retained state are available in runtime status.'})

    def mute(self, seconds: float) -> None:
        with self.store.lock, self.store.db:
            self.store.db.execute('INSERT OR REPLACE INTO wa_settings VALUES(?,?)',
                                  ('alerts_muted_until', str(self.clock() + max(0, min(seconds, 86400)))))

    def next(self, busy: bool = False) -> dict | None:
        now = self.clock()
        if busy or now - self.last_spoken < 30:
            return None
        muted = self.store.rows('SELECT value FROM wa_settings WHERE key=?', ('alerts_muted_until',))
        if not muted or float(muted[0]['value']) <= now:
            alerts = self.store.rows('SELECT alert_id,score FROM wa_alerts WHERE delivered_at IS NULL AND acknowledged_at IS NULL AND score>=70 ORDER BY score DESC,created_at LIMIT 10')
            if alerts:
                # Avoid sending raw untrusted contact text or classifier reasons
                # as a privileged user turn to the main Gemini session.
                count = len(alerts)
                return {'kind': 'whatsapp', 'ids': [a['alert_id'] for a in alerts],
                        'summary': f'Sir, you have {count} important WhatsApp notification' + ('s.' if count != 1 else '.') + ' The observed messages are available in your inbox.'}
        with self.lock:
            return dict(self.queue[0]) if self.queue else None

    def delivered(self, item: dict) -> None:
        self.last_spoken = self.clock()
        if item['kind'] == 'whatsapp':
            with self.store.lock, self.store.db:
                self.store.db.executemany('UPDATE wa_alerts SET delivered_at=? WHERE alert_id=?', [(self.clock(), alert_id) for alert_id in item['ids']])
        else:
            with self.lock:
                if self.queue:
                    self.queue.popleft()
