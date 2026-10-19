"""Bounded isolated reply worker, serialized per chat, with takeover rechecks."""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import threading
import time
from core.event_bus import bus
from core.execution_policy import trust_context, TRUST_EXTERNAL_MESSAGE
from services.whatsapp.importance import classify
from services.whatsapp.policy import generate_reply, may_reply


class ReplyWorker:
    def __init__(self, store, adapter, classifier=classify, generator=generate_reply, *, quiet_seconds=1.5) -> None:
        self.store, self.adapter = store, adapter
        self.classifier, self.generator = classifier, generator
        self.pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix='ZayaWhatsApp')
        self.slots = threading.BoundedSemaphore(50)
        self._locks: dict[str, threading.Lock] = {}
        self._lock = threading.Lock()
        self._condition = threading.Condition()
        self._pending: dict[str, dict] = {}
        self.quiet_seconds = quiet_seconds
        self.closed = False

    def enqueue(self, message) -> None:
        chat_id = self.store.canonical_chat(message.chat_id)
        with self._condition:
            if self.closed:
                return
            pending = self._pending.get(chat_id)
            if pending is None:
                if not self.slots.acquire(blocking=False):
                    bus.publish('system.warning', summary='WhatsApp worker queue full; message remains in the inbox for review.')
                    return
                pending = self._pending[chat_id] = {'messages': {}, 'updated': time.monotonic(), 'in_flight': 0}
                self.pool.submit(self._drain, chat_id)
            if len(pending['messages']) + pending['in_flight'] >= 50:
                bus.publish('system.warning', summary='WhatsApp chat burst full; excess messages remain in the inbox for review.')
                return
            pending['messages'][message.message_id] = message
            pending['updated'] = time.monotonic()
            self._condition.notify_all()

    def _drain(self, chat_id) -> None:
        try:
            while True:
                with self._condition:
                    pending = self._pending[chat_id]
                    deadline = time.monotonic() + 8
                    while not self.closed:
                        delay = min(pending['updated'] + self.quiet_seconds, deadline) - time.monotonic()
                        if delay <= 0:
                            break
                        self._condition.wait(delay)
                    if self.closed:
                        return
                    messages = list(pending['messages'].values())
                    pending['messages'].clear()
                    pending['in_flight'] = len(messages)
                fresh = self._process_messages(messages)
                with self._condition:
                    # A new message arrived during generation. Reconsider the
                    # whole burst instead of sending an already stale answer.
                    if not fresh:
                        pending['messages'] = {**{m.message_id: m for m in messages}, **pending['messages']}
                    pending['in_flight'] = 0
                    if not pending['messages']:
                        del self._pending[chat_id]
                        self._condition.notify_all()
                        return
        finally:
            self.slots.release()

    def close(self) -> None:
        with self._condition:
            self.closed = True
            self._condition.notify_all()
        self.pool.shutdown(wait=False, cancel_futures=True)

    def process(self, message) -> None:
        self._process_messages([message])

    def _process_messages(self, messages) -> bool:
        if not messages:
            return True
        chat_id = self.store.canonical_chat(messages[0].chat_id)
        messages = [replace(message, chat_id=chat_id) for message in messages]
        token = trust_context.set(TRUST_EXTERNAL_MESSAGE)
        try:
            with self._lock:
                lock = self._locks.setdefault(chat_id, threading.Lock())
            with lock:
                return self._process(messages)
        finally:
            trust_context.reset(token)

    def _process(self, messages) -> bool:
        messages = [m for m in messages if m.direction == 'incoming' and self.store.rows(
            'SELECT message_id FROM wa_messages WHERE message_id=? AND handled=0', (m.message_id,))]
        if self.closed or not messages:
            return True
        message = messages[-1]
        try:
            watermark = self._incoming_version(message.chat_id)
            history = list(reversed(self.store.conversation(message.chat_id, 60)))
            visible_ids = {row['message_id'] for row in history}
            state = self.store.chat(message.chat_id)
            eligible, relay, score = [], False, 0
            for incoming in messages:
                importance = self.classifier(incoming, history)
                if not isinstance(importance, dict):
                    raise ValueError('Importance classifier returned an invalid result.')
                incoming_score = max(0, min(100, int(importance.get('score', 40))))
                notify = importance.get('notify_owner') is True
                if incoming_score >= 40 or importance.get('needs_owner') or notify:
                    if self.store.alert(incoming, incoming_score, str(importance.get('category', 'normal')), str(importance.get('reason', 'Owner review needed.'))[:300], notify_owner=notify):
                        # Alert details travel with the event so the phone can
                        # show who wrote and why it mattered — without the phone
                        # ever classifying anything itself.
                        alert = self.store.rows(
                            'SELECT alert_id FROM wa_alerts WHERE message_id=?',
                            (incoming.message_id,))
                        bus.publish('whatsapp.alert.created', chat_id=incoming.chat_id,
                                    message_id=incoming.message_id, score=incoming_score,
                                    alert_id=(alert[0]['alert_id'] if alert else incoming.message_id),
                                    title=self.store.chat(incoming.chat_id).get('title') or 'WhatsApp',
                                    category=str(importance.get('category', 'normal')),
                                    reason=str(importance.get('reason', ''))[:300],
                                    needs_owner=bool(importance.get('needs_owner')))
                if (incoming.message_id in visible_ids and state['mode'] in {'draft', 'auto'} and incoming.complete and incoming.source != 'hermes_hook'
                        and (state['mode'] == 'draft' or may_reply(incoming, state['mode'], importance))):
                    eligible.append(incoming)
                    relay = relay or notify
                    score = max(score, incoming_score)
            if not eligible:
                return True
            message = eligible[-1]
            pending_ids = {m.message_id for m in eligible}
            held_ids = {m.message_id for m in messages} - pending_ids
            reply_context = [dict(row, pending_reply=row['message_id'] in pending_ids) for row in history]
            if relay:
                reply_context += [{'direction': 'system', 'text': 'Owner voice notification queued; delivery pending.', 'owner_relay_queued': True}]
            generated = self.generator(message, reply_context)
            latest = self.store.chat(message.chat_id)
            if (self.closed or latest['mode'] != state['mode'] or latest['started_at'] != state['started_at']
                    or latest['last_manual_owner_message_at'] != state['last_manual_owner_message_at']):
                return True
            if self._incoming_version(message.chat_id) != watermark:
                return False
            for incoming in eligible:
                if not self.store.claim_message(incoming.message_id):
                    return True
            reply = str(generated.get('reply', '')).strip()
            if generated.get('needs_owner') is not False:
                self.store.alert(message, max(score, 70), 'important', 'Reply requires owner judgment or unavailable facts.')
                bus.publish('whatsapp.alert.created', chat_id=message.chat_id, message_id=message.message_id, score=max(score, 70))
                return True
            # Silence is a deliberate conversational outcome, not a failure.
            if generated.get('should_reply') is False or not reply:
                return True
            reply_to = generated.get('reply_to_id')
            if reply_to == '':
                reply_to = None
            valid_targets = {row['message_id'] for row in history if row['direction'] == 'incoming'
                             and row['complete'] and row['source'] != 'hermes_hook' and row['message_id'] not in held_ids}
            if reply_to is not None and (not isinstance(reply_to, str) or reply_to not in valid_targets):
                raise ValueError('Reply target must be an incoming message in this chat context.')
            reply = 'Zaya · Sajan Rai’s AI assistant:\n' + reply
            self.store.save_draft(message.message_id, reply)
            # Owner may pause or reply while the model is generating. Re-read
            # authoritative mode immediately before any transport side effect.
            latest = self.store.chat(message.chat_id)
            if self.closed or latest['mode'] != 'auto' or latest['last_manual_owner_message_at'] != state['last_manual_owner_message_at']:
                return True
            result = self.adapter.send(message.chat_id, reply, 'reply-' + message.message_id, reply_to)
            bus.publish('whatsapp.message.sent' if result.status == 'success' else 'tool.failed',
                        tool='whatsapp', chat_id=message.chat_id, message_id=message.message_id, result=result.to_dict())
        except Exception as error:
            # No privileged fallback or screen typing. Keep the incoming record.
            from core.audit import redact
            self.store.alert(message, 70, 'important', f'Reply worker failed: {redact(str(error))[:200]}')
            bus.publish('whatsapp.alert.created', chat_id=message.chat_id, message_id=message.message_id, score=70)
        return True

    def _incoming_version(self, chat_id):
        return self.store.rows("SELECT MAX(rowid) AS version FROM wa_messages WHERE chat_id=? AND direction='incoming'",
                               (chat_id,))[0]['version']
