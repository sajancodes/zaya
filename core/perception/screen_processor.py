"""
Screen & webcam capture for Zaya vision.

Provides the two capture entry points main.py uses — `_capture_screen()` and
`_capture_camera()` — plus their helpers (compression, camera auto-detection,
config access). main.py grabs a frame here on demand, then injects it into the
main Gemini Live session; there is no separate vision session here.
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import numpy as np

try:
    import cv2
    _CV2 = True
except ImportError:
    class _Cv2Fallback:
        VideoCapture = None
    cv2 = _Cv2Fallback()
    _CV2 = False

try:
    import mss
    import mss.tools
    _MSS = True
except ImportError:
    _MSS = False

try:
    import PIL.Image
    _PIL = True
except ImportError:
    _PIL = False


def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


_BASE        = _base_dir()
_CONFIG_PATH = _BASE / "config" / "api_keys.json"


def _load_config() -> dict:
    try:
        return json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_config_key(key: str, value) -> None:
    try:
        from memory.config_manager import _patch_config
        _patch_config(**{key: value})
    except Exception as e:
        print(f"[Vision] ⚠️  Could not save config key '{key}': {e}")


def _get_os() -> str:
    return _load_config().get("os_system", "windows").lower()


_IMG_MAX_W = 1280
_IMG_MAX_H = 720
_JPEG_Q    = 82


def _compress(img_bytes: bytes, source_format: str = "PNG") -> tuple[bytes, str]:
    if not _PIL:
        return img_bytes, f"image/{source_format.lower()}"

    try:
        img = PIL.Image.open(io.BytesIO(img_bytes)).convert("RGB")
        img.thumbnail((_IMG_MAX_W, _IMG_MAX_H), PIL.Image.BILINEAR)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=_JPEG_Q, optimize=False)
        return buf.getvalue(), "image/jpeg"
    except Exception as e:
        print(f"[Vision] ⚠️  Image compress failed: {e}")
        return img_bytes, f"image/{source_format.lower()}"


def _capture_screen() -> tuple[bytes, str]:

    if not _MSS:
        raise RuntimeError("mss is not installed. Run: pip install mss")

    with mss.mss() as sct:
        monitors = sct.monitors          # [0] = all combined, [1..n] = real screens
        target   = monitors[1] if len(monitors) > 1 else monitors[0]
        shot     = sct.grab(target)
        png      = mss.tools.to_png(shot.rgb, shot.size)

    return _compress(png, "PNG")


def _cv2_backend() -> int:
    """Return the best OpenCV camera backend for the current OS."""
    if not _CV2:
        return 0
    os_name = _get_os()
    if os_name == "windows":
        return cv2.CAP_DSHOW
    if os_name == "mac":
        return cv2.CAP_AVFOUNDATION
    return cv2.CAP_ANY


def _probe_camera(index: int, backend: int, warmup: int = 5) -> bool:

    if not _CV2:
        return False
    cap = cv2.VideoCapture(index, backend)
    if not cap.isOpened():
        cap.release()
        return False
    for _ in range(warmup):
        cap.read()
    ret, frame = cap.read()
    cap.release()
    if not ret or frame is None:
        return False
    return bool(np.mean(frame) > 8)


def _detect_camera_index() -> int:

    backend = _cv2_backend()
    print("[Vision] 🔍 Auto-detecting camera...")
    for idx in range(6):
        if _probe_camera(idx, backend):
            print(f"[Vision] ✅ Camera found at index {idx}")
            _save_config_key("camera_index", idx)
            return idx
        print(f"[Vision] ⚠️  Camera index {idx}: no usable frame")

    print("[Vision] ⚠️  No camera found — defaulting to index 0")
    _save_config_key("camera_index", 0)
    return 0


def _get_camera_index() -> int:
    cfg = _load_config()
    if "camera_index" in cfg:
        return int(cfg["camera_index"])
    return _detect_camera_index()


def _capture_camera() -> tuple[bytes, str]:
    if not _CV2:
        raise RuntimeError("OpenCV (cv2) is not installed. Run: pip install opencv-python")

    # Reuse the optional worker's sensor only on an explicit vision request.
    # Hand tracking never pushes image frames into the Live session on its own.
    try:
        from core.gesture.controller import hands
        tracker=hands.tracker
    except ImportError:
        tracker=None
    if tracker is not None and tracker.state=='ACTIVE':
        index=int(_load_config().get('camera_index',tracker.device))
        if index==tracker.device:
            frame=tracker.capture_frame()
            if frame:
                return frame,'image/jpeg'
            raise RuntimeError('The hand camera could not return the requested vision frame.')
    else:
        index=_get_camera_index()
    backend = _cv2_backend()
    cap     = cv2.VideoCapture(index, backend)

    if not cap.isOpened():
        raise RuntimeError(f"Camera index {index} could not be opened.")

    for _ in range(10):
        cap.read()

    ret, frame = cap.read()
    cap.release()

    if not ret or frame is None:
        raise RuntimeError("Camera returned no frame.")

    if _PIL:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = PIL.Image.fromarray(rgb)
        img.thumbnail((_IMG_MAX_W, _IMG_MAX_H), PIL.Image.BILINEAR)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=_JPEG_Q)
        return buf.getvalue(), "image/jpeg"

    encoded, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, _JPEG_Q])
    if not encoded or buf is None:
        raise RuntimeError('Camera frame could not be encoded as JPEG.')
    return buf.tobytes(), "image/jpeg"


_LAST_FRAME_HASHES: dict[str, int] = {}


def compute_dhash(img_bytes: bytes, hash_size: int = 8) -> int | None:
    """Compute difference hash (dHash) of an image byte buffer."""
    if not _PIL:
        return None
    try:
        img = PIL.Image.open(io.BytesIO(img_bytes)).convert("L")
        resized = img.resize((hash_size + 1, hash_size), PIL.Image.Resampling.BILINEAR)
        if hasattr(resized, "get_flattened_data"):
            pixels = list(resized.get_flattened_data())
        else:
            pixels = list(resized.getdata())  # type: ignore
        diff = 0
        for row in range(hash_size):
            row_offset = row * (hash_size + 1)
            for col in range(hash_size):
                if pixels[row_offset + col] > pixels[row_offset + col + 1]:
                    diff |= 1 << (row * hash_size + col)
        return diff
    except Exception as e:
        print(f"[Vision] ⚠️ compute_dhash failed: {e}")
        return None


def hamming_distance(h1: int, h2: int) -> int:
    """Return the number of differing bits between two integer hashes."""
    return bin(h1 ^ h2).count("1")


def frame_changed(source: str, img_bytes: bytes, threshold: int = 4) -> bool:
    """Return True if the frame has changed by at least threshold bits compared to last capture.

    If source has no prior capture recorded, records hash and returns True.
    """
    current_hash = compute_dhash(img_bytes)
    if current_hash is None:
        return True

    previous_hash = _LAST_FRAME_HASHES.get(source)
    if previous_hash is None:
        _LAST_FRAME_HASHES[source] = current_hash
        return True

    distance = hamming_distance(current_hash, previous_hash)
    if distance >= threshold:
        _LAST_FRAME_HASHES[source] = current_hash
        return True

    return False
