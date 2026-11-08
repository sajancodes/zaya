"""Optional loopback renderer service. Never accepts system commands from a page."""
import asyncio
import secrets
import socket
import threading
from contextlib import suppress
from pathlib import Path

def _resolve_renderer_root():
    from core.runtime_paths import get_resource_dir, get_app_root
    for candidate in (
        get_resource_dir() / 'spatial_renderer' / 'dist',
        get_app_root() / 'spatial_renderer' / 'dist',
        Path(__file__).resolve().parents[1] / 'spatial_renderer' / 'dist'
    ):
        if candidate.is_dir():
            return candidate
    return Path(__file__).resolve().parents[1] / 'spatial_renderer' / 'dist'

ROOT = _resolve_renderer_root()
_lock=threading.Lock()
_server=None
_thread=None
_url=''


def make_app(session,token):
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect
    from fastapi.staticfiles import StaticFiles
    from starlette.middleware.trustedhost import TrustedHostMiddleware
    from core.spatial.spatial_protocol import ClientProtocol
    app=FastAPI(docs_url=None,redoc_url=None,openapi_url=None)
    app.add_middleware(TrustedHostMiddleware,allowed_hosts=['127.0.0.1','localhost'])

    @app.middleware('http')
    async def isolate_assets(request,call_next):
        response=await call_next(request)
        response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self' 'wasm-unsafe-eval'; connect-src 'self' ws://127.0.0.1:* ws://localhost:*; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; worker-src 'self' blob:; object-src 'none'"
        response.headers['Referrer-Policy']='no-referrer'
        response.headers['X-Content-Type-Options']='nosniff'
        return response

    @app.get('/assets/{bundle_id}/{name}')
    async def get_asset(bundle_id:str,name:str):
        import re
        from fastapi import Response,HTTPException
        if not re.fullmatch(r'[a-f0-9]{32}', bundle_id) or not re.fullmatch(r'[\w\-.]+', name) or '..' in name:
            raise HTTPException(400, 'Invalid asset identifier')
        from core.spatial.asset_import import resource
        value=resource(bundle_id,name)
        if value is None:
            raise HTTPException(404)
        return Response(value[0],media_type=value[1],headers={'Cache-Control':'private, max-age=600','X-Content-Type-Options':'nosniff'})

    @app.websocket('/ws')
    async def connect(ws:WebSocket):
        origin=ws.headers.get('origin','')
        expected='http://'+ws.headers.get('host','')
        if not secrets.compare_digest(ws.query_params.get('token',''),token) or (origin and origin!=expected):
            await ws.close(code=1008);return
        loop=asyncio.get_running_loop();queue=asyncio.Queue(maxsize=32)
        def enqueue(packet):
            def push():
                if queue.full():
                    # Latest authoritative snapshot heals dropped intermediate updates.
                    while not queue.empty():
                        queue.get_nowait()
                    from core.spatial.spatial_protocol import envelope
                    queue.put_nowait(envelope('scene.patch',session.session_id,packet['sequence'],session.snapshot()))
                else:
                    queue.put_nowait(packet)
            loop.call_soon_threadsafe(push)
        with session.lock:
            if len(session.listeners)>=2:
                await ws.close(code=1013);return
            await ws.accept()
            session.listeners.add(enqueue);session.renderer_connected=True
            session.publish('scene.create',session.snapshot())
        protocol=ClientProtocol(session.session_id)
        async def send():
            while True:
                await ws.send_json(await queue.get())
        sender=asyncio.create_task(send())
        try:
            while True:
                message=protocol.accept(await ws.receive_text())
                if message['type']=='selection.changed':
                    session.select(message['payload'].get('ids'))
                elif message['type']=='view.changed':
                    session.set_view(message['payload'])
                elif message['type']=='renderer.metrics':
                    session.metrics(message['payload'])
                elif message['type']=='part.manipulated':
                    from core.gesture.controller import hands
                    from core.gesture.gesture_state import InteractionMode
                    if hands.mode!=InteractionMode.SPATIAL or hands.tracker.state!='ACTIVE':
                        raise ValueError('Hand manipulation is not owner-enabled.')
                    session.manipulate(message['payload'])
        except (WebSocketDisconnect,ValueError,TypeError,RuntimeError):
            try:
                await ws.close()
            except RuntimeError:
                pass
        finally:
            sender.cancel()
            with suppress(asyncio.CancelledError):
                await sender
            with session.lock:
                session.listeners.discard(enqueue);session.renderer_connected=bool(session.listeners)
    if ROOT.is_dir():
        app.mount('/',StaticFiles(directory=str(ROOT),html=True),name='renderer')
    return app


def start():
    global _server,_thread,_url
    with _lock:
        if _thread and _thread.is_alive():
            return _url
        if not (ROOT/'index.html').is_file():
            raise RuntimeError('Build spatial_renderer with npm install and npm run build first.')
        import uvicorn
        from core.spatial.spatial_session import session
        token=secrets.token_urlsafe(32)
        sock=socket.socket();sock.bind(('127.0.0.1',0));sock.listen(16)
        port=sock.getsockname()[1]
        app=make_app(session,token)
        _server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=port,access_log=False,log_level='error',ws_max_size=512_000))
        _thread=threading.Thread(target=lambda:_server.run(sockets=[sock]),daemon=True,name='ZayaSpatial')
        _thread.start();_url=f'http://127.0.0.1:{port}/#{token}'
        return _url


def stop():
    global _server,_thread,_url
    with _lock:
        if _server is not None:
            try:
                from core.spatial.spatial_session import session
                session.save()
            except Exception:
                pass
            _server.should_exit = True
        if _thread is not None:
            _thread.join(3)
        _server = None
        _thread = None
        _url = ''
