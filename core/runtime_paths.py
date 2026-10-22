"""Centralized runtime path resolver and user data directory manager.
Created and developed by Sajan Rai for Zaya.

Guarantees clean separation between immutable application binaries and mutable user data.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable, Optional

OFFICIAL_HAND_MODEL_URL = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
OFFICIAL_HAND_MODEL_SHA256 = "fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1"
MAX_MODEL_SIZE = 12 * 1024 * 1024  # 12 MB


def is_frozen() -> bool:
    """Return True if running inside a packaged PyInstaller binary."""
    return getattr(sys, "frozen", False)


def get_app_root() -> Path:
    """Return application binaries root directory."""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def get_resource_dir() -> Path:
    """Return read-only packaged resource directory."""
    if is_frozen():
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass)
        resources_sub = Path(sys.executable).resolve().parent / "resources"
        if resources_sub.is_dir():
            return resources_sub
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def get_user_data_dir() -> Path:
    """Return mutable user data root directory.

    In production/frozen builds: %LOCALAPPDATA%\\Zaya.
    In development builds: repository root by default (or ZAYA_USER_DATA_DIR / ZAYA_FORCE_APPDATA).
    """
    override = os.environ.get("ZAYA_USER_DATA_DIR")
    if override:
        return Path(override).resolve()

    if is_frozen() or os.environ.get("ZAYA_FORCE_APPDATA") == "1":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data) / "Zaya"
        return Path.home() / ".zaya"

    # Development source checkout
    return Path(__file__).resolve().parents[1]


def get_config_dir() -> Path:
    return get_user_data_dir() / "config"


def get_memory_dir() -> Path:
    return get_user_data_dir() / "memory"


def get_log_dir() -> Path:
    return get_user_data_dir() / "logs"


def get_cache_dir() -> Path:
    return get_user_data_dir() / "cache"


def get_model_dir() -> Path:
    return get_user_data_dir() / "models"


def get_update_dir() -> Path:
    return get_user_data_dir() / "updates"


def ensure_user_directories() -> None:
    """Ensure all required mutable user directories exist and seed default config if needed."""
    for folder in (get_config_dir(), get_memory_dir(), get_log_dir(), get_cache_dir(), get_model_dir(), get_update_dir()):
        folder.mkdir(parents=True, exist_ok=True)

    # In frozen mode, seed non-sensitive default configs if absent
    if is_frozen():
        bundled_config = get_resource_dir() / "config"
        target_config = get_config_dir()
        if bundled_config.is_dir():
            for item in bundled_config.iterdir():
                if item.is_file() and not (target_config / item.name).exists():
                    try:
                        shutil.copy2(item, target_config / item.name)
                    except Exception:
                        pass


def find_hand_worker() -> Optional[Path]:
    """Locate the isolated hand worker executable or development runtime."""
    # 1. Packaged ZayaHandWorker.exe next to application executable or in app root
    app_root = get_app_root()
    candidate = app_root / "ZayaHandWorker.exe"
    if candidate.is_file():
        return candidate

    # 2. Inside resource directory
    candidate_res = get_resource_dir() / "ZayaHandWorker.exe"
    if candidate_res.is_file():
        return candidate_res

    # 3. Development .venv-hands runtime
    dev_runtime = Path(__file__).resolve().parents[1] / ".venv-hands" / "Scripts" / "python.exe"
    if dev_runtime.is_file():
        return dev_runtime

    return None


def verify_file_sha256(path: Path, expected_hash: str) -> bool:
    """Verify SHA-256 hash of a file."""
    if not path.is_file():
        return False
    sha = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            sha.update(chunk)
    return sha.hexdigest().lower() == expected_hash.lower()


def find_or_download_hand_model(progress_callback: Optional[Callable[[int, int], None]] = None) -> Path:
    """Locate the official MediaPipe Hand Landmarker model or download it atomically from Google."""
    # Check candidate locations
    candidates = [
        get_model_dir() / "hand_landmarker.task",
        get_app_root() / "models" / "hand_landmarker.task",
        get_resource_dir() / "models" / "hand_landmarker.task",
    ]
    for c in candidates:
        if c.is_file() and c.stat().st_size <= MAX_MODEL_SIZE:
            if verify_file_sha256(c, OFFICIAL_HAND_MODEL_SHA256):
                return c
            # Discard corrupted model in user data cache
            if c == get_model_dir() / "hand_landmarker.task":
                try:
                    c.unlink(missing_ok=True)
                except OSError:
                    pass

    # Target destination
    destination = get_model_dir() / "hand_landmarker.task"
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_path = destination.with_suffix(".tmp")

    try:
        req = urllib.request.Request(OFFICIAL_HAND_MODEL_URL, headers={"User-Agent": "Zaya-Model-Downloader"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            content_length = int(resp.headers.get("Content-Length", 0))
            if content_length > MAX_MODEL_SIZE:
                raise ValueError("Model file exceeds maximum permitted size.")

            received = 0
            with temp_path.open("wb") as out:
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    received += len(chunk)
                    if received > MAX_MODEL_SIZE:
                        raise ValueError("Model download exceeded permitted size.")
                    out.write(chunk)
                    if progress_callback and content_length > 0:
                        progress_callback(received, content_length)

        # Verify exact hash
        if not verify_file_sha256(temp_path, OFFICIAL_HAND_MODEL_SHA256):
            raise ValueError("Downloaded hand model hash verification failed.")

        # Atomic rename
        temp_path.replace(destination)
        return destination
    except Exception as err:
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)
        raise RuntimeError(f"Failed to acquire hand landmarker model: {err}") from err
