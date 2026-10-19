"""Mobile companion endpoints: pairing, events, voice, tasks, WhatsApp, files.

Registered onto the existing FastAPI app by dashboard/server.py. Nothing here
starts a server of its own — the phone talks to the same Zaya process, the same
runtime, the same Gemini session and the same WhatsApp automation as the desktop.

Three transports, deliberately separate:

    /api/mobile/*        request/response: pairing, tasks, inbox, files
    /ws/mobile           JSON events up and down, plus phone-mic PCM frames
    /ws/phone-output     Zaya's own PCM voice down to the phone speaker

They are separate sockets because they fail differently. A wedged audio stream
must not take the control channel with it, and a control reconnect must not
interrupt a voice call.

Security posture (unchanged from the rest of Zaya, only extended):

  * a phone is usable only after an owner-issued one-time pairing key, and keeps
    a per-device secret that is stored as a hash on the laptop;
  * transport is TLS (Tailscale or the dashboard certificate) over OkHttp;
  * every payload is bounded before it reaches the wire;
  * contact messages are data on the phone — the inbox endpoints are read-only
    except for owner mode switches, and no inbound message text can ever reach
    the command queue through these routes.
"""
from __future__ import annotations

import asyncio
import logging
import queue
import re
import time
from collections import deque
from pathlib import Path

from fastapi import Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse

try:                                              # phone uploads are optional
    from fastapi import File as FastAPIFile, UploadFile
    try:
        import python_multipart  # noqa: F401  FastAPI >= 0.113
    except Exception:                         # pragma: no cover - old FastAPI
        import multipart  # noqa: F401
    _MULTIPART_OK = True
except Exception:                                 # pragma: no cover - import guard
    _MULTIPART_OK = False

from core import mobile_protocol as protocol
from core.mobile_bridge import get_bridge
from core.mobile_calls import get_call_manager
from core.remote_commands import get_gate

log = logging.getLogger(__name__)

# Mirrors main.py's SEND_SAMPLE_RATE / RECEIVE_SAMPLE_RATE. Kept as plain numbers
# so this module never imports the Qt application; tests assert they agree.
PHONE_UP_RATE = 16000      # phone microphone  → Zaya
PHONE_DOWN_RATE = 24000    # Zaya's voice      → phone speaker

MAX_WS_FRAME = protocol.MAX_FRAME_BYTES
EVENT_QUEUE = 200
MAX_UPLOAD_MB = 500
TOKEN_TTL = 7 * 24 * 3600
MAX_TRACKED_TOKENS = 500


def _safe_filename(raw: str) -> str:
    """Same rule as the dashboard's own upload: a name, never a path."""
    name = Path(raw).name
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', name).strip('. ')
    return name or 'upload'



class RateLimiter:
    """Small sliding-window limiter. Used for pairing and login attempts."""

    def __init__(self, limit: int, window: float, clock=time.time) -> None:
        self.limit, self.window, self._clock = int(limit), float(window), clock
        self._hits: dict[str, deque] = {}

    def allow(self, key: str) -> bool:
        now = self._clock()
        hits = self._hits.setdefault(key, deque())
        while hits and now - hits[0] > self.window:
            hits.popleft()
        if len(hits) >= self.limit:
            return False
        hits.append(now)
        if len(self._hits) > 2000:            # bounded memory under a scan
            for stale in [k for k, v in self._hits.items() if not v or now - v[-1] > self.window]:
                self._hits.pop(stale, None)
        return True


class MobileSession:
    """One `/ws/mobile` connection: a bounded event queue and a writer task."""

    def __init__(self, api: 'MobileApi', ws: WebSocket, device: dict, token: str) -> None:
        self.api, self.ws, self.device, self.token = api, ws, device, token
        self.queue: asyncio.Queue = asyncio.Queue(maxsize=EVENT_QUEUE)
        self.dropped = 0
        self.sent = 0
        self.alive = True
        self.capabilities: dict = {}
        self.audio_output = False
        self.closed_at = 0.0

    # called from any thread (event bus, timer, audio path)
    def enqueue(self, envelope: dict) -> None:
        loop = self.api.loop
        if loop is None or not self.alive:
            return

        def push() -> None:
            try:
                self.queue.put_nowait(envelope)
            except asyncio.QueueFull:
                # A phone that cannot keep up loses old events, never Zaya's
                # session. The client resyncs its state on reconnect anyway.
                self.dropped += 1

        try:
            loop.call_soon_threadsafe(push)
        except RuntimeError:
            self.alive = False

    async def send_loop(self) -> None:
        while self.alive:
            envelope = await self.queue.get()
            try:
                await asyncio.wait_for(self.ws.send_json(envelope), timeout=10.0)
                self.sent += 1
            except Exception:
                self.alive = False
                break

    def info(self) -> dict:
        return {'device_id': self.device.get('device_id', ''), 'sent': self.sent,
                'dropped': self.dropped, 'queue': self.queue.qsize(),
                'app_version': self.device.get('app_version', '')}


class MobileApi:
    SERVER_NAME = 'Zaya'

    def __init__(self, server) -> None:
        self.server = server
        self.loop: asyncio.AbstractEventLoop | None = None
        self.sessions: set[MobileSession] = set()
        self.tokens: dict[str, dict] = {}
        self.limiter = RateLimiter(limit=20, window=60.0)
        self.audio_seconds = 0.0
        self.audio_frames = 0
        self.bridge = get_bridge()
        self.calls = get_call_manager()
        self.video_frames = queue.Queue(maxsize=1)
        self._last_video = ('', 0.0)
        self.gate = get_gate()
        self._detach_sink = self.bridge.add_sink(self.push, name='mobile')
        self._started_at = time.time()
        self._registry_ready = True
        try:
            self.devices = self.server.device_registry()
        except Exception as error:                      # keep the dashboard usable
            log.warning('Paired-device storage unavailable: %s', error)
            self._registry_ready = False
            self.devices = None

    # ── fan-out ──────────────────────────────────────────────────────────────

    def push(self, envelope: dict) -> None:
        """Bridge sink. Runs on whatever thread published the event."""
        for session in list(self.sessions):
            session.enqueue(envelope)

    def broadcast(self, type_: str, payload: dict | None = None) -> int:
        return self.bridge.emit(protocol.envelope(type_, payload))

    def session_infos(self) -> list[dict]:
        return [session.info() for session in self.sessions]

    def stats(self) -> dict:
        return {'sessions': len(self.sessions), 'tokens': len(self.tokens),
                'audio_listeners': self.bridge.audio_listener_count(),
                'audio_frames': self.audio_frames,
                'audio_seconds': round(self.audio_seconds, 2),
                'uptime': round(time.time() - self._started_at, 1)}

    # ── tokens & device auth ─────────────────────────────────────────────────

    def issue_token(self, device: dict) -> str:
        import secrets
        token = secrets.token_urlsafe(32)
        now = time.time()
        self.tokens[token] = {
            'device_id': device.get('device_id', ''),
            'device_name': device.get('device_name', ''),
            'created_at': now,
            'seen_at': now,
        }
        self._prune_tokens(now)
        return token

    def _prune_tokens(self, now: float) -> None:
        for token, entry in list(self.tokens.items()):
            if now - float(entry.get('seen_at', 0)) > TOKEN_TTL:
                self.tokens.pop(token, None)
        while len(self.tokens) > MAX_TRACKED_TOKENS:
            oldest = min(self.tokens.items(), key=lambda item: item[1].get('seen_at', 0))
            self.tokens.pop(oldest[0], None)

    def device_for_token(self, token: str) -> dict | None:
        token = (token or '').strip()
        entry = self.tokens.get(token)
        if not entry:
            return None
        now = time.time()
        if now - float(entry.get('seen_at', 0)) > TOKEN_TTL:
            self.tokens.pop(token, None)
            return None
        entry['seen_at'] = now
        device = self.devices.get(entry['device_id']) if self.devices else None
        if device is None:
            return None
        if device.get('revoked'):
            self.tokens.pop(token, None)
            return None
        return device

    def owner_authorized(self, request: Request) -> bool:
        """The dashboard's own owner token: used for device administration."""
        token = request.headers.get('authorization', '').removeprefix('Bearer ').strip()
        return bool(token) and token in self.server._tokens

    def _device_from_request(self, request: Request) -> dict | None:
        token = (request.headers.get('authorization', '').removeprefix('Bearer ').strip()
                 or request.query_params.get('token', '').strip())
        return self.device_for_token(token)

    @staticmethod
    def _client_ip(request: Request) -> str:
        return (request.client.host if request.client else '') or ''

    # ── pairing / login ──────────────────────────────────────────────────────

    def register(self, app) -> None:
        @app.post('/api/mobile/pair')
        async def mobile_pair(request: Request):
            if not self.limiter.allow(f'pair:{self._client_ip(request)}'):
                return JSONResponse({'ok': False, 'error': 'Too many attempts. Wait a minute.'},
                                    status_code=429)
            try:
                body = await request.json()
            except Exception:
                return JSONResponse({'ok': False, 'error': 'Invalid request'}, status_code=400)
            key = str(body.get('key') or '').strip().upper()
            now = time.time()
            pending = self.server._pending_keys.get(key)
            if not key or pending is None or pending <= now:
                return JSONResponse({'ok': False, 'error': 'Invalid or expired pairing key'},
                                    status_code=401)
            if not self._registry_ready or self.devices is None:
                return JSONResponse({'ok': False, 'error': 'Device storage unavailable'},
                                    status_code=503)
            del self.server._pending_keys[key]        # one-time use, like the QR flow
            record, secret = self.devices.pair(
                str(body.get('device_name') or 'Android device')[:80],
                app_version=str(body.get('app_version') or '')[:40],
                platform=str(body.get('platform') or 'android')[:40],
                ip=self._client_ip(request))
            token = self.issue_token(record)
            self.server.note_remote_connection('Android companion paired.')
            return JSONResponse({
                'ok': True,
                'device_id': record['device_id'],
                'device_secret': secret,
                'token': token,
                'protocol_version': protocol.PROTOCOL_VERSION,
                'server_name': self.SERVER_NAME,
                'audio': {'uplink_rate': PHONE_UP_RATE, 'downlink_rate': PHONE_DOWN_RATE,
                          'channels': 1, 'encoding': 'pcm16'},
            })

        @app.post('/api/mobile/login')
        async def mobile_login(request: Request):
            if not self.limiter.allow(f'login:{self._client_ip(request)}'):
                return JSONResponse({'ok': False, 'error': 'Too many attempts. Wait a minute.'},
                                    status_code=429)
            try:
                body = await request.json()
            except Exception:
                return JSONResponse({'ok': False, 'error': 'Invalid request'}, status_code=400)
            device_id = str(body.get('device_id') or '').strip()
            secret = str(body.get('device_secret') or '')
            if not self._registry_ready or self.devices is None:
                return JSONResponse({'ok': False, 'error': 'Device storage unavailable'},
                                    status_code=503)
            locked = self.devices.locked(device_id)
            if locked > 0:
                return JSONResponse({'ok': False, 'error': 'Device temporarily locked',
                                     'retry_after': int(locked)}, status_code=429)
            record = self.devices.authenticate(device_id, secret)
            if record is None:
                return JSONResponse({'ok': False, 'error': 'Authentication failed'},
                                    status_code=401)
            self.devices.touch(device_id, app_version=str(body.get('app_version') or '')[:40],
                               platform=str(body.get('platform') or 'android')[:40],
                               ip=self._client_ip(request))
            record = self.devices.get(device_id) or record
            token = self.issue_token(record)
            self.server.note_remote_connection('Known device reconnected.')
            return JSONResponse({'ok': True, 'token': token, 'device_id': device_id,
                                 'protocol_version': protocol.PROTOCOL_VERSION,
                                 'server_name': self.SERVER_NAME,
                                 'audio': {'uplink_rate': PHONE_UP_RATE,
                                           'downlink_rate': PHONE_DOWN_RATE,
                                           'channels': 1, 'encoding': 'pcm16'}})

        # ── device administration (owner only) ───────────────────────────────

        @app.get('/api/mobile/devices')
        async def mobile_devices(request: Request):
            if not self.owner_authorized(request):
                return JSONResponse({'error': 'Unauthorized'}, status_code=401)
            if not self._registry_ready or self.devices is None:
                return JSONResponse({'devices': [], 'available': False})
            return JSONResponse({'devices': self.devices.list(include_revoked=True),
                                 'sessions': self.session_infos(), 'available': True})

        @app.post('/api/mobile/revoke')
        async def mobile_revoke(request: Request):
            try:
                body = await request.json()
            except Exception:
                body = {}
            target = str(body.get('device_id') or '').strip()
            if not self._registry_ready or self.devices is None:
                return JSONResponse({'ok': False, 'error': 'Device storage unavailable'},
                                    status_code=503)
            owner = self.owner_authorized(request)
            device = self._device_from_request(request)
            if not owner:
                # A device may always revoke itself; nothing else.
                if device is None or device['device_id'] != target:
                    return JSONResponse({'error': 'Unauthorized'}, status_code=401)
            if not target:
                return JSONResponse({'ok': False, 'error': 'device_id required'}, status_code=400)
            removed = self.devices.revoke(target)
            for token, entry in list(self.tokens.items()):
                if entry.get('device_id') == target:
                    self.tokens.pop(token, None)
            for session in list(self.sessions):
                if session.device.get('device_id') == target:
                    session.alive = False
            self.server.note_remote_connection('A paired device was revoked.')
            return JSONResponse({'ok': True, 'revoked': bool(removed)})

        # ── read-only state for the phone's first paint ──────────────────────

        @app.get('/api/mobile/state')
        async def mobile_state(request: Request):
            device = self._device_from_request(request)
            if device is None:
                return JSONResponse({'error': 'Unauthorized'}, status_code=401)
            return JSONResponse(self.snapshot())

        @app.get('/api/mobile/tasks')
        async def mobile_tasks(request: Request):
            device = self._device_from_request(request)
            if device is None:
                return JSONResponse({'error': 'Unauthorized'}, status_code=401)
            return JSONResponse({'tasks': self.tasks()})

        @app.post('/api/mobile/output')
        async def mobile_output(request: Request):
            device = self._device_from_request(request)
            if device is None:
                return JSONResponse({'error': 'Unauthorized'}, status_code=401)
            try:
                body = await request.json()
            except Exception:
                return JSONResponse({'ok': False, 'error': 'Invalid request'}, status_code=400)
            try:
                target = self.bridge.set_output_target(str(body.get('target') or ''))
            except ValueError as error:
                return JSONResponse({'ok': False, 'error': str(error)}, status_code=400)
            return JSONResponse({'ok': True, 'target': target})

        # ── WhatsApp (read-only views + owner mode switches) ─────────────────

        @app.get('/api/mobile/whatsapp')
        async def mobile_whatsapp(request: Request, action: str = 'status', chat: str = '',
                                  query: str = '', limit: int = 15):
            device = self._device_from_request(request)
            if device is None:
                return JSONResponse({'error': 'Unauthorized'}, status_code=401)
            if action not in {'status', 'recent', 'unread', 'important', 'conversation', 'search'}:
                return JSONResponse({'error': 'Unsupported action'}, status_code=400)
            try:
                result = await asyncio.get_running_loop().run_in_executor(
                    None, self._whatsapp_query, action, chat, query, limit)
            except Exception as error:
                return JSONResponse({'ok': False, 'error': f'WhatsApp unavailable: {error}'},
                                    status_code=503)
            return JSONResponse({'ok': True, 'action': action, 'result': result})

        @app.post('/api/mobile/whatsapp/mode')
        async def mobile_whatsapp_mode(request: Request):
            device = self._device_from_request(request)
            if device is None:
                return JSONResponse({'error': 'Unauthorized'}, status_code=401)
            try:
                body = await request.json()
            except Exception:
                return JSONResponse({'ok': False, 'error': 'Invalid request'}, status_code=400)
            chat_id = str(body.get('chat_id') or '').strip()
            mode = str(body.get('mode') or '').strip().lower()
            try:
                result = await asyncio.get_running_loop().run_in_executor(
                    None, self._set_whatsapp_mode, chat_id, mode)
            except Exception as error:
                return JSONResponse({'ok': False, 'error': str(error)}, status_code=400)
            return JSONResponse({'ok': True, 'result': result})

        # ── files ────────────────────────────────────────────────────────────

        @app.get('/api/mobile/files')
        async def mobile_files(request: Request):
            device = self._device_from_request(request)
            if device is None:
                return JSONResponse({'error': 'Unauthorized'}, status_code=401)
            folder = Path(self.server._uploads_dir)
            files = []
            try:
                for entry in sorted((p for p in folder.iterdir() if p.is_file()),
                                    key=lambda p: p.stat().st_mtime, reverse=True)[:200]:
                    stat = entry.stat()
                    files.append({'name': entry.name, 'size': stat.st_size,
                                  'modified': stat.st_mtime})
            except Exception:
                pass
            return JSONResponse({'files': files, 'folder': 'Zaya uploads'})

        @app.get('/api/mobile/download')
        async def mobile_download(request: Request, name: str = ''):
            device = self._device_from_request(request)
            if device is None:
                return JSONResponse({'error': 'Unauthorized'}, status_code=401)
            safe = Path(name).name
            path = Path(self.server._uploads_dir) / safe
            if not safe or not path.is_file():
                return JSONResponse({'error': 'Not found'}, status_code=404)
            return FileResponse(str(path), filename=safe)

        # Phone → laptop uploads. The dashboard's /api/upload only accepts an
        # owner token, which a paired phone deliberately never holds; this route
        # keeps the same folder, naming rule and byte limit but authenticates the
        # device instead, so a phone can hand Zaya a file to work on.
        if _MULTIPART_OK:
            @app.post('/api/mobile/upload')
            async def mobile_upload(request: Request, file: UploadFile = FastAPIFile(...)):
                device = self._device_from_request(request)
                if device is None:
                    return JSONResponse({'error': 'Unauthorized'}, status_code=401)
                folder = Path(self.server._uploads_dir)
                safe = _safe_filename(file.filename or 'upload')
                dest = folder / safe
                stem, suffix = Path(safe).stem, Path(safe).suffix
                counter = 1
                while dest.exists():
                    dest = folder / f'{stem}_{counter}{suffix}'
                    counter += 1
                size = 0
                max_bytes = MAX_UPLOAD_MB * 1024 * 1024
                try:
                    folder.mkdir(parents=True, exist_ok=True)
                    with open(dest, 'wb') as out:
                        while True:
                            chunk = await file.read(65536)
                            if not chunk:
                                break
                            size += len(chunk)
                            if size > max_bytes:
                                out.close()
                                dest.unlink(missing_ok=True)
                                return JSONResponse(
                                    {'error': f'File too large (max {MAX_UPLOAD_MB} MB)'},
                                    status_code=413,
                                )
                            out.write(chunk)
                except Exception as error:
                    try:
                        dest.unlink(missing_ok=True)
                    except Exception:
                        pass
                    return JSONResponse({'error': str(error)}, status_code=500)

                # The desktop's transfer list should show it, exactly like an
                # upload from the dashboard does.
                try:
                    asyncio.create_task(self.server.broadcast({
                        'type': 'file_received',
                        'name': dest.name,
                        'size': size,
                        'saved_to': str(folder),
                    }))
                except Exception:
                    log.debug('file broadcast failed', exc_info=True)
                return JSONResponse({'ok': True, 'name': dest.name, 'size': size})
        else:
            @app.post('/api/mobile/upload')
            async def mobile_upload_unavailable(request: Request):
                device = self._device_from_request(request)
                if device is None:
                    return JSONResponse({'error': 'Unauthorized'}, status_code=401)
                return JSONResponse(
                    {'error': 'File uploads require: pip install python-multipart'},
                    status_code=503,
                )

    # ── data used by both transports ─────────────────────────────────────────

    def tasks(self, limit: int = 60) -> list[dict]:
        try:
            from core.task_runtime import get_runtime
            return [protocol.normalize_task(_as_dict(task))
                    for task in get_runtime().list(limit)]
        except Exception:
            log.debug('task snapshot failed', exc_info=True)
            return []

    def _whatsapp_query(self, action: str, chat: str, query: str, limit: int) -> dict:
        from services.whatsapp.service import get_service
        result = get_service().query(action, chat=chat, query=query, limit=limit)
        return {'status': result.status, 'summary': protocol.clip(result.summary, protocol.LIMITS['detail']),
                'data': _bounded(result.data, 400), 'evidence': result.evidence[:8]}

    def _set_whatsapp_mode(self, chat_id: str, mode: str) -> dict:
        from services.whatsapp.service import get_service
        store = get_service().store
        if chat_id:
            record = store.set_mode(chat_id, mode)
            return {'scope': 'chat', 'chat_id': record.get('chat_id'), 'mode': record.get('mode')}
        return store.set_global_mode(mode)

    def snapshot(self) -> dict:
        state = self.bridge.snapshot()
        active = self.calls.active()
        return {
            'protocol_version': protocol.PROTOCOL_VERSION,
            'server_name': self.SERVER_NAME,
            'state': state['state'],
            'emotion': state['emotion'],
            'caption': state['caption'],
            'output_target': state['output_target'],
            'call_active': state['call_active'],
            'active_call': active.public() if active else None,
            'tasks': self.tasks(20),
            'stats': self.stats(),
            'server_time': time.time(),
        }

    # ── WebSocket: events + commands + phone microphone ──────────────────────

    async def handle_mobile_socket(self, websocket: WebSocket, token: str) -> None:
        device = self.device_for_token(token)
        if device is None:
            await websocket.close(code=4001)
            return
        # The socket runs on the loop that owns it. `serve()` assigns this before
        # uvicorn starts, but an alternate ASGI host (or a test client) may not
        # have done so — and a None loop silently drops every event.
        if self.loop is None:
            self.loop = asyncio.get_running_loop()
        await websocket.accept()
        session = MobileSession(self, websocket, device, token)
        self.sessions.add(session)

        # No per-session bridge sink here: MobileApi already registered one in
        # __init__ that fans out to every session. Adding a second one delivered
        # every state change and chat line to the phone twice.
        writer = asyncio.create_task(session.send_loop())

        try:
            session.enqueue(protocol.envelope('hello', {
                'protocol_version': protocol.PROTOCOL_VERSION,
                'server': self.SERVER_NAME,
                'device_id': device['device_id'],
                'device_name': device.get('device_name', ''),
                'audio': {'uplink_rate': PHONE_UP_RATE, 'downlink_rate': PHONE_DOWN_RATE},
                'snapshot': self.snapshot(),
                'task_states': sorted({'created', 'inspecting', 'planning', 'executing',
                                       'verifying', 'waiting_confirmation', 'waiting_external',
                                       'completed', 'failed', 'cancelled', 'paused'}),
                'priorities': list(protocol.PRIORITY_NAMES.values()),
            }))
            self.server.note_remote_connection('Phone interface connected.')
            while True:
                message = await websocket.receive()
                if message.get('type') == 'websocket.disconnect':
                    break
                data = message.get('bytes')
                if data is not None:
                    self._accept_phone_audio(session, data)
                    continue
                text = message.get('text')
                if text is None:
                    continue
                if len(text) > MAX_WS_FRAME:
                    session.enqueue(protocol.envelope('error', {'error': 'Frame too large'}))
                    continue
                await self._handle_control(session, text)
        except WebSocketDisconnect:
            pass
        except Exception as error:
            log.info('Mobile socket ended: %s', error)
        finally:
            session.alive = False
            writer.cancel()
            self.sessions.discard(session)
            self._socket_closed(session)

    def _accept_phone_audio(self, session: MobileSession, data: bytes) -> None:
        """Phone microphone PCM → the same queue the browser's mic uses."""
        call = self.calls.active()
        if (not data or len(data) > 32768 or len(data) % 2 or call is None
                or call.state != 'answered' or call.device_id != session.device['device_id'] or call.muted):
            return
        queue = self.server._phone_audio_queue
        try:
            queue.put_nowait({'data': bytes(data), 'mime_type': 'audio/pcm', 'call_id': call.call_id,
                             'device_id': call.device_id})
            session.capabilities['mic_frames'] = session.capabilities.get('mic_frames', 0) + 1
        except asyncio.QueueFull:
            session.dropped += 1        # drop rather than block: Zaya's session wins

    async def _handle_control(self, session: MobileSession, raw: str) -> None:
        import json
        try:
            data = json.loads(raw)
        except Exception:
            session.enqueue(protocol.envelope('error', {'error': 'Malformed JSON'}))
            return
        if not isinstance(data, dict):
            return
        kind = str(data.get('type') or '')

        if kind in {'call.video.toggle', 'call.video.frame'}:
            self._call_video(session, data)
            return

        if kind == 'ping':
            session.enqueue(protocol.envelope('pong', {'time': time.time()}))
            return

        if kind == 'hello':
            session.capabilities = {'app_version': str(data.get('app_version') or '')[:40],
                                    'audio_output': bool(data.get('audio_output'))}
            session.enqueue(protocol.envelope('zaya.state',
                                              {'state': self.bridge.state,
                                               'emotion': self.bridge.emotion}))
            return

        if kind == 'command':
            self._submit_command(session, str(data.get('text') or ''),
                                 str(data.get('request_id') or ''))
            return

        if kind == 'output.target':
            try:
                self.bridge.set_output_target(str(data.get('target') or ''))
            except ValueError:
                pass
            return

        if kind in {'call.answer', 'call.decline', 'call.end', 'call.start', 'call.mute'}:
            self._call_control(session, kind, str(data.get('call_id') or ''), data)
            return

        if kind == 'whatsapp.mode':
            chat_id, mode = str(data.get('chat_id') or ''), str(data.get('mode') or '')
            try:
                result = await asyncio.get_running_loop().run_in_executor(
                    None, self._set_whatsapp_mode, chat_id, mode)
                session.enqueue(protocol.envelope('whatsapp.mode', {
                    'mode': result.get('mode', mode), 'chat_id': result.get('chat_id', chat_id),
                    'scope': result.get('scope', 'global')}))
            except Exception as error:
                session.enqueue(protocol.envelope('error', {'error': f'WhatsApp mode refused: {error}'}))
            return

    def _submit_command(self, session: MobileSession, text: str, request_id: str) -> None:
        text = protocol.clip(text, protocol.LIMITS['text'])
        if not text:
            session.enqueue(protocol.envelope('error', {'error': 'Empty command'}))
            return
        command, outcome = self.gate.submit(text, request_id=request_id, source='phone')
        if outcome == 'rejected' or command is None:
            session.enqueue(protocol.envelope('error', {'error': 'Command rejected'}))
            return
        if outcome == 'duplicate':
            # The phone is resending because it never saw the acknowledgement.
            # Answer with the original request's real state; never run it twice.
            session.enqueue(command.envelope())
            return
        try:
            self.server._command_queue.put_nowait({
                'text': command.text, 'request_id': command.request_id,
                'source': 'phone', 'scope': command.scope,
            })
        except asyncio.QueueFull:
            session.enqueue(protocol.envelope('error', {'error': 'Zaya is busy; try again shortly'}))
            return
        if self.server._wake_callback:
            try:
                self.server._wake_callback()
            except Exception:
                log.debug('wake callback failed', exc_info=True)
        session.enqueue(command.envelope())
        self.bridge.emit(protocol.envelope('chat.message', {
            'role': 'user', 'text': command.text, 'request_id': command.request_id,
            'source': 'phone',
        }))

    def _call_video(self, session: MobileSession, data: dict) -> None:
        """A single bounded camera frame, only from the answering phone's opt-in."""
        if data.get('type') not in {'call.video.toggle', 'call.video.frame'}:
            return
        call = self.calls.active()
        if (call is None or call.state != 'answered' or call.call_id != data.get('call_id')
                or call.device_id != session.device['device_id']):
            return
        if data.get('type') == 'call.video.toggle':
            self.calls.set_video(call.call_id, call.device_id, data.get('enabled'))
            self._last_video = ('', 0.0)
            while not self.video_frames.empty():
                try:
                    self.video_frames.get_nowait()
                except queue.Empty:
                    break
            return
        if not call.video_enabled:
            return
        now = time.monotonic()
        if self._last_video[0] == call.call_id and now - self._last_video[1] < .8:
            return
        import base64
        import binascii
        import io
        from PIL import Image
        encoded = data.get('jpeg')
        if not isinstance(encoded, str) or len(encoded) > 240000:
            return
        try:
            jpeg = base64.b64decode(encoded, validate=True)
            if not jpeg.startswith(b'\xff\xd8') or len(jpeg) > 180000:
                return
            with Image.open(io.BytesIO(jpeg)) as image:
                if image.format != 'JPEG' or image.width * image.height > 1024 * 1024:
                    return
                image.verify()
        except (ValueError, OSError, binascii.Error, Image.DecompressionBombError):
            return
        # The camera decoder can run while another thread ends the call.
        active = self.calls.active()
        if (active is None or active.call_id != call.call_id or active.state != 'answered'
                or active.device_id != session.device['device_id'] or not active.video_enabled):
            return
        self._last_video = (call.call_id, now)
        try:
            self.video_frames.get_nowait()
        except queue.Empty:
            pass
        try:
            self.video_frames.put_nowait({'call_id': call.call_id, 'device_id': call.device_id, 'data': jpeg})
        except queue.Full:
            pass  # Latest-frame delivery is best-effort; never end the control socket.

    def _call_control(self, session: MobileSession, kind: str, call_id: str, data: dict) -> None:
        calls = self.calls
        device_id = session.device['device_id']
        active = calls.active()
        if kind in {'call.end', 'call.mute'}:
            if active is None or active.device_id != device_id or (call_id and call_id != active.call_id):
                return
            call_id = active.call_id
        if kind == 'call.answer':
            if active is not None and active.direction == 'outgoing':
                return  # Only the laptop's delayed answer may connect an outgoing call.
            call = calls.answer(call_id, device_id=device_id)
            if call is None:
                session.enqueue(protocol.envelope('error', {'error': 'That call is no longer ringing'}))
        elif kind == 'call.decline':
            if active is None or active.state != 'ringing' or active.direction != 'incoming':
                return
            if calls.decline(call_id) is None:
                session.enqueue(protocol.envelope('error', {'error': 'That call is no longer ringing'}))
        elif kind == 'call.end':
            calls.end(call_id)
        elif kind == 'call.start':
            # Owner-initiated call from the phone: they are asking to talk now.
            call = calls.dial(device_id)
            if call is None:
                session.enqueue(protocol.envelope('error',
                                                  {'error': 'Zaya could not start the call right now', 'call_start_failed': True}))
        elif kind == 'call.mute':
            calls.set_muted(call_id, device_id, data.get('muted'))
        if kind in {'call.answer', 'call.start'} and getattr(self.server, '_wake_callback', None):
            self.server._wake_callback()

    def _socket_closed(self, session: MobileSession) -> None:
        """Losing the voice socket during a call ends the call: the phone can no
        longer hear Zaya, and a 'call' that is one-way is worse than a clean end."""
        active = self.calls.active()
        if active is not None and active.device_id == session.device['device_id']:
            self.calls.end(active.call_id, outcome='disconnected')
        self.server.note_remote_connection('Phone interface disconnected.')

    # ── WebSocket: Zaya's voice → phone speaker ──────────────────────────────

    async def handle_phone_output(self, websocket: WebSocket, token: str) -> None:
        device = self.device_for_token(token)
        if device is None:
            await websocket.close(code=4001)
            return
        await websocket.accept()
        listener = self.bridge.add_audio_listener(name=f'out:{device["device_id"][:8]}')
        event = asyncio.Event()
        listener.bind(asyncio.get_running_loop(), event)
        await websocket.send_json({'protocol_version': protocol.PROTOCOL_VERSION,
                                   'type': 'audio.start',
                                   'payload': {'sample_rate': PHONE_DOWN_RATE, 'channels': 1,
                                               'encoding': 'pcm16'}})
        try:
            while True:
                try:
                    await asyncio.wait_for(event.wait(), timeout=5.0)
                    event.clear()
                except asyncio.TimeoutError:
                    # Idle. Send a heartbeat: it is the only way to notice a phone
                    # that vanished without a close frame. A dead socket raises,
                    # and the handler then drops its listener instead of keeping
                    # a silent queue forever.
                    await asyncio.wait_for(websocket.send_json({
                        'protocol_version': protocol.PROTOCOL_VERSION,
                        'type': 'audio.ping', 'payload': {'time': time.time()},
                    }), timeout=5.0)
                frames = listener.drain()
                if not frames:
                    continue
                for frame in frames:
                    active = self.calls.active()
                    if active is not None and active.state == 'answered' and active.device_id != device['device_id']:
                        continue
                    await asyncio.wait_for(websocket.send_bytes(frame), timeout=5.0)
                    self.audio_frames += 1
                    self.audio_seconds += len(frame) / 2 / PHONE_DOWN_RATE
                if listener.dropped:
                    log.debug('Phone output dropped %s frames (slow socket)', listener.dropped)
        except asyncio.TimeoutError:
            log.info('Phone output socket stalled; closing it so Zaya is not held back.')
        except WebSocketDisconnect:
            pass
        except Exception as error:
            log.info('Phone output ended: %s', error)
        finally:
            self.bridge.remove_audio_listener(listener)
            active = self.calls.active()
            if active is not None and active.state == 'answered' and active.device_id == device['device_id']:
                self.calls.end(active.call_id, outcome='disconnected')


def _as_dict(task) -> dict:
    from dataclasses import asdict, is_dataclass
    return asdict(task) if is_dataclass(task) else dict(task)


def _bounded(value, limit: int):
    """Clip a WhatsApp result so inbox rows cannot become an unbounded frame."""
    if isinstance(value, dict):
        return {str(key)[:60]: _bounded(item, max(1, limit - 1)) for key, item in list(value.items())[:limit]}
    if isinstance(value, list):
        return [_bounded(item, max(1, limit - 1)) for item in value[:limit]]
    if isinstance(value, str):
        return protocol.clip(value, 2000)
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return protocol.clip(str(value), 2000)
