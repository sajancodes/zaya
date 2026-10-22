"""Windows desktop update checker, verifier and installer.
Created and developed by Sajan Rai for Zaya.

Enforces strict manifest validation, HTTPS, approved GitHub host, file size,
SHA-256 verification and atomic staging before any installer execution.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable, Optional

from core.version import VERSION, BUILD, CHANNEL
from core.runtime_paths import get_update_dir

APPROVED_HOST = "github.com"
APPROVED_REPO_PATH = "/sajancodes/zaya-companion-releases/"
DEFAULT_MANIFEST_URL = "https://github.com/sajancodes/zaya-companion-releases/releases/latest/download/desktop-update.json"
MAX_INSTALLER_SIZE = 500 * 1024 * 1024  # 500 MB max
MAX_MANIFEST_SIZE = 64 * 1024  # 64 KB max


class UpdateStatus(str, Enum):
    IDLE = "IDLE"
    CHECKING = "CHECKING"
    UP_TO_DATE = "UP_TO_DATE"
    AVAILABLE = "AVAILABLE"
    DOWNLOADING = "DOWNLOADING"
    READY = "READY"
    FAILED = "FAILED"


@dataclass(frozen=True)
class DesktopUpdateManifest:
    schema: int
    channel: str
    version: str
    build: int
    filename: str
    url: str
    sha256: str
    size: int

    @classmethod
    def parse(cls, data: dict | str) -> DesktopUpdateManifest:
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except Exception as e:
                raise ValueError(f"Malformed update manifest JSON: {e}") from e

        if not isinstance(data, dict):
            raise ValueError("Update manifest must be a JSON object.")

        schema = int(data.get("schema", 0))
        if schema != 1:
            raise ValueError(f"Unsupported update manifest schema: {schema}")

        channel = str(data.get("channel", "stable")).strip().lower()
        version = str(data.get("version", "")).strip()
        if not re.match(r"^[0-9]+\.[0-9]+(\.[0-9]+)?(-[0-9A-Za-z.]+)?$", version):
            raise ValueError(f"Invalid manifest version format: {version}")

        build = int(data.get("build", 0))
        if build <= 0:
            raise ValueError(f"Invalid manifest build number: {build}")

        filename = str(data.get("filename", "")).strip()
        if filename != "Zaya-Setup.exe":
            raise ValueError(f"Unexpected installer filename: {filename}")

        url = str(data.get("url", "")).strip()
        parsed_url = urllib.parse.urlparse(url)
        if parsed_url.scheme != "https":
            raise ValueError(f"Update URL must be HTTPS: {url}")
        if parsed_url.netloc.lower() != APPROVED_HOST or APPROVED_REPO_PATH not in parsed_url.path:
            raise ValueError(f"Update URL host/path not approved: {url}")

        sha256 = str(data.get("sha256", "")).strip().lower()
        if not re.match(r"^[0-9a-f]{64}$", sha256):
            raise ValueError(f"Invalid SHA-256 hash in manifest: {sha256}")

        size = int(data.get("size", 0))
        if not (1024 < size <= MAX_INSTALLER_SIZE):
            raise ValueError(f"Invalid installer size in manifest: {size}")

        return cls(
            schema=schema,
            channel=channel,
            version=version,
            build=build,
            filename=filename,
            url=url,
            sha256=sha256,
            size=size
        )


def verify_authenticode_signature(file_path: Path, expected_publisher: Optional[str] = None) -> bool:
    """Verify Authenticode code signature on Windows if configured."""
    if os.name != "nt":
        return True

    # If code signing is not yet enforced or certificate is unconfigured, return True
    if os.environ.get("ZAYA_REQUIRE_AUTHENTICODE") != "1":
        return True

    try:
        cmd = [
            "powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
            f"(Get-AuthenticodeSignature -LiteralPath '{file_path}').Status.ToString()"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        status = result.stdout.strip()
        if status != "Valid":
            return False

        if expected_publisher:
            cmd_subj = [
                "powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
                f"(Get-AuthenticodeSignature -LiteralPath '{file_path}').SignerCertificate.Subject"
            ]
            res_subj = subprocess.run(cmd_subj, capture_output=True, text=True, timeout=15)
            if expected_publisher.lower() not in res_subj.stdout.lower():
                return False

        return True
    except Exception:
        return False


class DesktopUpdater:
    """Manages update checking, downloading, verifying, and execution."""

    def __init__(self, manifest_url: str = DEFAULT_MANIFEST_URL):
        self.manifest_url = manifest_url
        self.status = UpdateStatus.IDLE
        self.available_manifest: Optional[DesktopUpdateManifest] = None
        self.ready_installer: Optional[Path] = None
        self.error_message: str = ""
        self.download_progress: int = 0
        self.listeners: list[Callable[[UpdateStatus, str], None]] = []
        self._lock = threading.Lock()
        self._check_timer: Optional[threading.Timer] = None
        self.last_check_time: float = 0

    def add_listener(self, callback: Callable[[UpdateStatus, str], None]) -> None:
        if callback not in self.listeners:
            self.listeners.append(callback)

    def _set_status(self, status: UpdateStatus, message: str = "") -> None:
        self.status = status
        self.error_message = message if status == UpdateStatus.FAILED else ""
        for callback in list(self.listeners):
            try:
                callback(status, message)
            except Exception:
                pass

    def check(self, force: Boolean = False) -> Optional[DesktopUpdateManifest]:
        """Check for updates synchronously (call from background thread)."""
        now = time.monotonic()
        if not force and (now - self.last_check_time < 3600):
            return self.available_manifest

        with self._lock:
            self._set_status(UpdateStatus.CHECKING, "Checking for updates...")
            self.last_check_time = now

            try:
                req = urllib.request.Request(
                    self.manifest_url,
                    headers={"User-Agent": f"Zaya-Desktop/{VERSION} (build {BUILD})"}
                )
                with urllib.request.urlopen(req, timeout=15) as resp:
                    if resp.status == 404:
                        self._set_status(UpdateStatus.UP_TO_DATE, "No updates published yet.")
                        return None
                    raw_data = resp.read(MAX_MANIFEST_SIZE + 1)
                    if len(raw_data) > MAX_MANIFEST_SIZE:
                        raise ValueError("Manifest exceeded permitted size limit.")

                manifest = DesktopUpdateManifest.parse(raw_data.decode("utf-8"))

                # Check if build/version is newer than current
                is_newer = (manifest.build > BUILD) or (
                    manifest.build == BUILD and manifest.version != VERSION
                )

                if is_newer:
                    self.available_manifest = manifest
                    self._set_status(UpdateStatus.AVAILABLE, f"Version {manifest.version} is available.")
                    return manifest
                else:
                    self.available_manifest = None
                    self._set_status(UpdateStatus.UP_TO_DATE, f"Zaya v{VERSION} is up to date.")
                    return None

            except Exception as e:
                self.available_manifest = None
                self._set_status(UpdateStatus.FAILED, f"Update check failed: {e}")
                return None

    def download(self, progress_callback: Optional[Callable[[int, int], None]] = None) -> Optional[Path]:
        """Download and verify update installer (call from background thread)."""
        manifest = self.available_manifest
        if not manifest:
            self._set_status(UpdateStatus.FAILED, "No update available to download.")
            return None

        with self._lock:
            self._set_status(UpdateStatus.DOWNLOADING, f"Downloading Zaya v{manifest.version}...")
            self.download_progress = 0

            updates_dir = get_update_dir()
            updates_dir.mkdir(parents=True, exist_ok=True)
            target_installer = updates_dir / "Zaya-Setup.exe"
            temp_installer = updates_dir / "Zaya-Setup.exe.tmp"

            try:
                req = urllib.request.Request(
                    manifest.url,
                    headers={"User-Agent": f"Zaya-Desktop/{VERSION}"}
                )
                sha = hashlib.sha256()
                received = 0

                with urllib.request.urlopen(req, timeout=60) as resp:
                    total_size = int(resp.headers.get("Content-Length", manifest.size))
                    if total_size != manifest.size:
                        raise ValueError(f"Content-Length ({total_size}) does not match manifest size ({manifest.size}).")

                    with temp_installer.open("wb") as out:
                        while True:
                            chunk = resp.read(65536)
                            if not chunk:
                                break
                            received += len(chunk)
                            if received > manifest.size:
                                raise ValueError("Downloaded data exceeded declared installer size.")
                            sha.update(chunk)
                            out.write(chunk)

                            pct = int((received * 100) / manifest.size) if manifest.size else 0
                            self.download_progress = pct
                            if progress_callback:
                                progress_callback(received, manifest.size)

                if received != manifest.size:
                    raise ValueError(f"Downloaded bytes ({received}) did not match expected size ({manifest.size}).")

                # Verify SHA-256
                digest = sha.hexdigest().lower()
                if digest != manifest.sha256:
                    raise ValueError(f"SHA-256 mismatch: got {digest}, expected {manifest.sha256}")

                # Verify Authenticode signature if required
                if not verify_authenticode_signature(temp_installer, "Sajan Rai"):
                    raise ValueError("Windows Authenticode signature verification failed.")

                # Atomic rename
                temp_installer.replace(target_installer)
                self.ready_installer = target_installer
                self._set_status(UpdateStatus.READY, f"Zaya v{manifest.version} is ready to install.")
                return target_installer

            except Exception as e:
                if temp_installer.exists():
                    temp_installer.unlink(missing_ok=True)
                self.ready_installer = None
                self._set_status(UpdateStatus.FAILED, f"Download verification failed: {e}")
                return None

    def apply_update(self, restart: bool = True, silent: bool = True) -> bool:
        """Launch the verified installer and exit Zaya."""
        if not self.ready_installer or not self.ready_installer.is_file():
            self._set_status(UpdateStatus.FAILED, "No verified update installer is ready.")
            return False

        try:
            cmd = [str(self.ready_installer)]
            if silent:
                # Inno Setup silent install parameters
                cmd.extend(["/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"])

            # Spawn installer as detached process
            flags = subprocess.DETACHED_PROCESS if os.name == "nt" else 0
            subprocess.Popen(cmd, creationflags=flags)

            if restart:
                sys.exit(0)
            return True
        except Exception as e:
            self._set_status(UpdateStatus.FAILED, f"Could not launch installer: {e}")
            return False

    def start_background_poller(self, interval_seconds: int = 6 * 3600) -> None:
        """Periodically check for updates in a background daemon thread."""
        def poll():
            try:
                self.check()
            finally:
                self._check_timer = threading.Timer(interval_seconds, poll)
                self._check_timer.daemon = True
                self._check_timer.start()

        # Initial check delayed by 15 seconds so startup is never blocked
        self._check_timer = threading.Timer(15, poll)
        self._check_timer.daemon = True
        self._check_timer.start()


# Global updater singleton
desktop_updater = DesktopUpdater()
