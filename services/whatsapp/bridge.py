"""Authenticated loopback-only Hermes hook receiver and reversible installer."""
from __future__ import annotations
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
from core.runtime_paths import mutable_path
import secrets
import shutil
import threading
import time
from typing import Callable

ROOT = Path(__file__).resolve().parents[2]
DESCRIPTOR = mutable_path(ROOT / 'config' / 'hermes_bridge.json')


class HookReceiver:
    def __init__(self, callback: Callable, descriptor: Path = DESCRIPTOR, port: int = 0) -> None:
        self.callback, self.descriptor = callback, descriptor
        self.secret = secrets.token_urlsafe(32)
        self.last_event_at: float | None = None
        receiver = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                return  # private chat content and authorization never reach HTTP logs

            def do_POST(self):
                if self.path != '/events' or self.headers.get('Origin'):
                    self.send_error(403)
                    return
                supplied = self.headers.get('Authorization', '').removeprefix('Bearer ')
                if not hmac.compare_digest(supplied, receiver.secret):
                    self.send_error(401)
                    return
                try:
                    length = int(self.headers.get('Content-Length', '0'))
                    if length < 1 or length > 65536:
                        self.send_error(413)
                        return
                    payload = json.loads(self.rfile.read(length))
                    if payload.get('event') not in {'gateway:startup', 'session:start', 'session:end', 'agent:start', 'agent:end'}:
                        raise ValueError('Unsupported hook event')
                    if not isinstance(payload.get('context'), dict):
                        raise ValueError('Invalid context')
                    receiver.callback(payload['event'], payload['context'])
                    receiver.last_event_at = time.time()
                except (ValueError, TypeError, KeyError):
                    self.send_error(400)
                    return
                except Exception:
                    self.send_error(503)
                    return
                self.send_response(204)
                self.end_headers()
        self.server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
        self.server.daemon_threads = True

    def start(self) -> None:
        self.descriptor.parent.mkdir(parents=True, exist_ok=True)
        self.descriptor.write_text(json.dumps({'url': f'http://127.0.0.1:{self.server.server_port}/events', 'token': self.secret}), encoding='utf-8')
        if os.name != 'nt':
            self.descriptor.chmod(0o600)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True, name='ZayaHermesEvents')
        self.thread.start()

    def close(self) -> None:
        # shutdown() waits forever when serve_forever() was never started.
        thread = getattr(self, 'thread', None)
        if thread and thread.is_alive():
            self.server.shutdown()
        self.server.server_close()
        if thread and thread is not threading.current_thread():
            thread.join(timeout=3)
        if self.descriptor.exists():
            try:
                if json.loads(self.descriptor.read_text())['token'] == self.secret:
                    self.descriptor.unlink()
            except (ValueError, KeyError):
                pass


def get_bridge_script(home: Path | None = None) -> Path:
    """Return the preferred WhatsApp bridge script.
    
    Prefers Zaya's bundled native bridge under bridge/whatsapp/bridge.js.
    Falls back to Hermes profile or hermes-agent if bundled bridge is absent.
    """
    bundled = ROOT / 'bridge' / 'whatsapp' / 'bridge.js'
    if bundled.is_file():
        return bundled
    h = home or hermes_home()
    candidates = [
        h / 'hermes-agent' / 'scripts' / 'whatsapp-bridge' / 'bridge.js',
        Path.home() / 'hermes-agent' / 'scripts' / 'whatsapp-bridge' / 'bridge.js',
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return bundled


def hermes_home() -> Path:
    if os.environ.get('HERMES_HOME'):
        return Path(os.environ['HERMES_HOME']).expanduser().resolve()
    # The installed Windows launcher uses LocalAppData/hermes, unlike Unix.
    if os.name == 'nt' and os.environ.get('LOCALAPPDATA'):
        return Path(os.environ['LOCALAPPDATA']) / 'hermes'
    return Path.home() / '.hermes'


def install_hook(home: Path | None = None, descriptor: Path = DESCRIPTOR) -> Path:
    destination = (home or hermes_home()) / 'hooks' / 'zaya-whatsapp'
    destination.mkdir(parents=True, exist_ok=True)
    template = Path(__file__).with_name('hook_handler.py')
    handler = destination / 'handler.py'
    if handler.exists() and handler.read_bytes() != template.read_bytes():
        shutil.copy2(handler, destination / f'handler.backup-{time.time_ns()}.py')
    shutil.copy2(template, handler)
    (destination / 'HOOK.yaml').write_text('name: zaya-whatsapp\ndescription: Observe WhatsApp events for Zaya; does not control Hermes turns\nevents:\n  - gateway:startup\n  - session:start\n  - session:end\n  - agent:start\n  - agent:end\n', encoding='utf-8')
    (destination / 'zaya-path.json').write_text(json.dumps({'descriptor': str(descriptor.resolve())}), encoding='utf-8')
    return destination
