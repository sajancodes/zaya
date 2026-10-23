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

from core.version import VERSION, BUILD, CHANNEL, semver_key
from core.runtime_paths import get_update_dir

APPROVED_HOST = "github.com"
APPROVED_REPO_PATH = "/sajancodes/zaya-companion-releases/"
DEFAULT_MANIFEST_URL = "https://zayaxyz.vercel.app/api/updates/desktop"
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
        precedence = semver_key(version)
        if channel not in ('stable', 'beta') or (channel == 'stable' and not precedence[3]):
            raise ValueError('Manifest channel/version mismatch.')

        build = int(data.get("build", 0))
        if build <= 0:
            raise ValueError(f"Invalid manifest build number: {build}")

        filename = str(data.get("filename", "")).strip()
        if filename not in ("ZayaSetup.exe", "Zaya-Setup.exe"):
            raise ValueError(f"Unexpected installer filename: {filename}")

        url = str(data.get("url", "")).strip()
        parsed_url = urllib.parse.urlparse(url)
        if parsed_url.scheme != "https":
            raise ValueError(f"Update URL must be HTTPS: {url}")
        if parsed_url.netloc.lower() != APPROVED_HOST or not parsed_url.path.startswith(APPROVED_REPO_PATH + 'releases/download/') or parsed_url.path.rsplit('/', 1)[-1] != filename or parsed_url.query or parsed_url.fragment:
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

    # Source checkouts can explicitly exercise unsigned local fixtures. Packaged
    # applications always require a trusted signature and matching publisher.
    if not getattr(sys, 'frozen', False) and os.environ.get("ZAYA_REQUIRE_AUTHENTICODE") != "1":
        return True

    try:
        environment = {**os.environ, 'ZAYA_VERIFY_FILE': str(file_path)}
        cmd = [
            "powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
            "$s = Get-AuthenticodeSignature -LiteralPath $env:ZAYA_VERIFY_FILE; "
            "@{status=$s.Status.ToString();subject=$s.SignerCertificate.Subject} | ConvertTo-Json -Compress"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15, env=environment,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        signature = json.loads(result.stdout)
        status = signature.get('status')
        if status != "Valid":
            return False

        if expected_publisher:
            if not re.search(r'(?:^|,\s*)CN=' + re.escape(expected_publisher) + r'(?:,|$)', signature.get('subject', ''), re.I):
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
        self.channel = CHANNEL
        self.preferences_file = get_update_dir() / 'preferences.json'
        try:
            saved = json.loads(self.preferences_file.read_text(encoding='utf-8'))
            if saved.get('channel') in ('stable', 'beta'):
                self.channel = saved['channel']
        except (OSError, ValueError, TypeError):
            pass

    def set_channel(self, channel):
        if channel not in ('stable', 'beta'):
            raise ValueError('Choose stable or beta updates.')
        with self._lock:
            self.channel = channel
            self.available_manifest = self.ready_installer = None
            self.last_check_time = 0
            self.preferences_file.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.preferences_file.with_suffix('.tmp')
            temporary.write_text(json.dumps({'channel': channel}), encoding='utf-8')
            temporary.replace(self.preferences_file)
            self._set_status(UpdateStatus.IDLE)

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

    def check(self, force: bool = False) -> Optional[DesktopUpdateManifest]:
        """Check for updates synchronously (call from background thread)."""
        now = time.monotonic()
        if not force and (now - self.last_check_time < 3600):
            return self.available_manifest

        with self._lock:
            self._set_status(UpdateStatus.CHECKING, "Checking for updates...")
            self.last_check_time = now

            try:
                req = urllib.request.Request(
                    self.manifest_url + ('&' if '?' in self.manifest_url else '?') + 'channel=' + self.channel,
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
                is_newer = manifest.channel == self.channel and semver_key(manifest.version) > semver_key(VERSION) and manifest.build > BUILD

                if is_newer:
                    self.available_manifest = manifest
                    self._set_status(UpdateStatus.AVAILABLE, f"Version {manifest.version} is available.")
                    return manifest
                else:
                    self.available_manifest = None
                    self._set_status(UpdateStatus.UP_TO_DATE, f"Zaya v{VERSION} is up to date.")
                    return None

            except urllib.error.HTTPError as e:
                self.available_manifest = self.ready_installer = None
                self._set_status(UpdateStatus.UP_TO_DATE if e.code == 404 else UpdateStatus.FAILED,
                                 'No desktop release is published yet.' if e.code == 404 else 'Update service unavailable. Try again later.')
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
            self.ready_installer = None
            target_installer = updates_dir / manifest.filename
            temp_installer = updates_dir / (manifest.filename + ".tmp")

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
            manifest = self.available_manifest
            if not manifest or self.ready_installer.stat().st_size != manifest.size or hashlib.sha256(self.ready_installer.read_bytes()).hexdigest() != manifest.sha256:
                raise ValueError('Staged update changed after verification.')
            if not verify_authenticode_signature(self.ready_installer, 'Sajan Rai'):
                raise ValueError('Staged update signature is no longer valid.')
            if os.name != 'nt':
                raise ValueError('Windows installer updates are unavailable on this platform.')
            cmd = [str(self.ready_installer)]
            if silent:
                # Inno Setup silent install parameters
                cmd.extend(["/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/ZAYARESTART=1"])

            # Spawn installer as detached process
            flags = subprocess.DETACHED_PROCESS if os.name == "nt" else 0
            subprocess.Popen(cmd, creationflags=flags)

            if restart:
                from PyQt6.QtWidgets import QApplication
                app = QApplication.instance()
                if app:
                    app.quit()
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
