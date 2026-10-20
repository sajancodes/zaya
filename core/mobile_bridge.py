"""Bridge between Zaya's runtime event bus and remote phone interfaces.

One Zaya, several bodies. This module is the single place where the laptop's
internal events become the stable mobile protocol, and where Zaya's own audio is
handed to a remote speaker instead of — or as well as — the laptop's.

Two rules shape the implementation:

  * Nothing here may slow the local session down. Every remote consumer gets a
    bounded queue that drops the oldest frame when it cannot keep up, and every
    sink call is isolated, so a disconnected phone costs Zaya nothing but a
    dropped counter.
  * The laptop stays authoritative. State, emotion, captions, tasks and call
    priorities are decided by the runtime; a phone can ask for things, never
    assert them.
"""
from __future__ import annotations

import logging
import threading
import time
from collections import deque
import uuid

from core.event_bus import bus
from core import mobile_protocol as protocol

log = logging.getLogger(__name__)


def safe(value, limit: int = 200) -> str:
    """Best-effort, never-raising rendering of a value for a log line."""
    try:
        text = value if isinstance(value, str) else repr(value)
    except Exception:
        return '<unprintable>'
    return text[:limit]


# ~5 seconds of 24 kHz PCM16 mono. Two bounds, because frames are not a fixed
# size: the session loop writes batches of up to 9600 bytes (200 ms each), while
# a browser or a test may push 2048-byte chunks. The byte budget is what actually
# caps the latency tail — a count-only queue would let a slow phone accumulate
# 20 seconds of Zaya's voice and then play it back after the moment has passed.
AUDIO_QUEUE_SECONDS = 5.0
AUDIO_QUEUE_BYTES = int(AUDIO_QUEUE_SECONDS * 24000 * 2)      # 240 000
AUDIO_QUEUE_FRAMES = 100

TARGETS = ('desktop', 'phone', 'both')


class AudioListener:
    """One remote speaker. Frames are pushed from the session loop, drained by
    the connection task. Drop-oldest on a bounded deque is the whole back-pressure
    story: a phone that stops reading loses old frames instead of stalling Zaya."""

    def __init__(self, name: str = '', maxlen: int = AUDIO_QUEUE_FRAMES,
                 max_bytes: int = AUDIO_QUEUE_BYTES) -> None:
        self.name = name
        self._frames: deque[bytes] = deque(maxlen=max(1, int(maxlen)))
        self._max_bytes = max(1, int(max_bytes))
        self._bytes = 0
        self._lock = threading.Lock()
        self._event = None
        self._loop = None
        self.dropped = 0
        self.delivered = 0
        self.closed = False

    def bind(self, loop, event) -> None:
        self._loop, self._event = loop, event

    def push(self, frame: bytes) -> None:
        if self.closed or not frame:
            return
        dropped = 0
        with self._lock:
            if self.closed:
                return
            if len(frame) > self._max_bytes:
                self.dropped += 1
                return  # Never let even one frame exceed the audio latency budget.
            if len(self._frames) >= self._frames.maxlen:      # this append evicts
                # Account for the oldest entry BEFORE deque.append evicts it.
                self._bytes -= len(self._frames[0])
                dropped += 1
            self._frames.append(frame)
            self._bytes += len(frame)
            while self._bytes > self._max_bytes and len(self._frames) > 1:
                self._bytes -= len(self._frames.popleft())
                dropped += 1
            self.dropped += dropped
        loop, event = self._loop, self._event
        if loop is None or event is None:
            return
        try:
            loop.call_soon_threadsafe(event.set)
        except RuntimeError:
            # The consumer's loop is gone. The frames simply age out.
            self.closed = True

    def drain(self) -> list[bytes]:
        with self._lock:
            frames = list(self._frames)
            self._frames.clear()
            self._bytes = 0
        self.delivered += len(frames)
        return frames

    def pending(self) -> int:
        with self._lock:
            return len(self._frames)

    def pending_bytes(self) -> int:
        with self._lock:
            return self._bytes

    def close(self) -> None:
        self.closed = True
        with self._lock:
            self._frames.clear()
            self._bytes = 0


class MobileBridge:
    def __init__(self, clock=time.time) -> None:
        self._clock = clock
        self._lock = threading.RLock()
        self._sinks: dict[int, tuple[str, object]] = {}
        self._next_sink = 1
        self._listeners: dict[int, tuple[str, AudioListener]] = {}
        self._next_listener = 1

        self._state = protocol.STANDBY
        self._emotion = 'neutral'
        self._caption = ''
        self._output_target = 'desktop'
        self._pre_call_target = 'desktop'
        self._call_active = False
        self._last_caption_at = 0.0

        self.sink_failures = 0
        self.last_failure = ''
        self._unsubscribe = None
        self._pending_requests: dict[str, tuple[threading.Event, dict]] = {}

    # ── request/response correlation ──────────────────────────────────────────

    def register_response(self, request_id: str, data: dict) -> bool:
        with self._lock:
            entry = self._pending_requests.get(request_id)
        if entry:
            event, result_slot = entry
            result_slot.update(data)
            event.set()
            return True
        return False

    def dispatch_phone_action(self, action: str, params: dict | None = None, timeout_sec: float = 12.0) -> dict:
        if self.sink_count() == 0:
            return {"status": "failed", "error": "No companion phone connected. Ensure Zaya Companion is running and paired."}

        req_id = f"act_{uuid.uuid4().hex[:10]}"
        event = threading.Event()
        result_slot: dict[str, Any] = {}

        with self._lock:
            self._pending_requests[req_id] = (event, result_slot)

        try:
            self.emit(protocol.envelope("action.request", {
                "request_id": req_id,
                "action": action,
                "params": params or {}
            }))
            signaled = event.wait(timeout=max(1.0, timeout_sec))
            if not signaled:
                return {"status": "failed", "error": f"Phone action '{action}' timed out after {timeout_sec}s.", "request_id": req_id}
            return result_slot
        finally:
            with self._lock:
                self._pending_requests.pop(req_id, None)

    def dispatch_screen_capture(self, prompt: str = "", timeout_sec: float = 15.0) -> dict:
        if self.sink_count() == 0:
            return {"status": "failed", "error": "No companion phone connected. Ensure Zaya Companion is running and paired."}

        req_id = f"scr_{uuid.uuid4().hex[:10]}"
        event = threading.Event()
        result_slot: dict[str, Any] = {}

        with self._lock:
            self._pending_requests[req_id] = (event, result_slot)

        try:
            self.emit(protocol.envelope("screen.frame", {
                "request_id": req_id,
                "prompt": prompt,
                "action": "capture",
            }))
            signaled = event.wait(timeout=max(1.0, timeout_sec))
            if not signaled:
                return {"status": "failed", "error": f"Screen capture timed out after {timeout_sec}s.", "request_id": req_id}
            return result_slot
        finally:
            with self._lock:
                self._pending_requests.pop(req_id, None)

    # ── lifecycle ─────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Subscribe to the runtime event bus. Idempotent."""
        with self._lock:
            if self._unsubscribe is not None:
                return
            self._unsubscribe = bus.subscribe('*', self.handle_event)

    def stop(self) -> None:
        with self._lock:
            unsubscribe, self._unsubscribe = self._unsubscribe, None
        if unsubscribe is not None:
            try:
                unsubscribe()
            except Exception:
                log.debug('bridge unsubscribe failed', exc_info=True)

    # ── sinks (WebSocket connections, tests, future transports) ───────────────

    def add_sink(self, sink, name: str = '') -> object:
        with self._lock:
            token = self._next_sink
            self._next_sink += 1
            self._sinks[token] = (name or f'sink-{token}', sink)

        def detach() -> None:
            with self._lock:
                self._sinks.pop(token, None)

        return detach

    def sink_count(self) -> int:
        with self._lock:
            return len(self._sinks)

    def emit(self, envelope: dict) -> int:
        """Send one envelope to every sink. Returns how many accepted it."""
        with self._lock:
            sinks = list(self._sinks.values())
        delivered = 0
        for name, sink in sinks:
            try:
                sink(envelope)
                delivered += 1
            except Exception as error:            # isolation: one phone cannot
                self._note_failure(name, error)   # break the others or Zaya
        return delivered

    def _note_failure(self, name: str, error: Exception) -> None:
        self.sink_failures += 1
        self.last_failure = f'{name}: {type(error).__name__}: {error}'[:300]
        if self.sink_failures <= 5 or self.sink_failures % 100 == 0:
            log.warning('Mobile sink failed (%s total): %s', self.sink_failures, self.last_failure)

    def broadcast(self, type_: str, payload: dict | None = None) -> int:
        return self.emit(protocol.envelope(type_, payload))

    # ── authoritative state ───────────────────────────────────────────────────

    @property
    def state(self) -> str:
        return self._state

    @property
    def emotion(self) -> str:
        return self._emotion

    @property
    def caption_text(self) -> str:
        return self._caption

    def set_state(self, raw_state, *, announce: bool = True) -> str:
        """Record the laptop's visual state and tell every remote body."""
        state = protocol.normalize_state(raw_state)
        with self._lock:
            changed = state != self._state
            self._state = state
            emotion = self._emotion
        if changed and announce:
            self.emit(protocol.state_envelope(state, emotion))
        return state

    def set_emotion(self, raw_emotion, *, announce: bool = True) -> str:
        """Emotion is chosen by the laptop (Gemini + avatar_expression), never by
        the phone. A change republishes the full state so a remote body always
        renders one coherent answer."""
        emotion = protocol.normalize_emotion(raw_emotion)
        with self._lock:
            changed = emotion != self._emotion
            self._emotion = emotion
            state = self._state
        if changed and announce:
            self.emit(protocol.state_envelope(state, emotion))
        return emotion

    def caption(self, text: str) -> None:
        text = protocol.clip(text, protocol.LIMITS['caption'])
        if not text:
            return
        with self._lock:
            if text == self._caption:
                return
            self._caption = text
            self._last_caption_at = self._clock()
        self.emit(protocol.envelope('zaya.caption', {'text': text, 'final': False}))

    def clear_caption(self) -> None:
        with self._lock:
            self._caption = ''

    # ── output routing ────────────────────────────────────────────────────────

    @property
    def output_target(self) -> str:
        return self._output_target

    def set_output_target(self, target: str) -> str:
        name = str(target or '').strip().lower()
        if name not in TARGETS:
            raise ValueError(f'Unknown output target: {target!r}')
        with self._lock:
            if self._call_active:
                return 'phone'  # In-call speaker selection is a phone hardware route.
            self._output_target = name
            if not self._call_active:
                self._pre_call_target = name
            call_active = self._call_active
        self.emit(protocol.envelope('system.output', {
            'target': name,
            'desktop': self.desktop_enabled(),
            'phone': self.phone_enabled(),
            'call_active': call_active,
        }))
        return name

    @property
    def call_active(self):
        with self._lock:
            return self._call_active

    def set_call_active(self, active: bool) -> None:
        """While a phone call is running, Zaya's voice belongs on the phone."""
        active = bool(active)
        with self._lock:
            if active == self._call_active:
                return
            self._call_active = active
            if active:
                self._pre_call_target = self._output_target
                self._output_target = 'phone'
            else:
                self._output_target = self._pre_call_target or 'desktop'
            target = self._output_target
        self.emit(protocol.envelope('system.output', {
            'target': target,
            'desktop': self.desktop_enabled(),
            'phone': self.phone_enabled(),
            'call_active': active,
        }))

    def desktop_enabled(self) -> bool:
        return self._output_target in ('desktop', 'both')

    def phone_enabled(self) -> bool:
        return self._output_target in ('phone', 'both')

    # ── outbound audio ───────────────────────────────────────────────────────

    def add_audio_listener(self, name: str = '', maxlen: int = AUDIO_QUEUE_FRAMES,
                           max_bytes: int = AUDIO_QUEUE_BYTES) -> AudioListener:
        listener = AudioListener(name=name, maxlen=maxlen, max_bytes=max_bytes)
        with self._lock:
            token = self._next_listener
            self._next_listener += 1
            self._listeners[token] = (name or f'listener-{token}', listener)

        def detach() -> None:
            with self._lock:
                entry = self._listeners.pop(token, None)
            if entry:
                entry[1].close()

        listener.detach = detach          # type: ignore[attr-defined]
        return listener

    def remove_audio_listener(self, listener: AudioListener) -> None:
        detach = getattr(listener, 'detach', None)
        if callable(detach):
            detach()
        else:
            listener.close()

    def audio_listener_count(self) -> int:
        with self._lock:
            return len(self._listeners)

    def push_output_audio(self, data: bytes) -> int:
        """Fan one PCM16 frame out to remote speakers. Never blocks, never raises.

        Called from the same task that feeds the local speakers, so a wedged
        socket must not be able to introduce latency into Zaya's own voice.
        """
        if not data or not self.phone_enabled():
            return 0
        with self._lock:
            listeners = [entry[1] for entry in self._listeners.values()]
        for listener in listeners:
            try:
                listener.push(data)
            except Exception:
                log.debug('audio listener push failed', exc_info=True)
        return len(listeners)

    # ── snapshot for a freshly connected phone ───────────────────────────────

    def snapshot(self) -> dict:
        with self._lock:
            return {
                'state': self._state,
                'emotion': self._emotion,
                'caption': protocol.clip(self._caption, protocol.LIMITS['caption']),
                'output_target': self._output_target,
                'call_active': self._call_active,
            }

    # ── bus translation ──────────────────────────────────────────────────────

    def handle_event(self, event: dict) -> None:
        """Translate a bus event. Must never raise — the bus logs and continues,
        but a silent failure here would mean a phone that stops updating."""
        if not isinstance(event, dict):
            return
        try:
            name = str(event.get('event') or '')
            if name == 'zaya.state.changed':
                self.set_state(event.get('state'))
                return
            if name == 'avatar.emotion':
                self.set_emotion(event.get('emotion'))
                return
            if name == 'avatar.caption':
                self.caption(event.get('text', ''))
                return
            for envelope in protocol.normalize_event(event):
                self.emit(envelope)
        except Exception:
            # The log call must be as safe as the code it reports on: a hostile
            # payload must not be able to raise from inside this handler.
            log.exception('Mobile bridge could not translate %r', safe(event))


_bridge: MobileBridge | None = None
_bridge_lock = threading.Lock()


def get_bridge() -> MobileBridge:
    """Process-wide bridge. Created lazily so actions and tests can import it
    without a running Qt application."""
    global _bridge
    with _bridge_lock:
        if _bridge is None:
            _bridge = MobileBridge()
            _bridge.start()
        return _bridge


def reset_bridge() -> None:
    """Test helper: drop the singleton so a fresh bridge is built."""
    global _bridge
    with _bridge_lock:
        if _bridge is not None:
            _bridge.stop()
        _bridge = None
