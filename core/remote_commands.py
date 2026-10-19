"""Remote command bookkeeping: one scope per request, no silent replays.

Two problems this exists to solve.

1. A remote command used to reuse whatever owner scope the laptop last set. The
   operator keys cached tool results by `scope:tool:args`, so a second phone
   command could be answered from the first command's memoised execution. Every
   accepted request now gets its own scope, exactly like a typed desktop command.

2. A phone that loses Wi-Fi mid-request has no way to know whether the laptop saw
   it. The transport is therefore split into three explicit stages —
   `submitted`, `acknowledged`, `completed` — and the phone may only resend when
   it still holds the same `request_id`. The gate recognises that id and reports a
   duplicate instead of running the command twice.

Commands arrive from more than one transport (dashboard HTTP, dashboard
WebSocket, the Android socket), so the gate is deliberately transport-agnostic.
"""
from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field

SUBMITTED = 'submitted'
ACKNOWLEDGED = 'acknowledged'
EXECUTING = 'executing'
COMPLETED = 'completed'
FAILED = 'failed'

# Identical text from the same source inside this window is treated as one
# command. It covers a WebSocket frame replayed by a reconnect and a double-tap
# on a phone button; it is far shorter than a human re-asking the same thing.
DEDUPE_WINDOW = 2.5

DEFAULT_TTL = 900.0
DEFAULT_HISTORY = 500


@dataclass
class RemoteCommand:
    request_id: str
    text: str
    source: str = 'remote'
    trust: str = ''
    scope: str = field(default_factory=lambda: uuid.uuid4().hex)
    status: str = SUBMITTED
    error: str = ''
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def envelope(self) -> dict:
        from core import mobile_protocol as protocol
        return protocol.envelope('command.status', {
            'request_id': protocol.clip(self.request_id, 120),
            'status': self.status,
            'text': protocol.clip(self.text, protocol.LIMITS['text']),
            'error': protocol.clip(self.error, protocol.LIMITS['detail']),
        }, timestamp=self.updated_at)


class RemoteCommandGate:
    def __init__(self, *, ttl: float = DEFAULT_TTL, history: int = DEFAULT_HISTORY,
                 dedupe_window: float = DEDUPE_WINDOW, clock=time.time) -> None:
        self._lock = threading.RLock()
        self._commands: dict[str, RemoteCommand] = {}
        self._order: list[str] = []
        self.ttl = float(ttl)
        self.history = int(history)
        self.dedupe_window = float(dedupe_window)
        self._clock = clock
        self.duplicates = 0
        self.accepted = 0

    # ── intake ────────────────────────────────────────────────────────────────

    def submit(self, text: str, *, request_id: str = '', source: str = 'remote',
               trust: str = '') -> tuple[RemoteCommand | None, str]:
        """Register a command. Returns (command, 'accepted' | 'duplicate' | 'rejected').

        `command` is the existing record when the outcome is `duplicate`, so the
        caller can reply on the original request's channel instead of starting new
        work.
        """
        body = (text or '').strip()
        if not body:
            return None, 'rejected'
        request_id = (request_id or '').strip()[:120]
        now = self._clock()
        with self._lock:
            self._prune(now)
            if request_id:
                existing = self._commands.get(request_id)
                if existing is not None:
                    self.duplicates += 1
                    return existing, 'duplicate'
            else:
                twin = self._recent_duplicate(body, source, now)
                if twin is not None:
                    self.duplicates += 1
                    return twin, 'duplicate'
                request_id = uuid.uuid4().hex
            command = RemoteCommand(request_id=request_id, text=body, source=source,
                                    trust=trust, created_at=now, updated_at=now)
            self._commands[request_id] = command
            self._order.append(request_id)
            self.accepted += 1
            self._prune(now)          # the cap holds even right after an insert
            return command, 'accepted'

    def _recent_duplicate(self, text: str, source: str, now: float) -> RemoteCommand | None:
        for request_id in reversed(self._order):
            command = self._commands.get(request_id)
            if command is None:
                continue
            if now - command.created_at > self.dedupe_window:
                break
            if command.text == text and command.source == source:
                return command
        return None

    # ── lifecycle ─────────────────────────────────────────────────────────────

    def begin(self, request_id: str) -> RemoteCommand | None:
        return self._update(request_id, EXECUTING)

    def acknowledge(self, request_id: str) -> RemoteCommand | None:
        return self._update(request_id, ACKNOWLEDGED)

    def complete(self, request_id: str, *, ok: bool = True, error: str = '') -> RemoteCommand | None:
        return self._update(request_id, COMPLETED if ok else FAILED, error=error)

    def _update(self, request_id: str, status: str, *, error: str = '') -> RemoteCommand | None:
        with self._lock:
            command = self._commands.get((request_id or '').strip())
            if command is None:
                return None
            command.status = status
            if error:
                command.error = str(error)[:1200]
            command.updated_at = self._clock()
            return command

    def get(self, request_id: str) -> RemoteCommand | None:
        with self._lock:
            return self._commands.get((request_id or '').strip())

    # ── housekeeping ─────────────────────────────────────────────────────────

    def _prune(self, now: float) -> None:
        """Forget expired records, then whatever the history cap pushes out.

        Both loops delete from `_commands` as well: an entry dropped from `_order`
        but left in the map would still answer a duplicate check (and would never
        be evicted, because nothing else knows it exists).
        """
        while self._order:
            command = self._commands.get(self._order[0])
            if command is not None and now - command.created_at < self.ttl:
                break
            self._commands.pop(self._order.pop(0), None)
        while len(self._order) > self.history:
            self._commands.pop(self._order.pop(0), None)

    def stats(self) -> dict:
        with self._lock:
            return {'accepted': self.accepted, 'duplicates': self.duplicates,
                    'tracked': len(self._commands)}


_gate: RemoteCommandGate | None = None
_gate_lock = threading.Lock()


def get_gate() -> RemoteCommandGate:
    global _gate
    with _gate_lock:
        if _gate is None:
            _gate = RemoteCommandGate()
        return _gate
