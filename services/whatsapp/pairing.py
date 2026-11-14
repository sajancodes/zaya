"""Real QR pairing through Hermes's native bridge; exact session pointer stays private."""
from __future__ import annotations
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import threading
import time
from core.event_bus import bus
from core.shell_session import terminate_tree
from services.whatsapp.bridge import get_bridge_script, hermes_home
from services.whatsapp.connection import CONNECTION_PATH, load_connection, normalize_account


class PairingManager:
    def __init__(self, home: Path | None = None, config_path: Path = CONNECTION_PATH):
        self.home = home or hermes_home()
        self.config_path = config_path
        self.session = self.home / 'whatsapp' / 'session'
        self.qr_path = config_path.with_name('hermes_pairing_qr.png')
        self.lock = threading.RLock()
        self.process = None
        self.state = 'idle'
        self.error = None
        self.qr_updated_at = None

    def status(self) -> dict:
        with self.lock:
            paired = False
            try:
                paired = load_connection(self.config_path) is not None
            except (OSError, ValueError, KeyError):
                pass
            return {'state': 'paired' if paired else self.state, 'paired': paired,
                    'qr_path': str(self.qr_path) if self.state == 'waiting_scan' and self.qr_path.exists() else None,
                    'qr_updated_at': self.qr_updated_at, 'error': self.error}

    def start(self) -> dict:
        with self.lock:
            if self.status()['paired'] or (self.process and self.process.poll() is None):
                return self.status()
            bridge = get_bridge_script(self.home)
            node = shutil.which('node')
            if not node or not bridge.is_file() or not (bridge.parent / 'node_modules').is_dir():
                raise RuntimeError('Install WhatsApp bridge dependencies before pairing.')
            # Existing linked identity is preserved. Do not erase a session to
            # produce a new QR merely because the local pointer is missing.
            creds = self.session / 'creds.json'
            if creds.exists():
                data = json.loads(creds.read_text(encoding='utf-8'))
                if data.get('me', {}).get('id'):
                    self._save_connection(data['me'])
                    return self.status()
            self.session.mkdir(parents=True, exist_ok=True)
            env = dict(os.environ, WHATSAPP_MODE='self-chat', WHATSAPP_DM_POLICY='pairing', HERMES_HOME=str(self.home))
            options = {'creationflags': subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == 'nt' else {'start_new_session': True}
            self.process = subprocess.Popen([node, str(bridge), '--pair-only', '--pair-json', '--session', str(self.session)],
                cwd=str(bridge.parent), env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace', **options)
            self.state = 'connecting'
            self.timer = threading.Timer(300, self.cancel)
            self.timer.daemon = True
            self.timer.start()
            threading.Thread(target=self._watch, daemon=True, name='ZayaWhatsAppPairing').start()
            return self.status()

    def _save_connection(self, user: dict) -> None:
        credentials = self.session / 'creds.json'
        if not credentials.exists():
            raise ValueError('Linked-device credentials have not been saved yet.')
        saved = json.loads(credentials.read_text(encoding='utf-8'))
        account = normalize_account(str(user.get('id', '')))
        if account != normalize_account(str(saved.get('me', {}).get('id', ''))):
            raise ValueError('Connected account does not match saved credentials.')
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        record = {'hermes_home': str(self.home.resolve()), 'session_path': str(self.session.resolve()),
                  'account_id': account, 'account_name': user.get('name'), 'mode': 'self-chat',
                  'paired_at': time.time(), 'credentials_saved': True}
        temporary = self.config_path.with_suffix('.tmp')
        temporary.write_text(json.dumps(record, indent=2), encoding='utf-8')
        temporary.replace(self.config_path)
        dotenv = self.home / '.env'
        text = dotenv.read_text(encoding='utf-8') if dotenv.exists() else ''
        for key, value in [('WHATSAPP_ENABLED', 'true'), ('WHATSAPP_MODE', 'self-chat')]:
            pattern = r'(?m)^' + re.escape(key) + r'=.*$'
            text = re.sub(pattern, key + '=' + value, text) if re.search(pattern, text) else text.rstrip() + '\n' + key + '=' + value + '\n'
        dotenv.write_text(text, encoding='utf-8')
        self.state = 'paired'
        if self.qr_path.exists():
            self.qr_path.unlink()
        bus.publish('whatsapp.connection.changed', paired=True)

    def _watch(self) -> None:
        try:
            for line in self.process.stdout:
                try:
                    event = json.loads(line)
                except ValueError:
                    continue
                with self.lock:
                    if event.get('event') == 'qr':
                        import qrcode
                        self.qr_path.parent.mkdir(parents=True, exist_ok=True)
                        qrcode.make(event['qr']).save(self.qr_path)
                        self.qr_updated_at = time.time()
                        self.state = 'waiting_scan'
                    elif event.get('event') == 'connected':
                        time.sleep(2.5)  # Hermes flushes linked-device credentials before exiting
                        self._save_connection(event.get('user') or {})
                        self.timer.cancel()
                    elif event.get('event') == 'error':
                        self.error = 'WhatsApp pairing failed; retry from the connection panel.'
            if self.state not in {'paired', 'cancelled'}:
                self.state = 'failed'
                self.error = 'Pairing ended without a confirmed linked account.'
        except (OSError, ValueError, KeyError):
            self.state = 'failed'
            self.error = 'Pairing could not be persisted; inspect local connection diagnostics.'
        finally:
            if self.process.stdout:
                self.process.stdout.close()

    def cancel(self) -> None:
        with self.lock:
            if self.state == 'paired':
                return
            if self.process:
                terminate_tree(self.process)
            self.state = 'cancelled'
            if self.qr_path.exists():
                self.qr_path.unlink()


_pairing = None
_lock = threading.Lock()


def get_pairing() -> PairingManager:
    global _pairing
    with _lock:
        if _pairing is None:
            _pairing = PairingManager()
    return _pairing
