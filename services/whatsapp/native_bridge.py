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
from services.whatsapp.bridge import get_bridge_script
from services.whatsapp.connection import load_connection
from services.whatsapp.models import Message, validate_chat_id


class AttachedProcess:
    """Process interface for an exact verified orphan; never an arbitrary PID."""
    def __init__(self, process):
        self.process, self.pid = process, process.pid
        self.returncode = None

    def poll(self):
        if not self.process.is_running():
            self.returncode = 1
        return self.returncode

    def kill(self):
        self.process.kill()


def verified_orphan(port: int, bridge: Path, session: Path):
    import psutil
    candidates = {c.pid for c in psutil.net_connections(kind='tcp')
                  if c.status == 'LISTEN' and c.laddr.port == port and c.pid}
    if len(candidates) != 1:
        raise RuntimeError('Cannot establish bridge process ownership.')
    process = psutil.Process(candidates.pop())
    args = process.cmdline()
    try:
        script = Path(args[1]).resolve()
        exact_session = Path(args[args.index('--session') + 1]).resolve()
        exact_port = int(args[args.index('--port') + 1])
    except (ValueError, IndexError):
        raise RuntimeError('Existing bridge command is not verifiable.')
    if script != bridge.resolve() or exact_session != session.resolve() or exact_port != port:
        raise RuntimeError('Existing bridge belongs to another session or application.')
    try:
        parent = process.parent()
        if parent and parent.create_time() <= process.create_time():
            raise RuntimeError('Existing bridge still has a live owner; competing consumer refused.')
    except psutil.NoSuchProcess:
        pass
    return AttachedProcess(process)


def normalize_event(event: dict, owner_id: str = '') -> Message:
    chat = validate_chat_id(str(event['chatId']))
    timestamp = event.get('timestamp', time.time())
    if isinstance(timestamp, dict):
        timestamp = timestamp.get('low', time.time())
    receipt = event.get('readReceiptKey') or {}
    if not isinstance(receipt, dict):
        raise ValueError('Invalid receipt key')
    owner = bool(event.get('fromOwner') or receipt.get('fromMe'))
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
    def __init__(self, callback, connection: dict | None = None, port: int = 8768, read_state_callback=None) -> None:
        self.callback = callback
        self.read_state_callback = read_state_callback
        self.read_state_available = False
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
        self.lease = None

    def _claim(self):
        path = Path(self.connection['session_path']) / 'zaya-bridge.lock'
        self.lease = path.open('a+b')
        if path.stat().st_size == 0:
            self.lease.write(b'0')
            self.lease.flush()
        self.lease.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(self.lease.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.lease.close()
            self.lease = None
            raise RuntimeError('Another Zaya instance already owns WhatsApp monitoring.')

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
        bridge = get_bridge_script(home)
        node = shutil.which('node')
        if not node or not bridge.is_file() or not (bridge.parent / 'node_modules').is_dir():
            raise RuntimeError('WhatsApp bridge or its Node dependencies are unavailable.')
        if self.read_state_callback:
            from services.whatsapp.bridge_read_state import prepare_bridge
            try:
                bridge = prepare_bridge(bridge)
                self.read_state_available = True
            except (ValueError, OSError):
                # An upstream update must not disable working messages/replies.
                # Status exposes this verification gap; manual replies still sync.
                self.read_state_available = False
        self._claim()
        try:
            self.http.get(self.url + '/health', timeout=.5)
        except requests.ConnectionError:
            pass
        except requests.RequestException as error:
            self.lease.close()
            self.lease = None
            raise RuntimeError('Existing bridge health could not be verified.') from error
        else:
            try:
                self.process = verified_orphan(self.port, bridge, Path(self.connection['session_path']))
            except Exception as error:
                self.lease.close()
                self.lease = None
                raise RuntimeError(f'Existing bridge ownership refused: {error}') from error
            self.thread = threading.Thread(target=self._poll, daemon=True, name='ZayaWhatsAppBridge')
            self.thread.start()
            return
        # Process-local policy allows contact observations only. This does not
        # weaken Telegram or change Hermes profile allowlists. Zaya never routes
        # this content to the privileged operator, even owner outgoing text.
        env = dict(os.environ, WHATSAPP_MODE='bot', WHATSAPP_ALLOWED_USERS='*',
                   WHATSAPP_DM_POLICY='open', WHATSAPP_FORWARD_OWNER_MESSAGES='true',
                   WHATSAPP_SEND_READ_RECEIPTS='false', WHATSAPP_REPLY_PREFIX='', HERMES_HOME=str(home))
        options = {'creationflags': subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == 'nt' else {'start_new_session': True}
        try:
            self.process = subprocess.Popen([node, str(bridge), '--port', str(self.port), '--session', self.connection['session_path']],
                                        cwd=str(bridge.parent), env=env, stdin=subprocess.DEVNULL,
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **options)
        except Exception:
            self.lease.close()
            self.lease = None
            raise
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
                health = response.json()
                if not isinstance(health, dict):
                    raise ValueError('Bridge returned invalid health data.')
                self.ready = health.get('status') == 'connected'
                if not self.ready:
                    continue
                response = self.http.get(self.url + '/messages', timeout=3)
                response.raise_for_status()
                events = response.json()
                if not isinstance(events, list):
                    raise ValueError('Bridge returned an invalid message batch.')
                for event in events:
                    try:
                        if not isinstance(event, dict):
                            raise ValueError('Invalid bridge event')
                        if event.get('event') == 'chat.read_state':
                            if self.read_state_callback:
                                self.read_state_callback(event)
                            self.last_event_at = time.time()
                            continue
                        account = self.connection.get('account_id') or ''
                        owner_id = account.split('@')[0].split(':')[0]
                        owner_id = owner_id + '@s.whatsapp.net' if owner_id else ''
                        message = normalize_event(event, owner_id)
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
        try:
            result = response.json()
            if not isinstance(result, dict):
                raise ValueError('Invalid send result')
        except ValueError:
            return subprocess.CompletedProcess([], 1, json.dumps({'error': 'Bridge returned an unreadable delivery result; delivery is unverified. Do not automatically resend.'}), '')
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
        if self.lease:
            self.lease.close()
            self.lease = None
