"""Bounded isolated reply worker, serialized per chat, with takeover rechecks."""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
import threading
from core.event_bus import bus
from core.execution_policy import trust_context, TRUST_EXTERNAL_MESSAGE
from services.whatsapp.importance import classify
from services.whatsapp.policy import generate_reply, may_reply


class ReplyWorker:
    def __init__(self, store, adapter, classifier=classify, generator=generate_reply) -> None:
        self.store, self.adapter = store, adapter
        self.classifier, self.generator = classifier, generator
        self.pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix='ZayaWhatsApp')
        self.slots = threading.BoundedSemaphore(50)
        self._locks: dict[str, threading.Lock] = {}
        self._lock = threading.Lock()
        self.closed = False

    def enqueue(self, message) -> None:
        if self.closed or not self.slots.acquire(blocking=False):
            bus.publish('system.warning', summary='WhatsApp worker queue full; message remains in the inbox for review.')
            return
        def run():
            try:
                self.process(message)
            finally:
                self.slots.release()
        self.pool.submit(run)

    def close(self) -> None:
        self.closed = True
        self.pool.shutdown(wait=False, cancel_futures=True)

    def process(self, message) -> None:
        token = trust_context.set(TRUST_EXTERNAL_MESSAGE)
        try:
            with self._lock:
                lock = self._locks.setdefault(message.chat_id, threading.Lock())
            with lock:
                self._process(message)
        finally:
            trust_context.reset(token)

    def _process(self, message) -> None:
        if self.closed or message.direction != 'incoming':
            return
        history = list(reversed(self.store.conversation(message.chat_id, 20)))
        try:
            importance = self.classifier(message, history)
            if not isinstance(importance, dict):
                raise ValueError('Importance classifier returned an invalid result.')
            score = max(0, min(100, int(importance.get('score', 40))))
            relay = importance.get('notify_owner') is True
            if score >= 40 or importance.get('needs_owner') or relay:
                if self.store.alert(message, score, str(importance.get('category', 'normal')), str(importance.get('reason', 'Owner review needed.'))[:300], notify_owner=relay):
                    bus.publish('whatsapp.alert.created', chat_id=message.chat_id, message_id=message.message_id, score=score)
            state = self.store.chat(message.chat_id)
            if state['mode'] not in {'draft', 'auto'} or not message.complete or message.source == 'hermes_hook':
                return
            if state['mode'] == 'auto' and not may_reply(message, state['mode'], importance):
                return
            if not self.store.claim_message(message.message_id):
                return
            reply_context = history
            if relay:
                reply_context = history + [{'direction': 'system', 'text': 'Owner voice notification queued; delivery pending.', 'owner_relay_queued': True}]
            generated = self.generator(message, reply_context)
            reply = str(generated.get('reply', '')).strip()
            if generated.get('needs_owner') is not False or not reply:
                self.store.alert(message, max(score, 70), 'important', 'Reply requires owner judgment or unavailable facts.')
                bus.publish('whatsapp.alert.created', chat_id=message.chat_id, message_id=message.message_id, score=max(score, 70))
                return
            reply = 'Zaya · Sajan Rai’s AI assistant:\n' + reply
            self.store.save_draft(message.message_id, reply)
            # Owner may pause or reply while the model is generating. Re-read
            # authoritative mode immediately before any transport side effect.
            latest = self.store.chat(message.chat_id)
            if self.closed or latest['mode'] != 'auto' or latest['last_manual_owner_message_at'] != state['last_manual_owner_message_at']:
                return
            result = self.adapter.send(message.chat_id, reply, 'reply-' + message.message_id, message.message_id)
            bus.publish('whatsapp.message.sent' if result.status == 'success' else 'tool.failed',
                        tool='whatsapp', chat_id=message.chat_id, message_id=message.message_id, result=result.to_dict())
        except Exception as error:
            # No privileged fallback or screen typing. Keep the incoming record.
            from core.audit import redact
            self.store.alert(message, 70, 'important', f'Reply worker failed: {redact(str(error))[:200]}')
            bus.publish('whatsapp.alert.created', chat_id=message.chat_id, message_id=message.message_id, score=70)
