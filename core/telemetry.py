"""Anonymous installation and heartbeat telemetry for Zaya.
Created and developed by Sajan Rai for Zaya.

Privacy Guarantees:
- Cryptographically random UUIDv4 installation ID only.
- ZERO hardware fingerprinting (no MAC address, CPU, disk, motherboard, or IP derivation).
- ZERO personal data, conversations, keys, audio, screen captures, or activity content.
- Respects the user's telemetry toggle in settings/onboarding.
- Lightweight daily heartbeat sent at most once every 24 hours.
"""
from __future__ import annotations

import json
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
from core.version import VERSION

logger = logging.getLogger(__name__)

DEFAULT_TELEMETRY_BASE_URL = os.environ.get(
    "ZAYA_TELEMETRY_URL",
    os.environ.get("ZAYA_WEBSITE_URL", "https://zaya.sajan.codes")
).rstrip("/")

HEARTBEAT_INTERVAL_SECONDS = 86400  # 24 hours


def _installation_file_path() -> Path:
    user_data = get_user_data_dir()
    user_data.mkdir(parents=True, exist_ok=True)
    return user_data / "installation.json"


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
                        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
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
        "telemetry_enabled": True,
        "install_reported": False,
        "last_heartbeat": 0,
    }
    try:
        path.write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
    except Exception as e:
        logger.debug(f"Could not write installation.json: {e}")
    return info


def is_telemetry_enabled() -> bool:
    """Return whether the user has opted in to anonymous analytics."""
    info = get_or_create_installation_info()
    return bool(info.get("telemetry_enabled", True))


def set_telemetry_enabled(enabled: bool) -> None:
    """Update the user's anonymous telemetry preference."""
    path = _installation_file_path()
    info = get_or_create_installation_info()
    info["telemetry_enabled"] = bool(enabled)
    try:
        path.write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
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
        "version": info.get("installed_version", VERSION),
    }

    success = _post_json(endpoint, payload)
    if success:
        info["install_reported"] = True
        try:
            _installation_file_path().write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
        except Exception:
            pass
    return success


def report_heartbeat_event(base_url: Optional[str] = None, force: bool = False) -> bool:
    """Send a lightweight daily active heartbeat if >= 24h have elapsed."""
    if not is_telemetry_enabled():
        return False

    info = get_or_create_installation_info()
    now = int(time.time())
    last = int(info.get("last_heartbeat", 0))

    if not force and (now - last < HEARTBEAT_INTERVAL_SECONDS):
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
            _installation_file_path().write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
        except Exception:
            pass
    return success


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

        def _worker():
            # Initial delayed check (10 seconds after launch) so startup is instantaneous
            if self._stop_event.wait(10):
                return

            try:
                report_install_event(self.base_url)
                report_heartbeat_event(self.base_url)
            except Exception as e:
                logger.debug(f"Telemetry worker initial pass error: {e}")

            # Periodic check every 6 hours to catch 24h threshold
            while not self._stop_event.wait(6 * 3600):
                try:
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
