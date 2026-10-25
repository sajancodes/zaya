"""Anonymous installation and heartbeat telemetry for Zaya.
Created and developed by Sajan Rai for Zaya.

Privacy Guarantees:
- Cryptographically random UUIDv4 installation ID only.
- ZERO hardware fingerprinting (no MAC address, CPU, disk, motherboard, or IP derivation).
- ZERO personal data, conversations, keys, audio, screen captures, or activity content.
- Respects the user's telemetry toggle in settings/onboarding.
- Opt-in activity reported at most once per UTC day after acknowledgement.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from functools import wraps
import logging
import os
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from core.runtime_paths import get_user_data_dir
from core.version import VERSION, semver_key

logger = logging.getLogger(__name__)

DEFAULT_TELEMETRY_BASE_URL = os.environ.get(
    "ZAYA_TELEMETRY_URL",
    os.environ.get("ZAYA_WEBSITE_URL", "https://zayaxyz.vercel.app")
).rstrip("/")

HEARTBEAT_INTERVAL_SECONDS = 120  # Local checks only; no repeated successful daily requests.
_STATE_LOCK = threading.RLock()


def _serialized(function):
    @wraps(function)
    def locked(*args, **kwargs):
        with _STATE_LOCK:
            return function(*args, **kwargs)
    return locked


def _save_info(info):
    path = _installation_file_path()
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _utc_day(timestamp):
    return datetime.fromtimestamp(timestamp, timezone.utc).date()



def _installation_file_path() -> Path:
    user_data = get_user_data_dir()
    user_data.mkdir(parents=True, exist_ok=True)
    return user_data / "installation.json"


@_serialized
def get_or_create_installation_info() -> Dict[str, Any]:
    """Retrieve or initialize the anonymous installation metadata.

    Guarantees that updates to Zaya preserve the original installation_id
    and never increment unique user counts.
    """
    path = _installation_file_path()
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "installation_id" in data:
                # Update current version if application was upgraded
                if data.get("current_version") != VERSION:
                    data["current_version"] = VERSION
                    try:
                        _save_info(data)
                    except Exception:
                        pass
                return data
        except Exception as e:
            logger.debug(f"Could not load existing installation.json: {e}")

    # Generate fresh cryptographically random UUIDv4
    random_id = str(uuid.uuid4())
    info = {
        "installation_id": random_id,
        "platform": "windows" if sys.platform == "win32" else "android" if "android" in sys.platform else "linux",
        "installed_version": VERSION,
        "current_version": VERSION,
        "installed_at": int(time.time()),
        "telemetry_enabled": False,
        "install_reported": False,
        "last_heartbeat": 0,
    }
    try:
        _save_info(info)
    except Exception as e:
        logger.debug(f"Could not write installation.json: {e}")
    return info


def is_telemetry_enabled() -> bool:
    """Return whether the user has opted in to anonymous analytics."""
    info = get_or_create_installation_info()
    return bool(info.get("telemetry_enabled", False))


@_serialized
def set_telemetry_enabled(enabled: bool) -> None:
    """Update the user's anonymous telemetry preference."""
    path = _installation_file_path()
    info = get_or_create_installation_info()
    info["telemetry_enabled"] = bool(enabled)
    try:
        _save_info(info)
    except Exception as e:
        logger.debug(f"Could not save telemetry preference: {e}")


def _post_json(url: str, payload: Dict[str, Any], timeout_seconds: float = 5.0) -> bool:
    """Post JSON payload to backend with short timeout."""
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "User-Agent": f"Zaya-Client/{VERSION} ({payload.get('platform', 'unknown')})",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
            return resp.status in (200, 201, 204)
    except Exception as e:
        logger.debug(f"Telemetry request to {url} failed: {e}")
        return False


@_serialized
def report_install_event(base_url: Optional[str] = None) -> bool:
    """Report anonymous first-install event once.

    Does nothing if telemetry is disabled or install was already reported.
    """
    if not is_telemetry_enabled():
        return False

    info = get_or_create_installation_info()
    if info.get("install_reported"):
        return True

    server = (base_url or DEFAULT_TELEMETRY_BASE_URL).rstrip("/")
    endpoint = f"{server}/api/telemetry/install"
    payload = {
        "installation_id": info["installation_id"],
        "platform": info["platform"],
        "version": VERSION,
    }

    sent_at = int(time.time())
    success = _post_json(endpoint, payload)
    if success:
        info["install_reported"] = True
        info["last_heartbeat"] = sent_at
        try:
            _save_info(info)
        except Exception:
            pass
    return success


@_serialized
def report_heartbeat_event(base_url: Optional[str] = None, force: bool = False) -> bool:
    """Report activity once per UTC day; failures remain retryable.

    force is retained for callers but never bypasses a successful daily receipt.
    """
    if not is_telemetry_enabled():
        return False

    info = get_or_create_installation_info()
    now = int(time.time())
    last = int(info.get("last_heartbeat", 0))

    if last and _utc_day(now) == _utc_day(last):
        return True

    server = (base_url or DEFAULT_TELEMETRY_BASE_URL).rstrip("/")
    endpoint = f"{server}/api/telemetry/heartbeat"
    payload = {
        "installation_id": info["installation_id"],
        "platform": info["platform"],
        "version": VERSION,
    }

    success = _post_json(endpoint, payload)
    if success:
        info["last_heartbeat"] = now
        try:
            _save_info(info)
        except Exception:
            pass
    return success


def report_update_event(stage: str, target_version: Optional[str] = None, base_url: Optional[str] = None) -> bool:
    """Best-effort update health; no URLs, exceptions, paths or message content."""
    if target_version is not None:
        try:
            if not isinstance(target_version, str) or len(target_version) > 30:
                return False
            semver_key(target_version)
        except (TypeError, ValueError):
            return False
    if stage not in {'available', 'download_verified', 'installer_started', 'failed'} or not is_telemetry_enabled():
        return False
    info = get_or_create_installation_info()
    payload = {'installation_id': info['installation_id'], 'platform': info['platform'], 'version': VERSION,
               'event_id': str(uuid.uuid4()), 'stage': stage, 'target_version': target_version}
    return _post_json((base_url or DEFAULT_TELEMETRY_BASE_URL).rstrip('/') + '/api/telemetry/update', payload)


class TelemetryClient:
    """Background manager for Zaya installation and heartbeat telemetry."""

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = (base_url or DEFAULT_TELEMETRY_BASE_URL).rstrip("/")
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        """Start the background telemetry thread without blocking startup."""
        if self._thread is not None and self._thread.is_alive():
            return

        self._stop_event.clear()

        def _worker():
            # Initial delayed check (10 seconds after launch) so startup is instantaneous
            if self._stop_event.wait(10):
                return

            try:
                if report_install_event(self.base_url):
                    report_heartbeat_event(self.base_url)
            except Exception as e:
                logger.debug(f"Telemetry worker initial pass error: {e}")

            # Check locally for consent changes, offline retries and UTC day rollover.
            while not self._stop_event.wait(HEARTBEAT_INTERVAL_SECONDS):
                try:
                    if report_install_event(self.base_url):
                        report_heartbeat_event(self.base_url)
                except Exception as e:
                    logger.debug(f"Telemetry worker cycle error: {e}")

        self._thread = threading.Thread(target=_worker, name="Zaya-Telemetry", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)


# Global telemetry client instance
telemetry_client = TelemetryClient()
