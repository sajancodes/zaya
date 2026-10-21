"""Stable JSON contract between the laptop runtime and the Android companion.

The phone is a body, never a second assistant. Everything it renders is produced
by the running laptop runtime and translated into the envelopes defined here, so
the Android app never has to understand an internal Python object.

Wire shape (protocol_version 1):

    {
      "protocol_version": 1,
      "type": "zaya.state",
      "timestamp": 1712345678.123,
      "payload": {"state": "SPEAKING", "emotion": "happy"}
    }

`payload` is always an object. Unknown `type` values are ignored by clients, which
is what lets the laptop add events without shipping a new APK.
"""
from __future__ import annotations

import time

PROTOCOL_VERSION = 1

# ── canonical visual states ───────────────────────────────────────────────────
# The laptop is the only authority on state. Android renders exactly what the
# laptop sends; it never derives a state of its own.

STANDBY = 'STANDBY'
LISTENING = 'LISTENING'
THINKING = 'THINKING'
SPEAKING = 'SPEAKING'
SLEEPING = 'SLEEPING'
TASK_RUNNING = 'TASK_RUNNING'
ERROR = 'ERROR'
MUTED = 'MUTED'
CONNECTING = 'CONNECTING'

STATES = (STANDBY, LISTENING, THINKING, SPEAKING, SLEEPING, TASK_RUNNING, ERROR, MUTED, CONNECTING)

# Internal HUD states that are not part of the public set. TASK_* collapses into
# one visible state: the task list carries the detail, the face does not.
STATE_ALIASES = {
    'TASK': TASK_RUNNING,
    'TASK_STARTED': TASK_RUNNING,
    'IDLE': STANDBY,
    'READY': STANDBY,
    'WAITING': LISTENING,
    'OFFLINE': ERROR,
    'DISCONNECTED': ERROR,
}

EMOTIONS = ('neutral', 'happy', 'sad', 'angry', 'surprised')

# ── call priorities ───────────────────────────────────────────────────────────
# The laptop decides the priority; Android only renders the result.

P0_CRITICAL = 0
P1_IMMEDIATE = 1
P2_IMPORTANT = 2
P3_NORMAL = 3
PRIORITIES = (P0_CRITICAL, P1_IMMEDIATE, P2_IMPORTANT, P3_NORMAL)
PRIORITY_NAMES = {
    P0_CRITICAL: 'critical',
    P1_IMMEDIATE: 'immediate',
    P2_IMPORTANT: 'important',
    P3_NORMAL: 'normal',
}

# P0/P1 may ring the phone; P2 is a notification; P3 is quiet activity.
CALL_PRIORITIES = (P0_CRITICAL, P1_IMMEDIATE)
NOTIFY_PRIORITIES = (P0_CRITICAL, P1_IMMEDIATE, P2_IMPORTANT)

# ── bounds ────────────────────────────────────────────────────────────────────
# Every field that crosses the wire from runtime data is clipped here rather than
# trusted, so one long task goal cannot become a megabyte WebSocket frame.

LIMITS = {
    'text': 4000,
    'caption': 600,
    'title': 160,
    'detail': 1200,
    'reference': 200,
}

MAX_FRAME_BYTES = 256 * 1024


def priority_name(priority: int) -> str:
    try:
        return PRIORITY_NAMES.get(int(priority), 'normal')
    except (TypeError, ValueError):
        return 'normal'


def clip(value, limit: int, *, default: str = '') -> str:
    """Return a bounded, control-character-free string safe for the wire."""
    if value is None:
        return default
    text = value if isinstance(value, str) else str(value)
    text = ''.join(ch for ch in text if ch == '\n' or ch == '\t' or ord(ch) >= 32)
    text = text.strip()
    return text[:limit]


def normalize_state(raw) -> str:
    """Map any internal state string onto the public state set."""
    name = str(raw or '').strip().upper().replace('-', '_').replace(' ', '_')
    if not name:
        return STANDBY
    if name in STATES:
        return name
    if name.startswith('TASK'):
        return TASK_RUNNING
    return STATE_ALIASES.get(name, STANDBY)


def normalize_emotion(raw, *, default: str = 'neutral') -> str:
    name = str(raw or '').strip().lower()
    return name if name in EMOTIONS else default


def envelope(type_: str, payload: dict | None = None, *, timestamp: float | None = None) -> dict:
    return {
        'protocol_version': PROTOCOL_VERSION,
        'type': str(type_),
        'timestamp': float(timestamp if timestamp is not None else time.time()),
        'payload': payload if isinstance(payload, dict) else {},
    }


def state_envelope(state, emotion) -> dict:
    """The single authoritative 'who Zaya is right now' message."""
    return envelope('zaya.state', {
        'state': normalize_state(state),
        'emotion': normalize_emotion(emotion),
    })


def normalize_task(task) -> dict:
    """A bounded projection of a runtime task, shaped for a phone screen."""
    task = task if isinstance(task, dict) else {}
    return {
        'task_id': clip(task.get('id') or task.get('task_id'), LIMITS['reference']),
        'goal': clip(task.get('goal'), LIMITS['title']),
        'state': clip(task.get('state'), 40),
        'source': clip(task.get('source'), 40),
        'active_step': clip(task.get('active_step'), LIMITS['title']) or None,
        'error': clip(task.get('error'), LIMITS['detail']) or None,
        'attempts': int(task.get('attempts') or 0),
        'created_at': float(task.get('created_at') or 0.0),
        'updated_at': float(task.get('updated_at') or 0.0),
        'evidence_count': len(task.get('evidence') or []) if isinstance(task.get('evidence'), list) else 0,
        'side_effect_count': len(task.get('side_effects') or []) if isinstance(task.get('side_effects'), list) else 0,
    }


TASK_EVENTS = {
    'task.created', 'task.updated', 'task.completed', 'task.failed', 'task.cancelled',
    'task.executing', 'task.verifying', 'task.paused', 'task.waiting_confirmation',
    'task.waiting_external', 'task.inspecting', 'task.planning',
}


def normalize_event(event) -> list[dict]:
    """Translate one internal bus event into zero or more mobile envelopes.

    Returns an empty list for events that carry nothing the phone should show.
    This function is pure: it never touches runtime state and never raises.
    """
    if not isinstance(event, dict):
        return []
    name = str(event.get('event') or '')
    if not name:
        return []
    stamp = event.get('timestamp')

    if name in TASK_EVENTS:
        task = normalize_task(event.get('task') or {})
        if not task['task_id']:
            return []
        kind = name if name in {'task.created', 'task.completed', 'task.failed', 'task.cancelled'} else 'task.updated'
        return [envelope(kind, {'task': task}, timestamp=stamp)]

    if name == 'whatsapp.message.received':
        return [envelope('whatsapp.message.received', {
            'chat_id': clip(event.get('chat_id'), LIMITS['reference']),
            'message_id': clip(event.get('message_id'), LIMITS['reference']),
            'title': clip(event.get('title'), LIMITS['title']),
            'important': bool(event.get('important', False)),
        }, timestamp=stamp)]

    if name == 'whatsapp.alert.created':
        return [envelope('whatsapp.alert.created', {
            'alert_id': clip(event.get('alert_id'), LIMITS['reference']),
            'chat_id': clip(event.get('chat_id'), LIMITS['reference']),
            'title': clip(event.get('title'), LIMITS['title']) or 'WhatsApp',
            'score': int(event.get('score') or 0),
            'category': clip(event.get('category'), 40),
            # Classifier prose is unbounded free text derived from untrusted
            # contact messages: clip it and label it as data on the phone.
            'reason': clip(event.get('reason'), LIMITS['detail']),
        }, timestamp=stamp)]

    if name == 'whatsapp.mode.changed':
        return [envelope('whatsapp.mode', {
            'mode': clip(event.get('mode'), 40),
            'ai_active': bool(event.get('ai_active', False)),
            'feed_ready': bool(event.get('feed_ready', False)),
            'chat_id': clip(event.get('chat_id'), LIMITS['reference']),
            'title': clip(event.get('title'), LIMITS['title']),
        }, timestamp=stamp)]

    if name == 'avatar.caption':
        text = clip(event.get('text'), LIMITS['caption'])
        if not text:
            return []
        return [envelope('zaya.caption', {'text': text, 'final': False}, timestamp=stamp)]

    if name == 'owner.message':
        text = clip(event.get('text'), LIMITS['text'])
        return [envelope('chat.message', {'role': 'user', 'text': text,
                         'request_id': clip(event.get('request_id'), 120),
                         'source': clip(event.get('source'), 40)},
                         timestamp=stamp)] if text else []

    if name in {'zaya.message', 'assistant.message'}:
        text = clip(event.get('text'), LIMITS['text'])
        return [envelope('chat.message', {'role': 'zaya', 'text': text},
                         timestamp=stamp)] if text else []

    if name in {'system.warning', 'system.error'}:
        return [envelope('system.warning', {
            'severity': clip(event.get('severity') or 'high', 20),
            'text': clip(event.get('text'), LIMITS['detail']),
        }, timestamp=stamp)]

    if name == 'audio.duck.changed':
        return [envelope('system.audio', {
            'ducked': bool(event.get('active', False)),
            'voice': bool(event.get('voice', False)),
        }, timestamp=stamp)]

    if name in {'call.incoming', 'call.answered', 'call.ended', 'call.dialing', 'call.missed'}:
        return [envelope(name, {
            'caller_name': clip(event.get('caller_name'), LIMITS['title']),
            'caller_number': clip(event.get('caller_number'), 40),
            'call_id': clip(event.get('call_id'), LIMITS['reference']),
            'priority': int(event.get('priority', P1_IMMEDIATE)),
        }, timestamp=stamp)]

    if name == 'notification.received':
        return [envelope('notification.received', {
            'app': clip(event.get('app') or 'unknown', 40),
            'sender': clip(event.get('sender'), LIMITS['title']),
            'text': clip(event.get('text'), LIMITS['detail']),
            'package': clip(event.get('package'), 100),
        }, timestamp=stamp)]

    if name in {'hardware.control', 'hardware.status'}:
        return [envelope('hardware.status', {
            'target': clip(event.get('target'), 40),
            'state': clip(event.get('state'), 40),
            'battery': int(event.get('battery', 100)),
        }, timestamp=stamp)]

    if name == 'screen.frame':
        return [envelope('screen.frame', {
            'request_id': clip(event.get('request_id'), LIMITS['reference']),
            'width': int(event.get('width', 0)),
            'height': int(event.get('height', 0)),
            'prompt': clip(event.get('prompt'), LIMITS['detail']),
            'jpeg': event.get('jpeg', ''),
        }, timestamp=stamp)]

    if name == 'action.request':
        return [envelope('action.request', {
            'request_id': clip(event.get('request_id'), LIMITS['reference']),
            'action': clip(event.get('action'), 60),
            'params': event.get('params', {}) if isinstance(event.get('params'), dict) else {},
        }, timestamp=stamp)]

    if name == 'action.response':
        return [envelope('action.response', {
            'request_id': clip(event.get('request_id'), LIMITS['reference']),
            'status': clip(event.get('status'), 30),
            'result': event.get('result'),
            'error': clip(event.get('error'), LIMITS['detail']) if event.get('error') else None,
        }, timestamp=stamp)]

    return []


def to_wire_events(event_name_or_dict, payload: dict | None = None) -> list[dict]:
    """Convenience helper to convert event name and payload into wire envelopes."""
    if isinstance(event_name_or_dict, str):
        evt = {'event': event_name_or_dict}
        if isinstance(payload, dict):
            evt.update(payload)
        return normalize_event(evt)
    return normalize_event(event_name_or_dict)
