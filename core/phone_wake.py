"""Paired-phone wake listener; no microphone, provider or command execution API."""
from collections import deque
from http.server import BaseHTTPRequestHandler, HTTPServer
import ipaddress
import json
import os
import time
from urllib.request import urlopen

from core.desktop_lifecycle import ROOT, launch_desktop, python_windowless, spawn_fixed

PORT = 8002  # 8001 is the existing dashboard TLS alias.
TAILNET = ipaddress.ip_network('100.64.0.0/10')


def allowed_peer(address):
    try:
        ip = ipaddress.ip_address(address)
        return ip.is_loopback or ip in TAILNET
    except ValueError:
        return False


def make_server(registry, launch=launch_desktop, address=('0.0.0.0', PORT)):
    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(3)

        def log_message(self, *_args):
            pass  # Never record device secrets or request bodies.

        def reply(self, code, payload):
            data = json.dumps(payload).encode('utf-8')
            self.send_response(code)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path == '/health' and ipaddress.ip_address(self.client_address[0]).is_loopback:
                self.reply(200, {'service': 'zaya-phone-wake'})
            else:
                self.reply(404, {'ok': False})

        def do_POST(self):
            if self.path != '/wake' or not allowed_peer(self.client_address[0]):
                self.reply(403, {'ok': False, 'error': 'Paired tailnet phone required.'})
                return
            now = time.monotonic()
            while self.server.hits and now - self.server.hits[0] > 60:
                self.server.hits.popleft()
            if len(self.server.hits) >= 20:
                self.reply(429, {'ok': False, 'error': 'Please wait before calling again.'})
                return
            self.server.hits.append(now)
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 1024 or self.headers.get('Transfer-Encoding'):
                    raise ValueError('Invalid size')
                data = json.loads(self.rfile.read(size))
                device, secret = data.get('device_id'), data.get('device_secret')
                if not isinstance(device, str) or not isinstance(secret, str) or max(len(device), len(secret)) > 256:
                    raise ValueError('Invalid credential')
                record = registry.authenticate(device, secret)
            except (ValueError, TypeError, AttributeError, OSError):
                self.reply(400, {'ok': False, 'error': 'Invalid wake request.'})
                return
            if not record or record.get('platform') != 'android':
                self.reply(401, {'ok': False, 'error': 'This phone is not paired or was revoked.'})
                return
            # No URL, path, prompt or shell command from the caller is executed.
            try:
                outcome = launch()
            except OSError:
                self.reply(503, {'ok': False, 'error': 'Could not start Zaya. Check the laptop.'})
                return
            self.reply(202, {'ok': True, 'state': outcome})

    server = HTTPServer(address, Handler)
    server.hits = deque()
    return server


def healthy():
    try:
        with urlopen(f'http://127.0.0.1:{PORT}/health', timeout=0.5) as response:
            return json.load(response).get('service') == 'zaya-phone-wake'
    except (OSError, ValueError):
        return False


def install():
    """User-level logon entry; no elevation, credentials, or desktop autostart."""
    if os.name != 'nt':
        raise OSError('Phone wake launcher currently requires Windows.')
    import subprocess
    import winreg
    command = subprocess.list2cmdline([python_windowless(), str(ROOT / 'tools' / 'phone_wake.py')])
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Run') as key:
        winreg.SetValueEx(key, 'ZayaPhoneWake', 0, winreg.REG_SZ, command)
    if not healthy():
        spawn_fixed([str(ROOT / 'tools' / 'phone_wake.py')], windowless=False)
        for _ in range(20):
            if healthy():
                return
            time.sleep(0.2)
        raise OSError('Phone wake listener did not start on port 8002.')


def serve():
    from core.device_registry import get_registry
    try:
        server = make_server(get_registry())
    except OSError:
        if healthy():
            return
        raise
    with server:
        server.serve_forever()
