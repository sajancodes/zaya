"""FastAPI backend server for Zaya public distribution website and telemetry.
Created and developed by Sajan Rai for Zaya.

Serves:
1. React (TSX) single-page application frontend
2. Anonymous telemetry ingestion (/api/telemetry/install, /api/telemetry/heartbeat)
3. Download counters (/api/downloads/event, /download/windows, /download/android)
4. Authenticated owner admin analytics dashboard (/api/admin/metrics)
5. Official release manifests (/api/releases/latest, /api/releases)
6. SEO sitemap and robots.txt
"""
from __future__ import annotations

from contextlib import asynccontextmanager
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional, Literal

from fastapi import Cookie, Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from web.auth import (
    clear_login_failures,
    create_session,
    is_admin_enabled,
    is_login_rate_limited,
    record_login_failure,
    revoke_session,
    validate_session,
    verify_admin_credentials,
)
from web.database import (
    get_all_releases,
    get_analytics_metrics,
    get_latest_release,
    init_db,
    record_download,
    record_heartbeat,
    record_install,
    sync_releases_from_github,
)
from web.telemetry_service import is_rate_limited, validate_telemetry_payload
from web.release_validation import validate_release
from web.shared_limits import RateLimitUnavailable

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("zaya-web")

WEB_ROOT = Path(__file__).resolve().parent
DIST_DIR = WEB_ROOT / "dist"
STATIC_DIR = WEB_ROOT / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        init_db()
    except Exception:
        logger.error('Database not configured; public static pages remain available.')
        yield
        return
    # Attempt non-blocking release sync from GitHub
    import threading
    if os.environ.get('VERCEL'):
        # Serverless runtimes can suspend background work after a response.
        from starlette.concurrency import run_in_threadpool
        await run_in_threadpool(sync_releases_from_github)
    else:
        threading.Thread(target=sync_releases_from_github, daemon=True, name="ZayaReleaseSync").start()
    yield


app = FastAPI(
    title="Zaya Public Distribution API",
    description="Official distribution, telemetry, and release APIs for Zaya by Sajan Rai.",
    version="0.5.0",
    lifespan=lifespan,
)


@app.exception_handler(RateLimitUnavailable)
async def limits_unavailable(request: Request, error: RateLimitUnavailable):
    return JSONResponse({'detail': 'Request protection is temporarily unavailable. Please retry later.'}, status_code=503)

# CORS restricted to official production origin and local development hosts
ALLOWED_ORIGINS = [
    "https://zaya.sajan.codes",
    "https://zayaxyz.vercel.app",
    "https://sajan.codes",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]
extra_origins = os.environ.get("ALLOWED_ORIGINS", "")
if extra_origins:
    ALLOWED_ORIGINS.extend([o.strip() for o in extra_origins.split(",") if o.strip()])

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
)


@app.middleware('http')
async def security_headers(request: Request, call_next):
    if request.url.path.startswith('/api/admin/') and request.method == 'POST':
        origin = request.headers.get('origin')
        if origin and origin not in ALLOWED_ORIGINS and origin != str(request.base_url).rstrip('/'):
            return JSONResponse({'detail': 'Cross-origin administration is forbidden.'}, status_code=403)
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' https://www.googletagmanager.com; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self' https://*.google-analytics.com; frame-ancestors 'none'; base-uri 'self'; object-src 'none'"
    if request.url.path.startswith('/api/admin/'):
        response.headers['Cache-Control'] = 'no-store'
    return response


def downloadable_release(platform, channel='stable'):
    if platform not in ('windows', 'linux', 'android') or channel not in ('stable', 'beta'):
        raise HTTPException(400, 'Unsupported platform or release channel.')
    rel = get_latest_release(platform, channel=channel)
    if not rel:
        raise HTTPException(404, 'No verified release is published for this platform/channel.')
    try:
        return validate_release(rel)
    except (TypeError, ValueError):
        raise HTTPException(503, 'Release metadata is not ready for distribution.')


@app.get('/api/downloads/beta/{platform}/{package}')
async def beta_package_download(platform: str, package: str):
    """Count the advertised beta download request, then redirect to its immutable asset."""
    import json
    from urllib.parse import urlparse
    if (platform, package) not in {('windows', 'exe'), ('linux', 'deb'), ('linux', 'rpm'), ('linux', 'portable')}:
        raise HTTPException(404, 'Unsupported beta package.')
    metadata = json.loads((Path(__file__).parent / 'src' / 'data' / ('windowsBeta.json' if platform == 'windows' else 'linuxBeta.json')).read_text(encoding='utf-8'))
    if not metadata.get('published'):
        raise HTTPException(404, 'Beta is not available.')
    item = metadata if platform == 'windows' else next((p for p in metadata.get('packages', []) if p['format'] == package), None)
    if item is None:
        raise HTTPException(404, 'Package is not available.')
    url = item['url']
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.netloc != 'github.com' or not parsed.path.startswith('/sajancodes/zaya-companion-releases/releases/download/') or parsed.query or parsed.fragment:
        raise HTTPException(503, 'Package metadata is invalid.')
    try:
        record_download(platform, metadata['version'])
    except Exception:
        # Analytics outages must never prevent downloading the app.
        pass
    return RedirectResponse(url, status_code=302, headers={'Cache-Control': 'no-store'})


# ---------------------------------------------------------------------------
# Telemetry Pydantic Models
# ---------------------------------------------------------------------------
class TelemetryPayload(BaseModel):
    installation_id: str = Field(..., min_length=10, max_length=64)
    platform: str = Field(..., min_length=2, max_length=20)
    version: str = Field(..., min_length=1, max_length=30)


class DownloadEventPayload(BaseModel):
    platform: str = Field(..., min_length=2, max_length=20)
    version: str = Field(..., min_length=1, max_length=30)


class UpdateEventPayload(TelemetryPayload):
    model_config = {'extra': 'forbid'}
    event_id: str = Field(..., min_length=36, max_length=36)
    stage: Literal['available', 'download_verified', 'installer_started', 'failed']
    target_version: Optional[str] = Field(None, min_length=1, max_length=30)


class AdminLoginPayload(BaseModel):
    username: str
    password: str


class ReleaseActivation(BaseModel):
    active: bool


class CatalogSyncPayload(BaseModel):
    model_config = {'extra':'forbid'}
    tag: str = Field(..., min_length=6, max_length=80)


@app.post('/api/internal/releases/sync')
async def release_catalog_sync(payload: CatalogSyncPayload, request: Request):
    header = request.headers.get('authorization', '')
    if not header.startswith('Bearer '):
        raise HTTPException(401, 'Release workflow authentication required.')
    if is_rate_limited(request.client.host if request.client else 'unknown'):
        raise HTTPException(429, 'Rate limit exceeded.')
    from web.release_identity import authenticate
    try:
        authenticate(header[7:], payload.tag)
    except PermissionError:
        raise HTTPException(401, 'Release workflow authentication required.')
    from starlette.concurrency import run_in_threadpool
    try:
        return await run_in_threadpool(sync_releases_from_github, strict=True, tag=payload.tag)
    except Exception:
        raise HTTPException(503, 'Verified release catalog synchronization did not complete.')


@app.get('/api/admin/releases')
async def admin_releases(request: Request, zaya_admin_session: Optional[str] = Cookie(None)):
    if not is_admin_enabled() or not validate_session(zaya_admin_session):
        raise HTTPException(401, 'Administrator authentication required.')
    return get_all_releases()


@app.post('/api/admin/releases/{platform}/{version}')
async def admin_release_activation(platform: str, version: str, payload: ReleaseActivation,
                                   request: Request, zaya_admin_session: Optional[str] = Cookie(None)):
    if not is_admin_enabled() or not validate_session(zaya_admin_session):
        raise HTTPException(401, 'Administrator authentication required.')
    from web.database import firebase_enabled
    if not firebase_enabled():
        raise HTTPException(503, 'Release management requires the production Firebase backend.')
    from web.firebase_store import set_release_active
    if not any(row['version'] == version and row['platform'] == platform for row in get_all_releases()):
        raise HTTPException(404, 'Release not found.')
    set_release_active(version, platform, payload.active)
    return {'status': 'ok', 'active': payload.active}


# ---------------------------------------------------------------------------
# Telemetry Endpoints
# ---------------------------------------------------------------------------
@app.post("/api/telemetry/install", status_code=status.HTTP_201_CREATED)
async def api_telemetry_install(payload: TelemetryPayload, request: Request):
    client_ip = request.client.host if request.client else "unknown"
    if is_rate_limited(client_ip):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded.")

    data = payload.model_dump()
    valid, msg = validate_telemetry_payload(data)
    if not valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)

    is_unique = record_install(data["installation_id"], data["platform"], data["version"])
    return {"status": "ok", "unique_install": is_unique}


@app.post("/api/telemetry/heartbeat")
async def api_telemetry_heartbeat(payload: TelemetryPayload, request: Request):
    client_ip = request.client.host if request.client else "unknown"
    if is_rate_limited(client_ip):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded.")

    data = payload.model_dump()
    valid, msg = validate_telemetry_payload(data)
    if not valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)

    record_heartbeat(data["installation_id"], data["platform"], data["version"])
    return {"status": "ok"}


@app.post("/api/downloads/event")
async def api_download_event(payload: DownloadEventPayload, request: Request):
    client_ip = request.client.host if request.client else "unknown"
    if is_rate_limited(client_ip):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded.")

    platform = payload.platform.lower().strip()
    if platform not in ("windows", "android", "linux"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid platform.")

    record_download(platform, payload.version.strip(), client_ip)
    return {"status": "ok"}


@app.post('/api/telemetry/update')
async def api_update_event(payload: UpdateEventPayload, request: Request):
    from web.database import firebase_enabled
    from web.telemetry_service import UUID_PATTERN, VERSION_PATTERN
    if is_rate_limited(request.client.host if request.client else 'unknown'):
        raise HTTPException(429, 'Rate limit exceeded.')
    valid, message = validate_telemetry_payload(payload.model_dump())
    if not valid or not UUID_PATTERN.fullmatch(payload.event_id) or (payload.target_version is not None and not VERSION_PATTERN.fullmatch(payload.target_version)):
        raise HTTPException(400, 'Invalid update event metadata.')
    if not firebase_enabled():
        raise HTTPException(503, 'Update health requires the configured production backend.')
    from web.firebase_store import record_update_event
    recorded = record_update_event(payload.event_id, payload.platform, payload.target_version, payload.stage)
    return {'status':'ok', 'recorded':recorded}


# ---------------------------------------------------------------------------
# Direct Platform Downloads (Triggers counter & redirects)
# ---------------------------------------------------------------------------
@app.get("/download/windows")
async def download_windows(request: Request):
    client_ip = request.client.host if request.client else None
    rel = downloadable_release('windows', request.query_params.get('channel', 'stable'))
    version, url = rel['version'], rel['url']

    record_download("windows", version, client_ip)
    return RedirectResponse(url=url, status_code=status.HTTP_302_FOUND)


@app.get("/download/android")
async def download_android(request: Request):
    client_ip = request.client.host if request.client else None
    rel = downloadable_release('android', request.query_params.get('channel', 'stable'))
    version, url = rel['version'], rel['url']

    record_download("android", version, client_ip)
    return RedirectResponse(url=url, status_code=status.HTTP_302_FOUND)


# ---------------------------------------------------------------------------
# Release Manifest Endpoints
# ---------------------------------------------------------------------------
@app.get("/api/releases/latest")
async def api_releases_latest(platform: str = "windows", channel: str = 'stable'):
    return downloadable_release(platform, channel)


@app.get("/api/releases")
async def api_releases_all():
    releases = []
    for item in get_all_releases():
        try:
            if item.get('active', True):
                releases.append(validate_release(item))
        except (ValueError, TypeError):
            continue
    return releases


@app.get('/download/linux')
async def download_linux(request: Request):
    rel = downloadable_release('linux', request.query_params.get('channel', 'stable'))
    record_download('linux', rel['version'])
    return RedirectResponse(rel['url'], status_code=302)


@app.get('/api/updates/desktop')
async def desktop_update_manifest(channel: str = 'stable'):
    rel = downloadable_release('windows', channel)
    if int(rel.get('build', 0)) <= 0:
        raise HTTPException(503, 'Desktop build metadata is unavailable.')
    return {**{k: rel[k] for k in ('version', 'build', 'filename', 'url', 'sha256', 'size')},
            'channel': channel, 'schema': 1}


# ---------------------------------------------------------------------------
# Admin Authentication & Analytics Dashboard Endpoints
# ---------------------------------------------------------------------------
@app.post("/api/admin/login")
async def api_admin_login(payload: AdminLoginPayload, request: Request, response: Response):
    client_ip = request.client.host if request.client else "unknown"
    if is_login_rate_limited(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts. Please wait 5 minutes before trying again.",
        )

    if not is_admin_enabled():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin panel is disabled until an explicit strong ADMIN_PASSWORD (minimum 12 characters) is configured in the server environment.",
        )

    if not verify_admin_credentials(payload.username, payload.password):
        record_login_failure(client_ip)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials.")

    clear_login_failures(client_ip)
    token = create_session(payload.username)
    secure_cookie = os.environ.get("SECURE_COOKIE", "true").lower() != "false"
    response.set_cookie(
        key="zaya_admin_session",
        value=token,
        httponly=True,
        secure=secure_cookie,
        max_age=7 * 86400,
        samesite="lax",
    )
    return {"status": "ok", "message": "Authenticated"}


@app.post("/api/admin/logout")
async def api_admin_logout(response: Response, zaya_admin_session: Optional[str] = Cookie(None)):
    if zaya_admin_session:
        revoke_session(zaya_admin_session)
    response.delete_cookie(key="zaya_admin_session")
    return {"status": "ok", "message": "Logged out"}


def _require_admin(request, token):
    if not is_admin_enabled():
        raise HTTPException(503, 'Admin panel is disabled until an explicit strong ADMIN_PASSWORD is configured in the server environment.')
    auth_header = request.headers.get('Authorization') if request else None
    if not token and auth_header and auth_header.startswith('Bearer '):
        token = auth_header[7:].strip()
    if not validate_session(token):
        raise HTTPException(401, 'Unauthorized')


@app.get('/api/admin/metrics')
async def api_admin_metrics(zaya_admin_session: Optional[str] = Cookie(None), request: Request = None):
    _require_admin(request, zaya_admin_session)
    return get_analytics_metrics()


@app.post('/api/site-events', status_code=204)
async def site_events(request: Request):
    from pydantic import ValidationError
    from starlette.concurrency import run_in_threadpool
    from web.site_analytics import SiteEvent, sanitize, record_event, is_rate_limited as site_limit
    if request.headers.get('DNT') == '1' or request.headers.get('Sec-GPC') == '1':
        return Response(status_code=204)
    origin = request.headers.get('Origin')
    if origin and origin not in {*ALLOWED_ORIGINS, str(request.base_url).rstrip('/')}:
        raise HTTPException(403, 'Unexpected origin.')
    client_ip = request.client.host if request.client else 'unknown'
    if await run_in_threadpool(site_limit, client_ip):
        raise HTTPException(429, 'Rate limit exceeded.')
    raw = bytearray()
    async for chunk in request.stream():
        if len(raw) + len(chunk) > 2048:
            raise HTTPException(413, 'Event too large.')
        raw.extend(chunk)
    try:
        event = sanitize(SiteEvent.model_validate_json(bytes(raw)), request.headers.get('User-Agent', ''))
    except (ValueError, ValidationError):
        raise HTTPException(400, 'Invalid analytics event.') from None
    await run_in_threadpool(record_event, event)
    return Response(status_code=204)


@app.get('/api/admin/site-analytics')
def site_analytics_report(request: Request, days: int = 30, zaya_admin_session: Optional[str] = Cookie(None)):
    from web.site_analytics import report
    _require_admin(request, zaya_admin_session)
    if days not in (7, 30, 90):
        raise HTTPException(422, 'Choose 7, 30 or 90 days.')
    return report(days)


# ---------------------------------------------------------------------------
# SEO & Static Files
# ---------------------------------------------------------------------------
@app.get("/robots.txt")
async def robots_txt():
    content = (
        "User-agent: *\n"
        "Disallow: /admin\n"
        "Disallow: /api/\n"
        "Allow: /\n\n"
        "Sitemap: https://zaya.sajan.codes/sitemap.xml\n"
    )
    return Response(content=content, media_type="text/plain")


@app.get("/sitemap.xml")
async def sitemap_xml():
    routes = [
        "",
        "download",
        "features",
        "docs/getting-started",
        "docs/install/windows",
        "docs/install/android",
        "docs/install/source",
        "docs/voice",
        "docs/providers",
        "docs/local-ai",
        "docs/computer-control",
        "docs/browser",
        "docs/vision",
        "docs/perception",
        "docs/hand-control",
        "docs/air-keyboard",
        "docs/spatial",
        "docs/memory",
        "docs/missions",
        "docs/coding",
        "docs/whatsapp",
        "docs/mobile",
        "docs/security",
        "docs/privacy",
        "docs/architecture",
        "docs/configuration",
        "docs/troubleshooting",
        "docs/reference",
        "releases",
        "roadmap",
        "privacy",
        "terms",
        "security",
        "about",
    ]
    xml_items = []
    for r in routes:
        loc = f"https://zaya.sajan.codes/{r}".rstrip("/")
        xml_items.append(f"<url><loc>{loc}</loc><changefreq>weekly</changefreq></url>")
    xml_content = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(xml_items)
        + "\n</urlset>"
    )
    return Response(content=xml_content, media_type="application/xml")


# Mount assets directory if React build exists
if (DIST_DIR / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=str(DIST_DIR / "assets")), name="assets")

if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# Catch-all route to serve the React SPA for client-side routing
@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    # If a specific static file exists in dist, serve it
    candidate = (DIST_DIR / full_path).resolve()
    if not candidate.is_relative_to(DIST_DIR.resolve()):
        raise HTTPException(404, 'Not found')
    if full_path and candidate.is_file():
        return FileResponse(str(candidate))

    # Otherwise serve index.html for React SPA
    index_file = DIST_DIR / "index.html"
    if index_file.is_file():
        return FileResponse(str(index_file))

    # Fallback to minimal welcome message if build not yet compiled
    return Response(
        content="Zaya web server online. Run 'npm run build' in web/ to compile React frontend.",
        media_type="text/plain",
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("web.server:app", host="127.0.0.1", port=8000, reload=True)
