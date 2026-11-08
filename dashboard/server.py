"""
dashboard/server.py — Zaya Local HTTP Dashboard

Plain HTTP on port 8000 (no SSL warnings, no firewall issues).
Security at the application layer: AES-256-CBC with session-key-derived key.
CryptoJS is auto-downloaded once and served locally — no CDN needed after that.

Install deps:  pip install fastapi "uvicorn[standard]" cryptography
"""

import asyncio
import base64
import hashlib
import re
import secrets
import socket
import string
import time
from pathlib import Path
from typing import Callable

_DEPS_OK = False
try:
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
    from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
    import uvicorn
    _DEPS_OK = True
except ImportError:
    pass

# python-multipart is required for file uploads — optional dependency
_UPLOAD_OK = False
try:
    from fastapi import UploadFile, File as FastAPIFile
    _UPLOAD_OK = True
except Exception:
    pass

BASE_DIR    = Path(__file__).resolve().parent.parent
STATIC_DIR  = Path(__file__).parent / "static"
PORT        = 8000
MAX_UPLOAD_MB = 500


def _make_uploads_dir() -> Path:
    """Return (and create) the cross-platform uploads folder."""
    for candidate in [
        Path.home() / "Downloads" / "Zaya Uploads",
        Path.home() / "Documents" / "Zaya Uploads",
        BASE_DIR / "uploads",
    ]:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            return candidate
        except Exception:
            pass
    return BASE_DIR / "uploads"


UPLOADS_DIR = _make_uploads_dir()

def _get_gemini_key() -> str | None:
    try:
        import json as _json
        with open(BASE_DIR / "config" / "api_keys.json", "r", encoding="utf-8") as f:
            return _json.load(f).get("gemini_api_key")
    except Exception:
        return None


def _dashboard_https_setting() -> str:
    """`auto` (default) or `off`, from config/api_keys.json → `dashboard_https`.

    The native phone companion reaches Zaya over the Tailscale tailnet, which is
    already encrypted end to end, and it only permits plain HTTP for `*.ts.net`
    names: a locally generated self-signed certificate can never be trusted by
    the app, so HTTPS would lock the phone out. An owner who pairs a phone sets
    this to `false` and the dashboard serves HTTP on its usual port — still
    encrypted on the wire by the tailnet. `true`/`auto` keep the dashboard's
    own TLS (and the `PORT+1` alias) exactly as before.
    """
    try:
        import json as _json
        with open(BASE_DIR / "config" / "api_keys.json", "r", encoding="utf-8") as f:
            value = _json.load(f).get("dashboard_https", "auto")
    except Exception:
        return "auto"
    if isinstance(value, bool):
        return "auto" if value else "off"
    text = str(value).strip().lower()
    return "off" if text in ("off", "false", "no", "0", "http") else "auto"

_KEY_CHARS = [c for c in (string.ascii_uppercase + string.digits)
              if c not in ('O', 'I', 'L', '0', '1')]

# ── AES-256-CBC ───────────────────────────────────────────────────────────────
# The salt must be the SAME string the browser derives its key with (see
# dashboard/static/app.html). Server and client had drifted apart — the client
# used 'ZAYA-DASHBOARD-v1' while the server still used the pre-rename
# 'JARVIS-DASHBOARD-v1' — so every encrypted remote command failed to decrypt
# and the dashboard silently fell back to plaintext. The current salt wins; the
# old one stays only as a decrypt fallback for a page already open in a browser.
_AES_SALT = b'ZAYA-DASHBOARD-v1'
_AES_LEGACY_SALTS = (b'JARVIS-DASHBOARD-v1',)


def _derive_key(session_key: str, salt: bytes = _AES_SALT) -> bytes:
    """SHA-256(sessionKey‖salt) → 32-byte AES-256 key (microseconds, no PBKDF2 needed)."""
    return hashlib.sha256(session_key.encode('utf-8') + salt).digest()


def _decrypt_gcm(aes_key: bytes, enc_b64: str) -> str:
    """Decrypt base64(nonce[12] ‖ ciphertext ‖ tag[16]) with AES-256-GCM."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    raw = base64.b64decode(enc_b64)
    if len(raw) < 28:
        raise ValueError("Invalid AES-GCM payload length")
    nonce, ct_and_tag = raw[:12], raw[12:]
    return AESGCM(aes_key).decrypt(nonce, ct_and_tag, None).decode('utf-8')


def _decrypt_cbc(aes_key: bytes, enc_b64: str) -> str:
    """Decrypt base64(IV[16] ‖ ciphertext) with AES-256-CBC + PKCS7."""
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.primitives import padding as sym_pad
    raw      = base64.b64decode(enc_b64)
    iv, ct   = raw[:16], raw[16:]
    dec      = Cipher(algorithms.AES(aes_key), modes.CBC(iv)).decryptor()
    padded   = dec.update(ct) + dec.finalize()
    unpadder = sym_pad.PKCS7(128).unpadder()
    return (unpadder.update(padded) + unpadder.finalize()).decode('utf-8')


# ── CryptoJS (auto-download once, served locally) ─────────────────────────────
_CRYPTOJS_CDN  = ("https://cdnjs.cloudflare.com/ajax/libs/"
                  "crypto-js/4.2.0/crypto-js.min.js")
_CRYPTOJS_FILE = STATIC_DIR / "crypto-js.min.js"


def _ensure_network_access(port: int) -> None:
    """Cross-platform, best-effort: open port in the OS firewall for LAN access.

    Runs in a background thread — never blocks uvicorn startup.

    Windows : writes a .bat file, runs it elevated via Windows ShellExecuteW
              (native UAC dialog, guaranteed to appear). One-time setup.
    macOS   : osascript admin dialog if the Application Firewall is on.
    Linux   : pkexec GUI → sudo -n → prints manual command as fallback.
    """
    import sys, subprocess, os, tempfile, threading

    # ── Windows ──────────────────────────────────────────────────────────────
    if sys.platform == "win32":
        import ctypes, time

        port_rule = f"Zaya Dashboard Port {port}"
        prog_rule  = "Zaya Dashboard Python"
        py_exe     = sys.executable

        def _netsh_rule_exists(name: str) -> bool:
            try:
                r = subprocess.run(
                    ["netsh", "advfirewall", "firewall", "show", "rule", f"name={name}"],
                    capture_output=True, text=True, timeout=5,
                )
                return r.returncode == 0 and "No rules match" not in r.stdout
            except Exception:
                return False

        def _network_is_public() -> bool:
            try:
                r = subprocess.run(
                    ["powershell", "-NoProfile", "-NonInteractive", "-Command",
                     "(Get-NetConnectionProfile | "
                     "Where-Object {$_.NetworkCategory -eq 'Public'} | "
                     "Measure-Object).Count"],
                    capture_output=True, text=True, timeout=6,
                )
                return r.stdout.strip() not in ("", "0")
            except Exception:
                return False

        need_port    = not _netsh_rule_exists(port_rule)
        need_prog    = not _netsh_rule_exists(prog_rule)

        if not need_port and not need_prog:
            return  # already fully configured

        # Build a .bat file — netsh runs fast when elevated
        bat_lines = ["@echo off"]
        if need_port:
            bat_lines.append(
                f'netsh advfirewall firewall add rule '
                f'name="{port_rule}" protocol=TCP dir=in '
                f'localport={port} action=allow'
            )
        if need_prog:
            bat_lines.append(
                f'netsh advfirewall firewall add rule '
                f'name="{prog_rule}" dir=in action=allow '
                f'program="{py_exe}" enable=yes'
            )

        bat_body = "\r\n".join(bat_lines) + "\r\n"
        fd, bat_path = tempfile.mkstemp(suffix=".bat", prefix="zaya_fw_")
        try:
            os.write(fd, bat_body.encode("mbcs"))   # Windows cmd.exe expects ANSI
            os.close(fd)
        except Exception:
            try:
                os.close(fd)
            except Exception:
                pass
            return

        # ── Try running directly (succeeds when already admin) ────────────────
        try:
            r = subprocess.run(
                [bat_path], capture_output=True, timeout=8, shell=True
            )
            if r.returncode == 0:
                print(f"[Dashboard] Firewall configured for port {port}.")
                try:
                    os.unlink(bat_path)
                except Exception:
                    pass
                return
        except Exception:
            pass

        # ── ShellExecuteW: native UAC elevation (most reliable on Windows) ────
        # ShellExecuteW with verb "runas" always shows the UAC dialog regardless
        # of UAC level settings. Non-blocking — uvicorn is already running.
        print("[Dashboard] One-time network setup required.")
        print("[Dashboard] >>> A Windows security dialog will appear — click 'Yes' <<<")
        try:
            ret = ctypes.windll.shell32.ShellExecuteW(
                None,       # hwnd  (no parent window)
                "runas",    # verb  (request elevation)
                bat_path,   # file  (our .bat)
                None,       # params
                None,       # working dir
                0,          # SW_HIDE (run without a visible cmd window)
            )
            if int(ret) > 32:
                # ShellExecuteW returns immediately; bat finishes in ~1 second.
                # Sleep briefly so the rules are in place before the first retry.
                time.sleep(2)
                print(f"[Dashboard] Network setup complete — port {port} is open.")
                print("[Dashboard] Refresh your phone browser to connect.")
            else:
                print("[Dashboard] Setup was not allowed.")
                print("[Dashboard] Phone connections may fail until Zaya is run as Administrator.")
        except Exception as e:
            print(f"[Dashboard] Firewall setup error: {e}")
        finally:
            # Cleanup after the bat has had time to run
            def _cleanup(path: str) -> None:
                time.sleep(5)
                try:
                    os.unlink(path)
                except Exception:
                    pass
            threading.Thread(target=_cleanup, args=(bat_path,), daemon=True).start()
        return

    # ── macOS ─────────────────────────────────────────────────────────────────
    if sys.platform == "darwin":
        fw_ctl = "/usr/libexec/ApplicationFirewall/socketfilterfw"
        try:
            r = subprocess.run(
                [fw_ctl, "--getglobalstate"], capture_output=True, text=True, timeout=5,
            )
            if "disabled" in r.stdout.lower():
                return  # firewall off — nothing to do

            py = sys.executable
            listed = subprocess.run(
                [fw_ctl, "--listapps"], capture_output=True, text=True, timeout=5,
            )
            if py in listed.stdout:
                return  # already allowed

            print("[Dashboard] One-time network setup — enter your password in the macOS dialog.")
            subprocess.run(
                ["osascript", "-e",
                 f'do shell script "{fw_ctl} --add {py} && {fw_ctl} --unblockapp {py}"'
                 f' with administrator privileges'],
                timeout=60,
            )
        except Exception:
            pass  # macOS firewall is off by default — silent failure is fine
        return

    # ── Linux ─────────────────────────────────────────────────────────────────
    def _privileged(cmd: list[str]) -> bool:
        for prefix in (["pkexec"], ["sudo", "-n"]):
            try:
                r = subprocess.run(prefix + cmd, capture_output=True, timeout=30)
                if r.returncode == 0:
                    return True
            except Exception:
                pass
        return False

    try:  # ufw
        r = subprocess.run(["ufw", "status"], capture_output=True, text=True, timeout=5)
        if "active" in r.stdout.lower():
            if _privileged(["ufw", "allow", f"{port}/tcp"]):
                print(f"[Dashboard] ufw: port {port} allowed.")
            else:
                print(f"[Dashboard] Run manually:  sudo ufw allow {port}/tcp")
            return
    except FileNotFoundError:
        pass

    try:  # firewalld
        r = subprocess.run(
            ["firewall-cmd", "--state"], capture_output=True, text=True, timeout=5,
        )
        if "running" in r.stdout.lower():
            ok = (_privileged(["firewall-cmd", "--add-port", f"{port}/tcp", "--permanent"])
                  and _privileged(["firewall-cmd", "--reload"]))
            if ok:
                print(f"[Dashboard] firewalld: port {port} allowed.")
            else:
                print(f"[Dashboard] Run manually:  sudo firewall-cmd --add-port={port}/tcp --permanent && sudo firewall-cmd --reload")
            return
    except FileNotFoundError:
        pass

    try:  # iptables (not persistent but works until reboot)
        r = subprocess.run(["iptables", "-L", "INPUT", "-n"], capture_output=True, timeout=5)
        if r.returncode == 0:
            if _privileged(["iptables", "-A", "INPUT", "-p", "tcp", "--dport", str(port), "-j", "ACCEPT"]):
                print(f"[Dashboard] iptables: port {port} opened.")
            else:
                print(f"[Dashboard] Run manually:  sudo iptables -A INPUT -p tcp --dport {port} -j ACCEPT")
    except FileNotFoundError:
        pass  # no iptables means firewall is probably off — nothing to do


def _ensure_crypto_js() -> None:
    if _CRYPTOJS_FILE.exists():
        return
    try:
        import urllib.request
        print("[Dashboard] Downloading CryptoJS (one-time setup)…")
        urllib.request.urlretrieve(_CRYPTOJS_CDN, str(_CRYPTOJS_FILE))
        print("[Dashboard] CryptoJS cached — will serve locally from now on.")
    except Exception as e:
        print(f"[Dashboard] CryptoJS download failed: {e}")
        print(f"[Dashboard] Encryption will fall back to CDN load on client.")


# _ensure_crypto_js() not run at import time


# ── helpers ───────────────────────────────────────────────────────────────────

def _local_ip() -> str:
    """Return the best LAN-facing IPv4 address, no internet required."""
    # Method 1: route trick (fast, works when internet is available)
    for probe in ("8.8.8.8", "1.1.1.1", "192.168.1.1"):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(0.5)
            s.connect((probe, 80))
            ip = s.getsockname()[0]
            s.close()
            if not ip.startswith("127."):
                return ip
        except Exception:
            pass

    # Method 2: hostname resolution (works offline on most systems)
    try:
        ip = socket.gethostbyname(socket.gethostname())
        if not ip.startswith("127."):
            return ip
    except Exception:
        pass

    # Method 3: enumerate all interfaces (fully offline, no external deps)
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith("127.") and not ip.startswith("169.254."):
                return ip
    except Exception:
        pass

    return "127.0.0.1"


def _ensure_certs() -> bool:
    """
    Make sure config/certs holds a TLS key pair, generating a self-signed one the
    first time the dashboard runs.

    The pair is deliberately NOT shipped in the repository. A private key that
    every user downloads is the same as having no private key at all: anyone can
    present a certificate that matches it. Generating locally gives each install
    its own key, costs about a second, and happens exactly once.

    Returns True when a usable pair exists afterwards; False leaves the caller on
    plain HTTP, which still works — the QR code simply encodes http:// instead.
    """
    certs = BASE_DIR / "config" / "certs"
    key_p = certs / "zaya.key"
    crt_p = certs / "zaya.crt"
    if key_p.exists() and crt_p.exists():
        return True

    try:
        import datetime
        import ipaddress
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.x509.oid import NameOID
    except ImportError:
        print("[Dashboard] cryptography not installed — serving over plain HTTP.")
        print("[Dashboard] For HTTPS run:  pip install cryptography")
        return False

    try:
        certs.mkdir(parents=True, exist_ok=True)
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

        who = x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, "Zaya Dashboard"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Zaya"),
        ])

        # The SAN has to cover every address the phone might use: the LAN IP the
        # QR code encodes, plus localhost when testing on the machine itself.
        alt = [x509.DNSName("localhost"),
               x509.IPAddress(ipaddress.IPv4Address("127.0.0.1"))]
        try:
            lan = _local_ip()
            if not lan.startswith("127."):
                alt.append(x509.IPAddress(ipaddress.IPv4Address(lan)))
        except Exception:
            pass          # no LAN address resolvable — localhost entries still work

        # Timezone-aware UTC: datetime.utcnow() is deprecated from Python 3.12 on,
        # and the builder normalises aware values to UTC itself.
        now = datetime.datetime.now(datetime.timezone.utc)
        cert = (
            x509.CertificateBuilder()
            .subject_name(who)
            .issuer_name(who)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - datetime.timedelta(days=1))
            .not_valid_after(now + datetime.timedelta(days=3650))
            .add_extension(x509.SubjectAlternativeName(alt), critical=False)
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .sign(key, hashes.SHA256())
        )

        key_p.write_bytes(key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ))
        crt_p.write_bytes(cert.public_bytes(serialization.Encoding.PEM))

        try:
            if sys.platform == "win32":
                import subprocess
                subprocess.run(
                    ["icacls", str(key_p), "/inheritance:r", "/grant:r", f"{os.environ.get('USERNAME', 'Users')}:(R,W)"],
                    capture_output=True, timeout=5, check=False
                )
            else:
                import os as _os
                _os.chmod(key_p, 0o600)
        except Exception:
            pass

        print(f"[Dashboard] Generated a self-signed certificate for this machine: {certs}")
        return True
    except Exception as e:
        print(f"[Dashboard] Certificate generation failed ({e}) — serving over plain HTTP.")
        return False


def _read(name: str) -> str:
    return (STATIC_DIR / name).read_text(encoding="utf-8")


# ── DashboardServer ───────────────────────────────────────────────────────────

class DashboardServer:

    def __init__(self):
        self._ip                          = _local_ip()
        from dashboard.mobile_api import RateLimiter
        self._tokens: dict[str, float]    = {}   # tok -> expires_at
        self._login_limiter               = RateLimiter(limit=5, window=60.0)
        self._token_keys: dict[str, str]  = {}   # auth_token → session_key
        self._aes_cache:  dict[str, bytes]= {}   # session_key → AES bytes
        self._clients: set[WebSocket]     = set()
        self._history: list[dict]         = []
        self._command_queue               = asyncio.Queue(maxsize=64)
        self._wake_callback               = None
        self._connect_callback            = None
        self._pending_keys: dict[str, float] = {}
        self._device_sessions: dict[str, dict] = {}  # legacy in-memory device tokens
        self._phone_audio_queue: asyncio.Queue    = asyncio.Queue(maxsize=200)
        self.assistant_ready: Callable[[], bool] | None = None
        self._phone_audio_dropped         = 0
        self._uploads_dir                 = UPLOADS_DIR
        self._devices                     = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._mobile                      = None
        self._login_html                  = _read("login.html")
        self._app_html                    = _read("app.html")
        self.app                          = self._build_app()

    # ── persistent paired devices ────────────────────────────────────────────

    def device_registry(self):
        """Paired devices live in SQLite, not in a dict that dies with the run."""
        if self._devices is None:
            from core.device_registry import get_registry
            self._devices = get_registry()
        return self._devices

    def mobile(self):
        if self._mobile is None:
            from dashboard.mobile_api import MobileApi
            self._mobile = MobileApi(self)
        return self._mobile

    def push_mobile_event(self, envelope: dict) -> None:
        """Thread-safe fan-out used by the runtime bridge."""
        mobile = self.mobile()
        mobile.push(envelope)

    def note_remote_connection(self, text: str) -> None:
        if self._connect_callback:
            try:
                self._connect_callback()
            except Exception:
                pass
        asyncio.create_task(self.broadcast({"type": "sys", "text": text}))

    # ── one-time key management ───────────────────────────────────────────

    def new_key(self, expiry_secs: int = 600) -> str:
        now = time.time()
        self._pending_keys = {k: v for k, v in self._pending_keys.items() if v > now}
        key = ''.join(secrets.choice(_KEY_CHARS) for _ in range(6))
        self._pending_keys[key] = now + expiry_secs
        return key

    @staticmethod
    def _ssl_enabled() -> bool:
        if _dashboard_https_setting() == "off":
            return False
        certs = BASE_DIR / "config" / "certs"
        return (certs / "zaya.key").exists() and (certs / "zaya.crt").exists()

    def get_url(self) -> str:
        proto = "https" if self._ssl_enabled() else "http"
        return f"{proto}://{self._ip}:{PORT}"

    def get_manual_url(self) -> str:
        """URL for manual browser entry. When HTTPS active, points to alias port (also HTTPS)."""
        if self._ssl_enabled():
            return f"{self._ip}:{PORT + 1}"
        return f"{self._ip}:{PORT}"

    def _aes_key(self, session_key: str) -> bytes:
        if session_key not in self._aes_cache:
            self._aes_cache[session_key] = _derive_key(session_key)
        return self._aes_cache[session_key]

    def _decrypt(self, token: str, enc_b64: str) -> str | None:
        sk = self._token_keys.get(token)
        if not sk:
            return None
        for salt in (_AES_SALT, *_AES_LEGACY_SALTS):
            aes_k = _derive_key(sk, salt)
            try:
                return _decrypt_gcm(aes_k, enc_b64)
            except Exception:
                pass
            try:
                return _decrypt_cbc(aes_k, enc_b64)
            except Exception:
                continue
        return None

    # ── callbacks ────────────────────────────────────────────────────────

    def set_wake_callback(self, fn) -> None:
        self._wake_callback = fn

    def set_connect_callback(self, fn) -> None:
        self._connect_callback = fn

    # ── broadcast ────────────────────────────────────────────────────────

    async def broadcast(self, msg: dict) -> None:
        self._history.append(msg)
        if len(self._history) > 300:
            self._history = self._history[-300:]
        dead: set[WebSocket] = set()
        for ws in list(self._clients):
            try:
                # A browser that stopped reading must not hold up the runtime
                # path that produced this message.
                await asyncio.wait_for(ws.send_json(msg), timeout=5.0)
            except Exception:
                dead.add(ws)
        self._clients -= dead

    # ── FastAPI app ───────────────────────────────────────────────────────

    def _build_app(self) -> "FastAPI":
        app = FastAPI(docs_url=None, redoc_url=None)

        def _valid_token(tok: str) -> bool:
            if not _valid_token(tok):
                return False
            exp = self._tokens.get(tok, 0.0)
            if exp < time.time():
                self._tokens.pop(tok, None)
                self._token_keys.pop(tok, None)
                return False
            return True

        def _auth(req: Request) -> bool:
            tok = req.headers.get("authorization", "").removeprefix("Bearer ").strip()
            return _valid_token(tok)

        # serve CryptoJS from local cache, fallback to CDN redirect
        @app.get("/static/crypto.js")
        async def serve_crypto():
            if _CRYPTOJS_FILE.exists():
                return FileResponse(str(_CRYPTOJS_FILE),
                                    media_type="application/javascript")
            from fastapi.responses import RedirectResponse
            return RedirectResponse(_CRYPTOJS_CDN)

        @app.get("/login", response_class=HTMLResponse)
        async def login_page():
            return HTMLResponse(self._login_html)

        @app.get("/", response_class=HTMLResponse)
        async def index():
            # Auth is handled client-side via sessionStorage bearer token.
            # Server-side header auth can't work here because browser navigations
            # don't send custom headers (location.href doesn't carry Authorization).
            html = (self._app_html
                    .replace("__IP__", self._ip)
                    .replace("__PORT__", str(PORT)))
            return HTMLResponse(html)

        @app.post("/login")
        async def login(req: Request):
            client_ip = req.client.host if req.client else "unknown"
            if not self._login_limiter.allow(client_ip):
                return JSONResponse({"ok": False, "error": "Too many login attempts. Please wait a minute."},
                                    status_code=429)
            body    = await req.json()
            entered = str(body.get("pin", "")).strip().upper()
            now     = time.time()
            if entered in self._pending_keys and self._pending_keys[entered] > now:
                del self._pending_keys[entered]          # one-time use
                tok = secrets.token_urlsafe(32)
                self._tokens[tok] = now + 86400.0
                self._token_keys[tok] = entered
                self._aes_key(entered)                   # pre-derive & cache
                if self._connect_callback:
                    self._connect_callback()
                asyncio.create_task(self.broadcast(
                    {"type": "sys", "text": "Remote connection established."}
                ))
                # Bearer token in response body — no cookies needed (works on any browser/HTTP)
                return JSONResponse({"ok": True, "token": tok})
            return JSONResponse({"ok": False, "error": "Invalid or expired key"},
                                status_code=401)

        @app.get("/auto-login")
        async def auto_login(key: str = ""):
            """QR code target — validates one-time key, creates session, redirects phone."""
            now = time.time()
            if not key or key not in self._pending_keys or self._pending_keys[key] <= now:
                return HTMLResponse("""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width">
<style>
  body{background:#07090f;color:#dde3ed;font-family:sans-serif;
       display:flex;align-items:center;justify-content:center;height:100vh;margin:0;text-align:center}
  h2{color:#f87171;margin-bottom:12px}p{color:#5e6a7e;font-size:14px}
</style></head>
<body><div><h2>Link Expired</h2>
<p>Press <strong style="color:#dde3ed">Remote Control</strong> in Zaya to get a new QR code.</p>
</div></body></html>""")

            del self._pending_keys[key]
            tok     = secrets.token_urlsafe(32)
            self._tokens[tok] = now + 86400.0
            self._token_keys[tok] = key
            self._aes_key(key)
            dev_tok, device_id = self._pair_browser_device(key)

            if self._connect_callback:
                self._connect_callback()
            asyncio.create_task(self.broadcast(
                {"type": "sys", "text": "Remote connection established via QR code."}
            ))

            return HTMLResponse(f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width">
<style>
  body{{background:#07090f;color:#dde3ed;font-family:sans-serif;
       display:flex;align-items:center;justify-content:center;height:100vh;margin:0;text-align:center}}
  p{{color:#5e6a7e;font-size:14px}}
</style></head>
<body>
<script>
  sessionStorage.setItem('zaya_token','{tok}');
  sessionStorage.setItem('jarvis_token','{tok}');
  sessionStorage.setItem('zaya_key','{key}');
  sessionStorage.setItem('jarvis_key','{key}');
  localStorage.setItem('zaya_device_token','{dev_tok}');
  localStorage.setItem('jarvis_device_token','{dev_tok}');
  localStorage.setItem('zaya_device_id','{device_id}');
  localStorage.setItem('jarvis_device_id','{device_id}');
  setTimeout(function(){{location.replace('/')}},400);
</script>
<p>Connecting to Zaya…</p>
</body></html>""")

        @app.post("/api/device-login")
        async def device_login_ep(req: Request):
            """Fresh auth token for a device paired earlier.

            Paired devices survive a Zaya restart (they are rows in the local
            SQLite store, not dict entries), so a phone or browser that was
            trusted yesterday reconnects by itself after the laptop reboots."""
            try:
                body = await req.json()
            except Exception:
                return JSONResponse({"ok": False}, status_code=400)
            dev_tok  = (body.get("device_token") or "").strip()
            device_id = (body.get("device_id") or "").strip()
            if not dev_tok:
                return JSONResponse({"ok": False}, status_code=401)

            session_key = None
            if device_id:
                session_key = self.device_registry().session_key_for(device_id, dev_tok)
            if session_key is None and dev_tok in self._device_sessions:
                # Legacy client that only ever stored its device token.
                session_key = self._device_sessions[dev_tok]["session_key"]
            if not session_key:
                return JSONResponse({"ok": False}, status_code=401)

            tok = secrets.token_urlsafe(32)
            self._tokens[tok] = time.time() + 86400.0
            self._token_keys[tok] = session_key
            self._aes_key(session_key)
            if self._connect_callback:
                self._connect_callback()
            asyncio.create_task(self.broadcast(
                {"type": "sys", "text": "Known device reconnected automatically."}
            ))
            return JSONResponse({"ok": True, "token": tok, "key": session_key,
                                 "device_id": device_id})

        def _pair_browser_device(session_key: str) -> tuple[str, str]:
            """Register this browser as a durable paired device.

            Its device secret is the local browser token, so the record can be
            authenticated later while the store keeps only a hash of it."""
            dev_tok = secrets.token_urlsafe(32)
            try:
                record, _secret = self.device_registry().pair(
                    "Web browser", app_version="browser", platform="web",
                    session_key=session_key, secret=dev_tok)
                return dev_tok, record["device_id"]
            except Exception:
                # Storage failure must not cost the owner their remote session.
                self._device_sessions[dev_tok] = {"session_key": session_key}
                return dev_tok, ""

        @app.post("/api/revoke-devices")
        async def revoke_devices(req: Request):
            """Invalidate every persistent device token (admin action)."""
            if not _auth(req):
                return JSONResponse({"error": "Unauthorized"}, status_code=401)
            count = len(self._device_sessions) + len(self._tokens)
            self._device_sessions.clear()
            self._tokens.clear()
            self._token_keys.clear()
            self._aes_cache.clear()
            try:
                count += self.device_registry().revoke_all()
            except Exception:
                pass
            if self._mobile:
                await self._mobile.revoke_all()
            return JSONResponse({"ok": True, "revoked": count})

        @app.post("/api/command")
        async def command(req: Request):
            if not _auth(req):
                return JSONResponse({"error": "Unauthorized"}, status_code=401)
            body  = await req.json()
            token = req.headers.get("authorization", "").removeprefix("Bearer ").strip()
            enc   = body.get("enc", "")
            if enc:
                text = self._decrypt(token, enc)
                if text is None:
                    return JSONResponse({"error": "Decryption failed"}, status_code=400)
            else:
                if token in self._token_keys:
                    return JSONResponse({"error": "Encrypted command required for secure session"}, status_code=400)
                text = (body.get("text") or "").strip()
            if text:
                self.submit_remote_command(text, source="dashboard",
                                           request_id=str(body.get("request_id") or ""))
                if self._wake_callback:
                    self._wake_callback()
            return JSONResponse({"ok": True})

        @app.post("/api/wake")
        async def wake_ep(req: Request):
            if not _auth(req):
                return JSONResponse({"error": "Unauthorized"}, status_code=401)
            if self._wake_callback:
                self._wake_callback()
            return JSONResponse({"ok": True})

        # ── Phone mic real-time audio → Gemini Live ──────────────────────────

        @app.websocket("/ws/phone-audio")
        async def phone_audio_ws(websocket: WebSocket, token: str = ""):
            tok = token.strip()
            if not _valid_token(tok):
                await websocket.close(code=4001)
                return
            await websocket.accept()
            asyncio.create_task(self.broadcast(
                {"type": "sys", "text": "Phone microphone live."}
            ))
            try:
                while True:
                    data = await websocket.receive_bytes()
                    try:
                        self._phone_audio_queue.put_nowait(
                            {"data": data, "mime_type": "audio/pcm"}
                        )
                    except asyncio.QueueFull:
                        # Drop the frame rather than block the socket: Zaya's own
                        # session must never pay for a phone that cannot keep up.
                        self._phone_audio_dropped += 1
            except WebSocketDisconnect:
                pass
            finally:
                asyncio.create_task(self.broadcast(
                    {"type": "sys", "text": "Phone microphone stopped."}
                ))

        # ── File sharing ──────────────────────────────────────────────────────

        def _safe_filename(raw: str) -> str:
            name = Path(raw).name                          # strip path components
            name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', name).strip(". ")
            return name or "upload"

        if _UPLOAD_OK:
            @app.post("/api/upload")
            async def upload_file(req: Request, file: UploadFile = FastAPIFile(...)):
                if not _auth(req):
                    return JSONResponse({"error": "Unauthorized"}, status_code=401)

                safe = _safe_filename(file.filename or "upload")
                dest = self._uploads_dir / safe
                stem, suffix = Path(safe).stem, Path(safe).suffix
                counter = 1
                while dest.exists():
                    dest = self._uploads_dir / f"{stem}_{counter}{suffix}"
                    counter += 1

                size = 0
                max_bytes = MAX_UPLOAD_MB * 1024 * 1024
                try:
                    with open(dest, "wb") as fout:
                        while True:
                            chunk = await file.read(65536)
                            if not chunk:
                                break
                            size += len(chunk)
                            if size > max_bytes:
                                fout.close()
                                dest.unlink(missing_ok=True)
                                return JSONResponse(
                                    {"error": f"File too large (max {MAX_UPLOAD_MB} MB)"},
                                    status_code=413,
                                )
                            fout.write(chunk)
                except Exception as exc:
                    try:
                        dest.unlink(missing_ok=True)
                    except Exception:
                        pass
                    return JSONResponse({"error": str(exc)}, status_code=500)

                asyncio.create_task(self.broadcast({
                    "type": "file_received",
                    "name": dest.name,
                    "size": size,
                    "saved_to": str(self._uploads_dir),
                }))
                return JSONResponse({"ok": True, "name": dest.name, "size": size})
        else:
            @app.post("/api/upload")
            async def upload_unavailable(req: Request):
                return JSONResponse(
                    {"error": "File uploads require: pip install python-multipart"},
                    status_code=503,
                )

        @app.get("/api/files")
        async def list_files(req: Request):
            if not _auth(req):
                return JSONResponse({"error": "Unauthorized"}, status_code=401)
            files = []
            try:
                for f in sorted(
                    (p for p in self._uploads_dir.iterdir() if p.is_file()),
                    key=lambda p: p.stat().st_mtime,
                    reverse=True,
                ):
                    files.append({"name": f.name, "size": f.stat().st_size})
            except Exception:
                pass
            return JSONResponse({"files": files})

        @app.get("/uploads/{filename}")
        async def download_file(filename: str, token: str = ""):
            # Auth via query param — browser <a download> can't send custom headers
            tok = token.strip()
            if not _valid_token(tok):
                return JSONResponse({"error": "Unauthorized"}, status_code=401)
            safe = re.sub(r'[/\\]', '', filename)
            path = self._uploads_dir / safe
            if not path.exists() or not path.is_file():
                return JSONResponse({"error": "Not found"}, status_code=404)
            return FileResponse(str(path), filename=safe)

        @app.websocket("/ws")
        async def ws_ep(websocket: WebSocket, token: str = ""):
            tok = token.strip()
            if not _valid_token(tok):
                await websocket.close(code=4001)
                return
            await websocket.accept()
            self._clients.add(websocket)
            for entry in self._history[-50:]:
                try:
                    await websocket.send_json(entry)
                except Exception:
                    break
            try:
                while True:
                    data = await websocket.receive_json()
                    if data.get("type") == "command":
                        enc = data.get("enc", "")
                        t   = self._decrypt(tok, enc) if enc else (data.get("text") or "").strip()
                        if t:
                            self.submit_remote_command(
                                t, source="dashboard",
                                request_id=str(data.get("request_id") or ""))
                            if self._wake_callback:
                                self._wake_callback()
            except WebSocketDisconnect:
                pass
            finally:
                self._clients.discard(websocket)

        # ── Android companion ─────────────────────────────────────────────────

        mobile = self.mobile()
        mobile.register(app)

        @app.websocket("/ws/mobile")
        async def mobile_ws(websocket: WebSocket, token: str = ""):
            await self.mobile().handle_mobile_socket(websocket, token.strip())

        @app.websocket("/ws/phone-output")
        async def phone_output_ws(websocket: WebSocket, token: str = ""):
            await self.mobile().handle_phone_output(websocket, token.strip())

        return app

    # ── remote command intake ────────────────────────────────────────────

    def submit_remote_command(self, text: str, *, source: str = "dashboard",
                              request_id: str = "") -> tuple[object, str]:
        """Queue a remote command exactly once, with its own owner scope.

        Every transport funnels through here so the dedupe rules and the
        acknowledgement lifecycle are identical for the browser dashboard and
        the Android app. Returns (command, 'accepted' | 'duplicate' | 'rejected').
        """
        from core.remote_commands import get_gate
        command, outcome = get_gate().submit(text, request_id=request_id, source=source,
                                            trust="authenticated_remote_owner")
        if outcome != 'accepted' or command is None:
            return command, outcome
        try:
            self._command_queue.put_nowait({
                "text": command.text, "request_id": command.request_id,
                "source": source, "scope": command.scope,
            })
        except asyncio.QueueFull:
            get_gate().complete(command.request_id, ok=False, error="Zaya was busy.")
            return command, "rejected"
        return command, outcome

    # ── serve ─────────────────────────────────────────────────────────────

    async def _serve_alias(self) -> None:
        """Second HTTPS server on PORT+1 sharing the same app and in-memory state.
        Chrome HTTPS-upgrades any bare IP:PORT the user types, so this port also needs TLS.
        User types IP:8001 → Chrome tries https → self-signed cert warning → accept once → done."""
        ssl_key  = BASE_DIR / "config" / "certs" / "zaya.key"
        ssl_cert = BASE_DIR / "config" / "certs" / "zaya.crt"
        asyncio.get_event_loop().run_in_executor(None, _ensure_network_access, PORT + 1)
        cfg = uvicorn.Config(
            self.app, host="0.0.0.0", port=PORT + 1, log_level="warning",
            ssl_keyfile=str(ssl_key), ssl_certfile=str(ssl_cert),
        )
        print(f"[Dashboard] Manual entry:  {self._ip}:{PORT + 1}  (type in browser, accept cert once)")
        try:
            await uvicorn.Server(cfg).serve()
        except (asyncio.CancelledError, KeyboardInterrupt):
            pass

    async def serve(self) -> None:
        if not _DEPS_OK:
            print("[Dashboard] fastapi/uvicorn not installed — dashboard disabled.")
            print("[Dashboard] Run:  pip install fastapi 'uvicorn[standard]' cryptography")
            return

        # The mobile bridge fans events in from worker threads, so it needs the
        # loop that actually owns the sockets.
        self._loop = asyncio.get_running_loop()
        try:
            self.mobile().loop = self._loop
        except Exception as error:
            print(f"[Dashboard] Mobile API unavailable: {error}")

        # Firewall setup runs in a thread — uvicorn starts immediately,
        # no waiting for UAC dialogs or subprocess timeouts.
        asyncio.get_event_loop().run_in_executor(None, _ensure_network_access, PORT)

        # Generate the TLS pair on first run so no private key ships in the repo.
        # Skipped when the owner has asked for plain HTTP (see dashboard_https):
        # regenerating it there would silently put the phone back behind TLS.
        if _dashboard_https_setting() != "off":
            _ensure_certs()

        use_ssl  = self._ssl_enabled()
        ssl_key  = BASE_DIR / "config" / "certs" / "zaya.key"
        ssl_cert = BASE_DIR / "config" / "certs" / "zaya.crt"

        if use_ssl:
            asyncio.create_task(self._serve_alias())

        cfg = uvicorn.Config(
            self.app, host="0.0.0.0", port=PORT, log_level="warning",
            **({"ssl_keyfile": str(ssl_key), "ssl_certfile": str(ssl_cert)} if use_ssl else {}),
        )

        proto = "https" if use_ssl else "http"
        print(f"[Dashboard] {proto}://{self._ip}:{PORT}")
        print("[Dashboard] Press 'Remote Control' in Zaya UI to get the QR code.")
        print("[Dashboard] Android companion: enter this address and the same pairing key.")
        await uvicorn.Server(cfg).serve()
