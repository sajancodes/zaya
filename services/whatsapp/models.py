from __future__ import annotations
from dataclasses import dataclass
import hashlib
import json
import re
import time


def validate_chat_id(value: str) -> str:
    if not re.fullmatch(r'[0-9A-Za-z_.+-]{1,100}@(s\.whatsapp\.net|g\.us|lid)', value):
        raise ValueError('An exact WhatsApp chat JID is required; resolve names from the inbox first.')
    return value


@dataclass(frozen=True)
class Message:
    message_id: str
    chat_id: str
    sender_id: str
    text: str
    timestamp: float
    direction: str = 'incoming'
    source: str = 'hermes_hook'
    display_name: str = ''
    ai_generated: bool = False
    reply_to_id: str | None = None
    transport_status: str = 'received'
    complete: bool = True
    chat_aliases: tuple[str, ...] = ()

    def __post_init__(self):
        validate_chat_id(self.chat_id)
        if self.direction not in {'incoming', 'outgoing'}:
            raise ValueError('Invalid message direction.')
        if not self.message_id or len(self.message_id) > 256 or len(self.text) > 100000:
            raise ValueError('Invalid or oversized message.')


def normalize_hook(event: str, context: dict) -> Message | None:
    if context.get('platform') != 'whatsapp' or event not in {'agent:start', 'agent:end'}:
        return None
    outgoing = event == 'agent:end'
    text = str(context.get('response') if outgoing else context.get('message') or '')
    if not text or text == 'None':
        return None
    # Installed Hermes hooks expose only 500 inbound characters and no raw ID.
    # Session + content dedup is deliberately conservative and never authorizes auto replies.
    fingerprint = hashlib.sha256(json.dumps([event, context.get('session_id'), context.get('chat_id'), context.get('user_id'), text], ensure_ascii=False).encode()).hexdigest()
    return Message('hook-' + fingerprint, str(context.get('chat_id', '')), str(context.get('user_id', '')),
                   text, float(context.get('timestamp') or time.time()), 'outgoing' if outgoing else 'incoming',
                   'hermes_hook', str(context.get('display_name', '')), outgoing, complete=False)
