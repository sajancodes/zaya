"""Own Hermes's supported HTTP bridge without a second AI agent or session.

Only the process spawned here is polled: /messages consumes a queue, so a
Hermes gateway-owned bridge must never be polled by a competing client.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import shutil
import subprocess
import threading
import time
import requests
from core.shell_session import terminate_tree
from services.whatsapp.connection import load_connection
from services.whatsapp.models import Message, validate_chat_id


def normalize_event(event: dict, owner_id: str = '') -> Message:
    chat = validate_chat_id(str(event['chatId']))
    timestamp = event.get('timestamp', time.time())
    if isinstance(timestamp, dict):
        timestamp = timestamp.get('low', time.time())
    owner = bool(event.get('fromOwner') or event.get('readReceiptKey', {}).get('fromMe'))
    peer = str(event.get('senderId', chat))
    aliases = ()
    if chat.endswith('@lid') and peer.endswith('@s.whatsapp.net') and peer != owner_id:
        aliases, chat = (chat,), validate_chat_id(peer)
    sender = owner_id if owner and owner_id else peer
    # Outgoing pushName belongs to the account owner, never the recipient.
    name = '' if owner else str(event.get('senderName') or event.get('chatName') or '')
    return Message(str(event['messageId']), chat, sender,
                   str(event.get('body', '')), float(timestamp), 'outgoing' if owner else 'incoming',
                   'native_bridge', name,
                   ai_generated=False, reply_to_id=event.get('quotedMessageId'), complete=True, chat_aliases=aliases)


class NativeBridge:
    def __init__(self, callback, connection: dict | None = None, port: int = 8768) -> None:
        self.callback = callback
        self.connection = connection or load_connection()
        self.port = port
        self.url = f'http://127.0.0.1:{port}'
        self.http = requests.Session()
        self.http.trust_env = False  # local bridge traffic never goes through a proxy
        self.process = None
        self.ready = False
        self.error: str | None = None
        self.closed = threading.Event()
        self.last_event_at: float | None = None

    def start(self) -> None:
        if not self.connection:
            raise ValueError('Pair WhatsApp before starting its live event feed.')
        home = Path(self.connection['hermes_home'])
        if (home / 'gateway.pid').exists():
            # Never change or stop the user's independently running gateway.
            try:
                import psutil
                pid_data = (home / 'gateway.pid').read_text().strip()
                pid = int(json.loads(pid_data).get('pid')) if pid_data.startswith('{') else int(pid_data)
                if psutil.pid_exists(pid):
                    raise RuntimeError('Hermes gateway is running; Zaya will use observation hooks without opening a second session.')
            except (ValueError, TypeError, KeyError):
                raise RuntimeError('Hermes gateway ownership could not be established; bridge start refused.')
        bridge = home / 'hermes-agent' / 'scripts' / 'whatsapp-bridge' / 'bridge.js'
        if not bridge.is_file():
            candidates = [Path.home() / 'hermes-agent' / 'scripts' / 'whatsapp-bridge' / 'bridge.js']
            bridge = next((p for p in candidates if p.is_file()), bridge)
        node = shutil.which('node')
        if not node or not bridge.is_file() or not (bridge.parent / 'node_modules').is_dir():
            raise RuntimeError('Hermes WhatsApp bridge or its Node dependencies are unavailable.')
        try:
            self.http.get(self.url + '/health', timeout=.5)
        except requests.ConnectionError:
            pass
        else:
            raise RuntimeError('Bridge port already belongs to a process; no competing queue consumer was started.')
        # Process-local policy allows contact observations only. This does not
        # weaken Telegram or change Hermes profile allowlists. Zaya never routes
        # this content to the privileged operator, even owner outgoing text.
        env = dict(os.environ, WHATSAPP_MODE='bot', WHATSAPP_ALLOWED_USERS='*',
                   WHATSAPP_DM_POLICY='open', WHATSAPP_FORWARD_OWNER_MESSAGES='true',
                   WHATSAPP_SEND_READ_RECEIPTS='false', WHATSAPP_REPLY_PREFIX='', HERMES_HOME=str(home))
        options = {'creationflags': subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == 'nt' else {'start_new_session': True}
        self.process = subprocess.Popen([node, str(bridge), '--port', str(self.port), '--session', self.connection['session_path']],
                                        cwd=str(bridge.parent), env=env, stdin=subprocess.DEVNULL,
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **options)
        self.thread = threading.Thread(target=self._poll, daemon=True, name='ZayaWhatsAppBridge')
        self.thread.start()

    def _poll(self) -> None:
        while not self.closed.wait(1):
            if self.process.poll() is not None:
                self.ready = False
                self.error = f'Bridge exited with code {self.process.returncode}.'
                return
            try:
                response = self.http.get(self.url + '/health', timeout=3)
                response.raise_for_status()
                self.ready = response.json().get('status') == 'connected'
                if not self.ready:
                    continue
                response = self.http.get(self.url + '/messages', timeout=3)
                response.raise_for_status()
                events = response.json()
                if not isinstance(events, list):
                    raise ValueError('Bridge returned an invalid message batch.')
                for event in events:
                    try:
                        message = normalize_event(event, self.connection.get('account_id', '').split(':')[0].split('@')[0] + '@s.whatsapp.net')
                        self.callback(message)
                        self.last_event_at = time.time()
                    except (ValueError, KeyError, TypeError):
                        self.error = 'One unsupported bridge event was skipped; no attachment paths were opened.'
                self.error = None
            except (requests.RequestException, ValueError) as error:
                self.ready = False
                self.error = f'Bridge feed unavailable: {type(error).__name__}'

    def send(self, chat_id: str, message: str, reply_to_id: str | None = None) -> subprocess.CompletedProcess:
        validate_chat_id(chat_id)
        if not self.ready:
            return subprocess.CompletedProcess([], 1, json.dumps({'error': 'WhatsApp bridge is not connected.'}), '')
        payload = {'chatId': chat_id, 'message': message}
        if reply_to_id:
            payload['replyTo'] = reply_to_id
        response = self.http.post(self.url + '/send', json=payload, timeout=50)
        result = response.json()
        if result.get('messageId'):
            result['message_id'] = result['messageId']
        return subprocess.CompletedProcess([], 0 if response.ok else 1, json.dumps(result), '')

    def close(self) -> None:
        self.closed.set()
        self.ready = False
        if self.process:
            terminate_tree(self.process)
        if hasattr(self, 'thread'):
            self.thread.join(timeout=5)
        self.http.close()
