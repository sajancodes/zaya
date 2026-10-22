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
from typing import Any, Dict, Optional

from fastapi import Cookie, Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("zaya-web")

WEB_ROOT = Path(__file__).resolve().parent
DIST_DIR = WEB_ROOT / "dist"
STATIC_DIR = WEB_ROOT / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info("Zaya database initialized in WAL mode.")
    # Attempt non-blocking release sync from GitHub
    import threading
    threading.Thread(target=sync_releases_from_github, daemon=True, name="ZayaReleaseSync").start()
    yield


app = FastAPI(
    title="Zaya Public Distribution API",
    description="Official distribution, telemetry, and release APIs for Zaya by Sajan Rai.",
    version="0.5.0",
    lifespan=lifespan,
)

# CORS restricted to official production origin and local development hosts
ALLOWED_ORIGINS = [
    "https://zaya.sajan.codes",
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


class AdminLoginPayload(BaseModel):
    username: str
    password: str


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


# ---------------------------------------------------------------------------
# Direct Platform Downloads (Triggers counter & redirects)
# ---------------------------------------------------------------------------
@app.get("/download/windows")
async def download_windows(request: Request):
    client_ip = request.client.host if request.client else None
    rel = get_latest_release("windows")
    version = rel["version"] if rel else "0.5.0"
    url = rel["url"] if rel else "https://github.com/sajancodes/zaya-companion-releases/releases/latest/download/ZayaSetup.exe"

    record_download("windows", version, client_ip)
    return RedirectResponse(url=url, status_code=status.HTTP_302_FOUND)


@app.get("/download/android")
async def download_android(request: Request):
    client_ip = request.client.host if request.client else None
    rel = get_latest_release("android")
    version = rel["version"] if rel else "0.4.6"
    url = rel["url"] if rel else "https://github.com/sajancodes/zaya-companion-releases/releases/latest/download/Zaya-Companion.apk"

    record_download("android", version, client_ip)
    return RedirectResponse(url=url, status_code=status.HTTP_302_FOUND)


# ---------------------------------------------------------------------------
# Release Manifest Endpoints
# ---------------------------------------------------------------------------
@app.get("/api/releases/latest")
async def api_releases_latest(platform: str = "windows"):
    rel = get_latest_release(platform)
    if not rel:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No releases found.")
    return rel


@app.get("/api/releases")
async def api_releases_all():
    return get_all_releases()


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


@app.get("/api/admin/metrics")
async def api_admin_metrics(
    zaya_admin_session: Optional[str] = Cookie(None),
    request: Request = None,
):
    if not is_admin_enabled():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin panel is disabled until an explicit strong ADMIN_PASSWORD is configured in the server environment.",
        )

    # Check session cookie or Bearer token header
    token = zaya_admin_session
    auth_header = request.headers.get("Authorization") if request else None
    if not token and auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()

    if not validate_session(token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    return get_analytics_metrics()


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
    candidate = DIST_DIR / full_path
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
