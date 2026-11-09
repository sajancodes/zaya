#computer_control.py
from __future__ import annotations

import io
import json
import platform
import re
import string
import subprocess
import sys
from typing import Any

if platform.system() == "Windows":
    _WIN_HIDE: dict = {"creationflags": subprocess.CREATE_NO_WINDOW}
else:
    _WIN_HIDE: dict = {}
import time
import random
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# ── DPI Awareness & Coordinate Space Normalization ───────────────────────────
def _enable_dpi_awareness() -> None:
    """Ensure process uses true per-monitor physical pixel metrics on Windows."""
    if platform.system() == "Windows":
        try:
            import ctypes
            try:
                # Per-Monitor V2 DPI awareness context (-4)
                ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
            except Exception:
                try:
                    # PROCESS_PER_MONITOR_DPI_AWARE = 2
                    ctypes.windll.shcore.SetProcessDpiAwareness(2)
                except Exception:
                    pass
        except Exception:
            pass

_enable_dpi_awareness()

def get_screen_metrics() -> dict[str, Any]:
    """Retrieve precise physical and logical screen dimensions and scaling factor."""
    _enable_dpi_awareness()
    primary_w, primary_h = 1920, 1080
    if _PYAUTOGUI:
        try:
            sz = pyautogui.size()
            primary_w, primary_h = int(sz.width), int(sz.height)
        except Exception:
            pass

    logical_w, logical_h = primary_w, primary_h
    if platform.system() == "Windows":
        try:
            import ctypes
            user32 = ctypes.windll.user32
            sm_w = user32.GetSystemMetrics(0)
            sm_h = user32.GetSystemMetrics(1)
            if sm_w > 0 and sm_h > 0:
                logical_w, logical_h = int(sm_w), int(sm_h)
        except Exception:
            pass

    scale_x = float(primary_w) / float(max(1, logical_w))
    scale_y = float(primary_h) / float(max(1, logical_h))

    return {
        "primary_w": primary_w,
        "primary_h": primary_h,
        "logical_w": logical_w,
        "logical_h": logical_h,
        "scale_x": scale_x,
        "scale_y": scale_y,
    }

def to_logical_coords(x: float, y: float, source_w: int, source_h: int) -> tuple[int, int]:
    """Transform coordinates from any source frame (e.g. 1000x1000 normalized,
    screenshot physical pixels, or logical space) into precise cursor coordinates.
    """
    metrics = get_screen_metrics()
    target_w = metrics["primary_w"]
    target_h = metrics["primary_h"]

    if source_w <= 0 or source_h <= 0:
        return int(round(x)), int(round(y))

    # Normalized [0..1000] per-mille coordinates (used by ER-2, GPT Operator, Claude Computer Use)
    if source_w == 1000 and source_h == 1000:
        mapped_x = int(round(float(x) * target_w / 1000.0))
        mapped_y = int(round(float(y) * target_h / 1000.0))
    elif source_w != target_w or source_h != target_h:
        # Scale proportionally from screenshot dimensions to target cursor space
        mapped_x = int(round(float(x) * target_w / float(source_w)))
        mapped_y = int(round(float(y) * target_h / float(source_h)))
    else:
        mapped_x = int(round(x))
        mapped_y = int(round(y))

    # Clamp to valid screen bounds
    clamped_x = max(0, min(target_w - 1, mapped_x))
    clamped_y = max(0, min(target_h - 1, mapped_y))
    return clamped_x, clamped_y

try:
    import pyautogui
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE    = 0.05
    _PYAUTOGUI = True
except ImportError:
    _PYAUTOGUI = False

try:
    import pyperclip
    _PYPERCLIP = True
except ImportError:
    _PYPERCLIP = False

def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


_BASE         = _base_dir()
_CONFIG_PATH  = _BASE / "config" / "api_keys.json"
_MEMORY_PATH  = _BASE / "memory" / "long_term.json"

def _load_config() -> dict:
    try:
        return json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}

def _platform_os() -> str:
    return {"Windows": "windows", "Darwin": "mac", "Linux": "linux"}.get(
        platform.system(), "linux"
    )

def _get_os() -> str:
    return _load_config().get("os_system", _platform_os()).lower()


def _get_api_key() -> str:
    from core import gemini
    return gemini.api_key()

_SAFE_SCREENSHOT_ROOTS = (
    Path.home(),
)

def _safe_screenshot_path(requested: str | None) -> Path:
    fallback = Path.home() / "Desktop" / "zaya_screenshot.png"
    if not requested:
        return fallback
    try:
        p = Path(requested).expanduser().resolve()
        for root in _SAFE_SCREENSHOT_ROOTS:
            if p.is_relative_to(root.resolve()):
                p.parent.mkdir(parents=True, exist_ok=True)
                return p
    except Exception:
        pass
    return fallback

def _require_pyautogui():
    if not _PYAUTOGUI:
        raise RuntimeError("PyAutoGUI not installed. Run: pip install pyautogui")

_FIRST_NAMES = [
    "Alex", "Jordan", "Taylor", "Morgan", "Casey", "Riley", "Drew", "Quinn",
    "Avery", "Blake", "Cameron", "Dakota", "Emerson", "Finley", "Harper",
]
_LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
    "Davis", "Wilson", "Moore", "Taylor", "Anderson", "Thomas", "Jackson",
]
_DOMAINS = ["gmail.com", "yahoo.com", "outlook.com", "proton.me", "mail.com"]


def _random_data(data_type: str) -> str:
    dt = data_type.lower().strip()

    if dt == "first_name":
        return random.choice(_FIRST_NAMES)

    if dt == "last_name":
        return random.choice(_LAST_NAMES)

    if dt == "name":
        return f"{random.choice(_FIRST_NAMES)} {random.choice(_LAST_NAMES)}"

    if dt == "email":
        first = random.choice(_FIRST_NAMES).lower()
        last  = random.choice(_LAST_NAMES).lower()
        num   = random.randint(10, 999)
        return f"{first}.{last}{num}@{random.choice(_DOMAINS)}"

    if dt == "username":
        return f"{random.choice(_FIRST_NAMES).lower()}{random.randint(100, 9999)}"

    if dt == "password":
        chars = string.ascii_letters + string.digits + "!@#$%"
        raw   = (
            random.choice(string.ascii_uppercase)
            + random.choice(string.digits)
            + random.choice("!@#$%")
            + "".join(random.choices(chars, k=9))
        )
        return "".join(random.sample(raw, len(raw)))

    if dt == "phone":
        return f"+1{random.randint(200,999)}{random.randint(1_000_000, 9_999_999)}"

    if dt == "birthday":
        y = random.randint(1980, 2000)
        m = random.randint(1, 12)
        d = random.randint(1, 28)
        return f"{m:02d}/{d:02d}/{y}"

    if dt == "address":
        num    = random.randint(100, 9999)
        street = random.choice(["Main St", "Oak Ave", "Park Blvd", "Elm St", "Cedar Ln"])
        return f"{num} {street}"

    if dt == "zip_code":
        return str(random.randint(10000, 99999))

    if dt == "city":
        return random.choice(["New York", "Los Angeles", "Chicago", "Houston", "Phoenix"])

    return f"random_{data_type}_{random.randint(1000, 9999)}"

def _user_profile() -> dict:
    """Read identity fields from long-term memory."""
    try:
        if _MEMORY_PATH.exists():
            data     = json.loads(_MEMORY_PATH.read_text(encoding="utf-8"))
            identity = data.get("identity", {})
            return {k: v.get("value", "") for k, v in identity.items()}
    except Exception:
        pass
    return {}

def _type(text: str, interval: float = 0.03) -> str:
    _require_pyautogui()
    time.sleep(0.3)
    pyautogui.typewrite(text, interval=interval)
    return f"Typed: {text[:60]}{'…' if len(text) > 60 else ''}"


def _smart_type(text: str, clear_first: bool = True) -> str:
    _require_pyautogui()
    if clear_first:
        _clear_field()
        time.sleep(0.1)

    if len(text) > 20 and _PYPERCLIP:
        pyperclip.copy(text)
        time.sleep(0.1)
        paste_key = "command" if _get_os() == "mac" else "ctrl"
        pyautogui.hotkey(paste_key, "v")
        return f"Smart-typed (clipboard): {text[:60]}{'…' if len(text) > 60 else ''}"

    pyautogui.typewrite(text, interval=0.04)
    return f"Smart-typed: {text[:60]}{'…' if len(text) > 60 else ''}"


def _native_win32_click(x: int, y: int, button: str = "left", clicks: int = 1) -> bool:
    """Ultra-low-latency native Windows cursor positioning and clicking via win32api."""
    if platform.system() != "Windows":
        return False
    try:
        import win32api
        import win32con

        win32api.SetCursorPos((x, y))
        time.sleep(0.02)

        down_flag = win32con.MOUSEEVENTF_LEFTDOWN if button == "left" else win32con.MOUSEEVENTF_RIGHTDOWN
        up_flag = win32con.MOUSEEVENTF_LEFTUP if button == "left" else win32con.MOUSEEVENTF_RIGHTUP

        for _ in range(clicks):
            win32api.mouse_event(down_flag, x, y, 0, 0)
            time.sleep(0.03)
            win32api.mouse_event(up_flag, x, y, 0, 0)
            if clicks > 1:
                time.sleep(0.05)
        return True
    except Exception:
        return False


def _click(x=None, y=None, button: str = "left", clicks: int = 1) -> str:
    _require_pyautogui()
    if x is not None and y is not None:
        target_x, target_y = int(round(x)), int(round(y))
        try:
            pyautogui.moveTo(target_x, target_y, duration=0.08)
            time.sleep(0.04)
        except Exception:
            pass

        if _native_win32_click(target_x, target_y, button=button, clicks=clicks):
            return f"{'Double-c' if clicks == 2 else 'C'}licked ({target_x}, {target_y}) [{button}]"

        pyautogui.click(target_x, target_y, button=button, clicks=clicks)
        return f"{'Double-c' if clicks == 2 else 'C'}licked ({target_x}, {target_y}) [{button}]"
    pyautogui.click(button=button, clicks=clicks)
    return f"Clicked at current position [{button}]"


def _hotkey(*keys) -> str:
    _require_pyautogui()
    pyautogui.hotkey(*keys)
    return f"Hotkey: {'+'.join(keys)}"


def _press(key: str) -> str:
    _require_pyautogui()
    pyautogui.press(key)
    return f"Pressed: {key}"


def _scroll(direction: str = "down", amount: int = 3) -> str:
    _require_pyautogui()
    vertical   = direction in ("up", "down")
    clicks     = amount if direction in ("up", "right") else -amount
    pyautogui.scroll(clicks) if vertical else pyautogui.hscroll(clicks)
    return f"Scrolled {direction} ×{amount}"


def _move(x: int, y: int, duration: float = 0.3) -> str:
    _require_pyautogui()
    pyautogui.moveTo(x, y, duration=duration)
    return f"Mouse → ({x}, {y})"


def _drag(x1: int, y1: int, x2: int, y2: int, duration: float = 0.5) -> str:
    _require_pyautogui()
    pyautogui.moveTo(x1, y1, duration=0.2)
    pyautogui.dragTo(x2, y2, duration=duration, button="left")
    return f"Dragged ({x1},{y1}) → ({x2},{y2})"


def _clipboard_get() -> str:
    if _PYPERCLIP:
        return pyperclip.paste()
    _hotkey("ctrl", "c")
    time.sleep(0.2)
    return "(copied — pyperclip unavailable for read)"


def _clipboard_paste(text: str) -> str:
    if _PYPERCLIP:
        pyperclip.copy(text)
        time.sleep(0.1)
        _require_pyautogui()
        paste_key = "command" if _get_os() == "mac" else "ctrl"
        pyautogui.hotkey(paste_key, "v")
        return f"Pasted: {text[:60]}{'…' if len(text) > 60 else ''}"
    return "pyperclip not available"


def _screenshot(save_path: str | None = None) -> str:
    _require_pyautogui()
    path = _safe_screenshot_path(save_path)
    img  = pyautogui.screenshot()
    img.save(str(path))
    return f"Screenshot saved: {path}"


def _clear_field() -> str:
    _require_pyautogui()
    select_key = "command" if _get_os() == "mac" else "ctrl"
    pyautogui.hotkey(select_key, "a")
    time.sleep(0.1)
    pyautogui.press("delete")
    return "Field cleared"

def _focus_window(title: str) -> str:
    os_name = _get_os()

    if os_name == "windows":
        try:
            literal = "'" + title.replace("'", "''") + "'"
            script = f'(New-Object -ComObject WScript.Shell).AppActivate({literal})'
            subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                capture_output=True, timeout=5, **_WIN_HIDE,
            )
            time.sleep(0.3)
            return f"Focused window: {title}"
        except Exception as e:
            return f"focus_window (Windows) failed: {e}"

    if os_name == "mac":
        script = ('on run argv\n'
                  'tell application "System Events" to set frontmost of '
                  '(first process whose name contains (item 1 of argv)) to true\n'
                  'end run')
        try:
            subprocess.run(
                ["osascript", "-e", script, title],
                capture_output=True, timeout=5,
            )
            time.sleep(0.3)
            return f"Focused window: {title}"
        except Exception as e:
            return f"focus_window (macOS) failed: {e}"

    if os_name == "linux":
        try:
            result = subprocess.run(
                ["wmctrl", "-a", title],
                capture_output=True, timeout=5,
            )
            if result.returncode == 0:
                time.sleep(0.3)
                return f"Focused window: {title}"
        except FileNotFoundError:
            pass
        try:
            result = subprocess.run(
                ["xdotool", "search", "--name", title, "windowactivate"],
                capture_output=True, timeout=5,
            )
            time.sleep(0.3)
            return f"Focused window: {title}"
        except FileNotFoundError:
            return "focus_window (Linux) requires wmctrl or xdotool"
        except Exception as e:
            return f"focus_window (Linux) failed: {e}"

    return f"focus_window: unknown OS '{os_name}'"

def _find_via_uia(description: str) -> tuple[int, int] | None:
    """Tier A: Inspect active/visible window accessibility hierarchy using pywinauto UIA."""
    if platform.system() != "Windows":
        return None
    try:
        from pywinauto import Desktop
        import ctypes
        user32 = ctypes.windll.user32
        fg_hwnd = user32.GetForegroundWindow()

        desc_lower = description.lower().strip()
        desktop = Desktop(backend="uia")

        # Prioritize foreground window descendants first
        windows = desktop.windows(visible_only=True)
        ordered_windows = []
        for win in windows:
            try:
                if win.handle == fg_hwnd:
                    ordered_windows.insert(0, win)
                else:
                    ordered_windows.append(win)
            except Exception:
                ordered_windows.append(win)

        candidates: list[tuple[float, tuple[int, int], str]] = []

        for win in ordered_windows[:6]:
            try:
                is_fg = (win.handle == fg_hwnd)
                fg_bonus = 0.15 if is_fg else 0.0

                for ctrl in win.descendants():
                    try:
                        text = (ctrl.window_text() or "").strip()
                        c_type = ctrl.element_info.control_type or ""
                        auto_id = ctrl.element_info.automation_id or ""
                        name = ctrl.element_info.name or ""

                        rect = ctrl.rectangle()
                        if rect.width() <= 0 or rect.height() <= 0:
                            continue

                        text_l = text.lower()
                        auto_id_l = auto_id.lower()
                        name_l = name.lower()

                        score = 0.0
                        if desc_lower == text_l or desc_lower == name_l:
                            score = 1.0
                        elif desc_lower == auto_id_l:
                            score = 0.95
                        elif desc_lower and (desc_lower in text_l or desc_lower in name_l):
                            score = 0.8
                        elif desc_lower and ((text_l and text_l in desc_lower)
                                             or (name_l and name_l in desc_lower)):
                            # The empty-string guard matters: "" in description
                            # is always True, so every nameless control in the
                            # tree used to score 0.7 and flood the candidate
                            # list until the ambiguity check rejected the match.
                            score = 0.7
                        elif desc_lower and auto_id_l and auto_id_l in desc_lower:
                            score = 0.65
                        else:
                            # Token overlap
                            tokens = [t for t in re.split(r"\W+", desc_lower) if len(t) > 2]
                            if tokens:
                                combined = f"{text_l} {c_type.lower()} {auto_id_l} {name_l}"
                                overlap = sum(1 for t in tokens if t in combined)
                                if overlap > 0:
                                    score = 0.4 + 0.3 * (overlap / len(tokens))

                        if score > 0.4:
                            # Bonuses for enabled/visible and interactive controls
                            try:
                                if ctrl.is_enabled():
                                    score += 0.05
                            except Exception:
                                pass
                            if c_type in ("Button", "Hyperlink", "MenuItem", "Edit", "TabItem", "CheckBox", "ListItem"):
                                score += 0.05
                            score += fg_bonus
                            candidates.append((score, (rect.mid_point().x, rect.mid_point().y), text or name or auto_id))
                    except Exception:
                        continue
            except Exception:
                continue

        if not candidates:
            return None

        # Sort descending by score
        candidates.sort(key=lambda c: c[0], reverse=True)
        top_score, top_point, _ = candidates[0]

        # Ambiguity check: if top two have nearly identical score (< 0.10 diff) and distinct points (> 30px distance)
        if len(candidates) > 1:
            second_score, second_point, _ = candidates[1]
            dist_sq = (top_point[0] - second_point[0]) ** 2 + (top_point[1] - second_point[1]) ** 2
            if (top_score - second_score < 0.10) and dist_sq > 900 and top_score < 1.0:
                # Ambiguous match among distinct controls — reject to avoid mis-clicking
                return None

        return to_logical_coords(top_point[0], top_point[1], 0, 0)
    except Exception as e:
        print(f"[ComputerControl] UIA element search failed: {e}")
        return None


def _find_via_ocr(description: str, screenshot_img: Any, shot_w: int, shot_h: int) -> tuple[int, int] | None:
    """Tier 1: Windows Native Media OCR text extraction & exact bounding box centroid grounding."""
    if platform.system() != "Windows" or not description:
        return None

    import tempfile
    import os
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf:
            tmp_path = tf.name

        screenshot_img.save(tmp_path, format="PNG")

        ps_script = """
param([string]$ImagePath)
try {
    Add-Type -AssemblyName System.Runtime.WindowsRuntime
    $asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | ? { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
    Function Await($winRtOp, $resultType) {
        $asTask = $asTaskGeneric.MakeGenericMethod($resultType)
        $netTask = $asTask.Invoke($null, @($winRtOp))
        $netTask.Wait(-1) | Out-Null
        return $netTask.Result
    }

    [Windows.Media.Ocr.OcrEngine, Windows.Foundation.UniversalApiContract, ContentType=WindowsRuntime] | Out-Null
    [Windows.Graphics.Imaging.BitmapDecoder, Windows.Foundation.UniversalApiContract, ContentType=WindowsRuntime] | Out-Null
    [Windows.Storage.StorageFile, Windows.Foundation.UniversalApiContract, ContentType=WindowsRuntime] | Out-Null

    $file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync((Resolve-Path $ImagePath).Path)) ([Windows.Storage.StorageFile])
    $stream = Await ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
    $decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
    $bitmap = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])

    $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
    if ($null -eq $engine) {
        $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage([Windows.Globalization.Language]::new("en-US"))
    }
    $result = Await ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])

    $lines = @()
    foreach ($l in $result.Lines) {
        $words = @()
        foreach ($w in $l.Words) {
            $r = $w.BoundingRect
            $words += @{ text = $w.Text; x = [int]$r.X; y = [int]$r.Y; w = [int]$r.Width; h = [int]$r.Height }
        }
        $lines += @{ text = $l.Text; words = $words }
    }
    $lines | ConvertTo-Json -Depth 4
} catch {
    Write-Output "[]"
}
"""
        cmd = [
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            ps_script,
            "-ImagePath",
            tmp_path,
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=6, **_WIN_HIDE)
        if res.returncode != 0 or not res.stdout.strip():
            return None

        raw_out = res.stdout.strip()
        data = json.loads(raw_out)
        lines = data if isinstance(data, list) else ([data] if isinstance(data, dict) else [])
        if not lines:
            return None

        desc_clean = re.sub(r"[^\w\s]", "", description.lower()).strip()
        tokens = [t for t in desc_clean.split() if len(t) > 1]
        if not tokens:
            tokens = [desc_clean]

        best_match = None
        best_score = 0.0

        for line in lines:
            l_text = line.get("text", "")
            l_clean = re.sub(r"[^\w\s]", "", l_text.lower()).strip()
            words = line.get("words", [])

            # Exact or full substring match on line
            if desc_clean and desc_clean in l_clean:
                if words:
                    min_x = min(w["x"] for w in words)
                    min_y = min(w["y"] for w in words)
                    max_x = max(w["x"] + w["w"] for w in words)
                    max_y = max(w["y"] + w["h"] for w in words)
                    center_x = (min_x + max_x) // 2
                    center_y = (min_y + max_y) // 2
                    return to_logical_coords(center_x, center_y, shot_w, shot_h)

            # Match individual words and compute score
            for w in words:
                w_text = re.sub(r"[^\w\s]", "", w.get("text", "").lower()).strip()
                if not w_text:
                    continue
                score = 0.0
                if w_text == desc_clean:
                    score = 1.0
                elif any(t == w_text for t in tokens):
                    score = 0.85
                elif any(t in w_text or w_text in t for t in tokens if len(t) >= 3):
                    score = 0.65

                if score > best_score:
                    best_score = score
                    cx = w["x"] + w["w"] // 2
                    cy = w["y"] + w["h"] // 2
                    best_match = (cx, cy)

        if best_match and best_score >= 0.65:
            return to_logical_coords(best_match[0], best_match[1], shot_w, shot_h)

    except Exception as e:
        logger.debug("[ComputerControl] Windows Media OCR failed: %s", e)
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass
    return None


def _detect_visual_candidates(screenshot_img: Any, w: int, h: int, max_candidates: int = 50) -> list[dict]:
    """Detect visual interactable UI candidates using OpenCV contours and edge detection."""
    try:
        import cv2
        import numpy as np

        # Convert PIL image to BGR numpy array
        np_img = np.array(screenshot_img)
        if np_img.shape[2] == 4:
            bgr = cv2.cvtColor(np_img, cv2.COLOR_RGBA2BGR)
        else:
            bgr = cv2.cvtColor(np_img, cv2.COLOR_RGB2BGR)

        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (3, 3), 0)
        edges = cv2.Canny(blurred, 30, 120)

        # Morphological close to join adjacent edges
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        dilated = cv2.dilate(edges, kernel, iterations=1)

        contours, _ = cv2.findContours(dilated, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

        raw_boxes = []
        # Use the IMAGE's own dimensions for the area filter. pyautogui.size()
        # reports the primary monitor while the screenshot covers the whole
        # virtual desktop, so the two disagree on a multi-monitor setup.
        img_h, img_w = (np_img.shape[0], np_img.shape[1]) if np_img.ndim >= 2 else (h, w)
        screen_area = max(1, img_w * img_h)

        for cnt in contours:
            x, y, bw, bh = cv2.boundingRect(cnt)
            area = bw * bh
            # Filter noise and whole screen containers:
            # Width and height > 12px, area > 150px, area < 50% screen
            if bw > 12 and bh > 10 and area > 150 and area < (0.50 * screen_area):
                raw_boxes.append((x, y, x + bw, y + bh))

        if not raw_boxes:
            return []

        # Deduplicate overlapping boxes with IoU > 0.40
        raw_boxes.sort(key=lambda b: (b[2] - b[0]) * (b[3] - b[1]))  # small to large
        deduped = []
        for b in raw_boxes:
            overlap = False
            b_area = (b[2] - b[0]) * (b[3] - b[1])
            for d in deduped:
                # Intersection
                ix1 = max(b[0], d[0])
                iy1 = max(b[1], d[1])
                ix2 = min(b[2], d[2])
                iy2 = min(b[3], d[3])
                if ix1 < ix2 and iy1 < iy2:
                    inter_area = (ix2 - ix1) * (iy2 - iy1)
                    iou = inter_area / min(b_area, (d[2] - d[0]) * (d[3] - d[1]))
                    if iou > 0.40:
                        overlap = True
                        break
            if not overlap:
                deduped.append(b)
                if len(deduped) >= max_candidates:
                    break

        return [
            {
                "box": box,
                "center": ((box[0] + box[2]) // 2, (box[1] + box[3]) // 2),
            }
            for box in deduped
        ]
    except Exception as e:
        print(f"[ComputerControl] OpenCV visual candidate detection failed: {e}")
        return []


def _detect_uia_candidates(w: int, h: int, max_candidates: int = 40) -> list[dict]:
    """Harvest interactive controls from the live accessibility tree (Windows only).

    Kept as its own function so the SoM path can be exercised without
    reaching into whatever happens to be on the owner's desktop: while this
    was inlined in _find_via_som(), the SoM test silently used the real
    screen and only passed on machines with no visible windows.
    """
    candidates: list[dict] = []
    if platform.system() != "Windows":
        return candidates
    try:
        from pywinauto import Desktop
        desktop = Desktop(backend="uia")
        for win in desktop.windows(visible_only=True)[:4]:
            for ctrl in win.descendants():
                try:
                    if ctrl.element_info.control_type in ("Button", "Hyperlink", "MenuItem", "Edit", "TabItem", "CheckBox"):
                        r = ctrl.rectangle()
                        if 5 < r.width() < w and 5 < r.height() < h:
                            candidates.append({
                                "box": (r.left, r.top, r.right, r.bottom),
                                "center": (r.mid_point().x, r.mid_point().y),
                            })
                            if len(candidates) >= max_candidates:
                                break
                except Exception:
                    continue
            if len(candidates) >= max_candidates:
                break
    except Exception:
        pass
    return candidates


def _find_via_som(description: str, screenshot_img: Any, w: int, h: int) -> tuple[int, int] | None:
    """Tier B: Set-of-Mark (SoM) visual candidate detection + structured LLM identification."""
    try:
        from PIL import ImageDraw
        from google.genai import types as gtypes
        from core import gemini

        # Harvest interactive candidates via the accessibility tree first, and
        # fall back to OpenCV contour detection when it yields nothing.
        candidates: list[dict] = _detect_uia_candidates(w, h)
        if not candidates:
            candidates = _detect_visual_candidates(screenshot_img, w, h, max_candidates=50)

        # If still no candidates found, fallback to coordinate search
        if not candidates:
            return None

        # Draw Set-of-Mark bounding boxes and numeric badges
        som_img = screenshot_img.copy()
        draw = ImageDraw.Draw(som_img)
        marks: dict[int, tuple[int, int]] = {}

        for idx, cand in enumerate(candidates, start=1):
            box = cand["box"]
            center = cand["center"]
            marks[idx] = center
            draw.rectangle(box, outline=(255, 30, 30), width=2)
            badge_box = [box[0], max(0, box[1] - 16), box[0] + 20, box[1]]
            draw.rectangle(badge_box, fill=(255, 30, 30))
            draw.text((box[0] + 3, max(0, box[1] - 15)), str(idx), fill=(255, 255, 255))

        buf = io.BytesIO()
        som_img.save(buf, format="PNG")
        som_bytes = buf.getvalue()

        prompt = (
            f"You are given a Set-of-Mark screenshot with numbered tags [1..{len(marks)}] over UI elements. "
            f"Identify the tag number corresponding to: '{description}'. "
            f"Reply with ONLY a JSON object: {{\"id\": <number>}} or {{\"id\": null}} if not found."
        )

        resp = gemini.call(
            [gtypes.Part.from_bytes(data=som_bytes, mime_type="image/png"), prompt],
            tier=gemini.FAST,
            timeout_ms=15_000,
        )
        if resp and resp.text:
            text = resp.text.strip()
            # Strict JSON parsing first
            try:
                parsed = json.loads(text)
                if isinstance(parsed, dict) and "id" in parsed:
                    val = parsed["id"]
                    if isinstance(val, int) and val in marks:
                        return to_logical_coords(marks[val][0], marks[val][1], w, h)
                    if val is None:
                        return None
            except Exception:
                pass

            # Regex fallback for mark id extraction
            match = re.search(r'\{\s*"id"\s*:\s*(\d+)\s*\}', text)
            if match:
                mark_id = int(match.group(1))
                if mark_id in marks:
                    return to_logical_coords(marks[mark_id][0], marks[mark_id][1], w, h)
    except Exception as e:
        print(f"[ComputerControl] SoM element search failed: {e}")

    return None


def _find_via_coordinates(description: str, screenshot_bytes: bytes, w: int, h: int) -> tuple[int, int] | None:
    """Tier 3: SOTA normalized [0..1000] visual spatial grounding via ER-2 / Gemini Vision."""
    try:
        from core import gemini

        prompt = (
            f"You are an expert GUI grounding agent. Analyze the provided screenshot ({w}x{h} px) "
            f"and locate the UI element: '{description}'.\n"
            f"Reply with ONLY a JSON object in this format:\n"
            f'{{"point": [y, x], "label": "{description}"}}\n'
            f"where y and x are integers normalized to 0-1000 (0 is top/left, 1000 is bottom/right).\n"
            f'If not visible on screen, reply: {{"point": null}}'
        )

        try:
            from google.genai import types as gtypes
            content_part = gtypes.Part.from_bytes(data=screenshot_bytes, mime_type="image/png")
        except ImportError:
            import base64
            content_part = {
                "inline_data": {
                    "mime_type": "image/png",
                    "data": base64.b64encode(screenshot_bytes).decode("ascii"),
                }
            }

        resp = None
        for tier in ("models/gemini-robotics-er-2-streaming-preview", gemini.SMART, gemini.FAST):
            try:
                resp = gemini.call(
                    [content_part, prompt],
                    tier=tier,
                    timeout_ms=18_000,
                )
                if resp and resp.text:
                    break
            except Exception:
                continue

        if resp is None or not resp.text:
            return None

        text = resp.text.strip()
        if "null" in text.lower() and '"point": null' in text.lower():
            return None

        # 1. Parse JSON format {"point": [y, x]} or {"box_2d": [ymin, xmin, ymax, xmax]}
        try:
            clean_json = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE).strip()
            data = json.loads(clean_json)
            if isinstance(data, dict):
                pt = data.get("point")
                if isinstance(pt, (list, tuple)) and len(pt) >= 2 and pt[0] is not None and pt[1] is not None:
                    norm_y, norm_x = float(pt[0]), float(pt[1])
                    return to_logical_coords(norm_x, norm_y, 1000, 1000)

                box = data.get("box_2d") or data.get("bbox")
                if isinstance(box, (list, tuple)) and len(box) >= 4:
                    ymin, xmin, ymax, xmax = float(box[0]), float(box[1]), float(box[2]), float(box[3])
                    norm_y = (ymin + ymax) / 2.0
                    norm_x = (xmin + xmax) / 2.0
                    return to_logical_coords(norm_x, norm_y, 1000, 1000)
        except Exception:
            pass

        # 2. Regex fallback for point [y, x] in normalized 0..1000
        pt_match = re.search(r'"point"\s*:\s*\[\s*(\d+(?:\.\d+)?)\s*,\s*(\d+(?:\.\d+)?)\s*\]', text)
        if pt_match:
            norm_y, norm_x = float(pt_match.group(1)), float(pt_match.group(2))
            return to_logical_coords(norm_x, norm_y, 1000, 1000)

        # 3. Regex fallback for box_2d [ymin, xmin, ymax, xmax]
        box_match = re.search(r'\[\s*(\d+(?:\.\d+)?)\s*,\s*(\d+(?:\.\d+)?)\s*,\s*(\d+(?:\.\d+)?)\s*,\s*(\d+(?:\.\d+)?)\s*\]', text)
        if box_match:
            ymin, xmin, ymax, xmax = (float(box_match.group(i)) for i in range(1, 5))
            norm_y = (ymin + ymax) / 2.0
            norm_x = (xmin + xmax) / 2.0
            return to_logical_coords(norm_x, norm_y, 1000, 1000)

        # 4. Fallback for raw x,y
        match_raw = re.search(r"(\d+)\s*,\s*(\d+)", text)
        if match_raw:
            raw_x, raw_y = int(match_raw.group(1)), int(match_raw.group(2))
            return to_logical_coords(raw_x, raw_y, w, h)

    except Exception as e:
        logger.debug("[ComputerControl] Coordinate fallback failed: %s", e)

    return None


def _screen_find(description: str) -> tuple[int, int] | None:
    """High-precision 4-tier UI element grounding:
    Tier 0: Accessibility tree inspection (pywinauto UIA).
    Tier 1: Windows Native Media OCR text bounding box centroid grounding.
    Tier 2: Set-of-Mark (SoM) visual candidate tagging with structured LLM detection.
    Tier 3: SOTA normalized [0..1000] visual spatial prediction (ER-2 / Gemini Vision).
    """
    if not description:
        return None

    # Tier 0: UIA accessibility inspection
    coords = _find_via_uia(description)
    if coords is not None:
        return coords

    # Capture screen for visual & OCR tiers
    try:
        _require_pyautogui()
        img = pyautogui.screenshot()
        # pyautogui.screenshot() captures the whole virtual desktop, which on
        # a multi-monitor setup is larger than pyautogui.size() (the primary
        # monitor). Every coordinate the accessibility tree reports is in
        # virtual-desktop space, so the visual tiers must use the same space.
        shot_w, shot_h = img.size
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        screenshot_bytes = buf.getvalue()
    except Exception as e:
        print(f"[ComputerControl] Screenshot capture failed: {e}")
        return None

    # Tier 1: Windows Native OCR exact text grounding
    coords = _find_via_ocr(description, img, shot_w, shot_h)
    if coords is not None:
        return coords

    # Tier 2: Set-of-Mark visual tagging
    coords = _find_via_som(description, img, shot_w, shot_h)
    if coords is not None:
        return coords

    # Tier 3: SOTA normalized visual spatial prediction
    return _find_via_coordinates(description, screenshot_bytes, shot_w, shot_h)


def computer_control(
    parameters: dict,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    """
    Dispatch table for all computer control actions.

    parameters keys (all optional unless noted):
      action        : (required) one of the actions listed below
      text          : text to type or paste
      x, y          : screen coordinates
      button        : 'left' | 'right' (default: left)
      keys          : hotkey string, e.g. 'ctrl+c'
      key           : single key name, e.g. 'enter'
      direction     : 'up' | 'down' | 'left' | 'right'
      amount        : scroll amount (default: 3)
      seconds       : wait duration
      title         : window title fragment for focus_window
      description   : natural-language element description for screen_find/click
      type          : data type for random_data
      field         : memory field name for user_data
      clear_first   : bool, clear field before typing (default: true)
      path          : save path for screenshot (must be inside home dir)

    Actions:
      type          — type text at cursor
      smart_type    — clear field + type (clipboard-backed)
      click         — left click (auto-resolves description if x/y omitted)
      double_click  — double left click (auto-resolves description if x/y omitted)
      right_click   — right click (auto-resolves description if x/y omitted)
      move          — move mouse (auto-resolves description if x/y omitted)
      drag          — click-drag between two points
      hotkey        — key combination
      press         — single key
      scroll        — scroll the wheel
      copy          — read clipboard
      paste         — write + paste clipboard
      screenshot    — capture screen (safe path only)
      wait          — sleep N seconds
      clear_field   — select-all + delete
      focus_window  — bring window to foreground
      screen_find   — AI element finder (returns x,y)
      screen_click  — AI element finder + click
      random_data   — generate fake form data
      user_data     — pull real data from memory
    """
    params = parameters or {}
    action = params.get("action", "").lower().strip()

    if not action:
        return "No action specified for computer_control."

    if player:
        player.write_log(f"[Computer] {action}")

    print(f"[ComputerControl] ▶ {action}  {params}")

    try:

        if action == "type":
            return _type(params.get("text", ""))

        if action == "smart_type":
            return _smart_type(
                params.get("text", ""),
                clear_first=params.get("clear_first", True),
            )

        # Smart coordinate auto-resolution when description/text/target is provided
        def _resolve_target_coords(param_dict: dict) -> tuple[int, int] | None:
            raw_x = param_dict.get("x")
            raw_y = param_dict.get("y")
            if raw_x is not None and raw_y is not None:
                try:
                    return int(raw_x), int(raw_y)
                except (ValueError, TypeError):
                    pass

            target_desc = (
                param_dict.get("description")
                or param_dict.get("text")
                or param_dict.get("label")
                or param_dict.get("target")
                or param_dict.get("element")
            )
            if target_desc:
                coords = _screen_find(str(target_desc))
                if coords:
                    return coords
            return None

        if action in ("click", "left_click"):
            target = _resolve_target_coords(params)
            if target:
                return _click(target[0], target[1], "left", 1)
            desc = params.get("description") or params.get("label") or params.get("element")
            if desc:
                return f"Element not found on screen: '{desc}'"
            return _click(None, None, "left", 1)

        if action == "double_click":
            target = _resolve_target_coords(params)
            if target:
                return _click(target[0], target[1], "left", 2)
            desc = params.get("description") or params.get("label") or params.get("element")
            if desc:
                return f"Element not found on screen: '{desc}'"
            return _click(None, None, "left", 2)

        if action == "right_click":
            target = _resolve_target_coords(params)
            if target:
                return _click(target[0], target[1], "right", 1)
            desc = params.get("description") or params.get("label") or params.get("element")
            if desc:
                return f"Element not found on screen: '{desc}'"
            return _click(None, None, "right", 1)

        if action == "move":
            target = _resolve_target_coords(params)
            if target:
                return _move(target[0], target[1])
            desc = params.get("description") or params.get("label") or params.get("element")
            if desc:
                return f"Element not found on screen: '{desc}'"
            return _move(int(params.get("x", 0)), int(params.get("y", 0)))

        if action == "drag":
            return _drag(
                int(params.get("x1", 0)), int(params.get("y1", 0)),
                int(params.get("x2", 0)), int(params.get("y2", 0)),
            )

        if action == "hotkey":
            raw  = params.get("keys", "")
            keys = [k.strip() for k in raw.split("+")] if isinstance(raw, str) else raw
            return _hotkey(*keys)

        if action == "press":
            return _press(params.get("key", "enter"))

        if action == "scroll":
            return _scroll(
                direction=params.get("direction", "down"),
                amount=int(params.get("amount", 3)),
            )

        if action == "copy":
            return _clipboard_get()

        if action == "paste":
            return _clipboard_paste(params.get("text", ""))

        if action == "screenshot":
            return _screenshot(params.get("path"))

        if action == "screen_find":
            coords = _screen_find(params.get("description", ""))
            return f"{coords[0]},{coords[1]}" if coords else "NOT_FOUND"

        if action == "screen_click":
            desc   = params.get("description", "")
            coords = _screen_find(desc)
            if coords:
                time.sleep(0.2)
                _click(x=coords[0], y=coords[1])
                return f"Clicked '{desc}' at {coords}"
            return f"Element not found on screen: '{desc}'"

        if action == "wait":
            secs = float(params.get("seconds", 1.0))
            secs = min(secs, 30.0)
            time.sleep(secs)
            return f"Waited {secs}s"

        if action == "clear_field":
            return _clear_field()

        if action == "focus_window":
            return _focus_window(params.get("title", ""))

        if action == "random_data":
            dt     = params.get("type", "name")
            result = _random_data(dt)
            print(f"[ComputerControl] 🎲 random {dt} → {result}")
            return result

        if action == "user_data":
            field   = params.get("field", "name")
            profile = _user_profile()
            value   = profile.get(field, "")
            if not value:
                value = _random_data(field)
                print(f"[ComputerControl] ⚠️ No '{field}' in memory, using random: {value}")
            return value

        return f"Unknown action: '{action}'"

    except Exception as e:
        print(f"[ComputerControl] ❌ {action}: {e}")
        return f"computer_control '{action}' failed: {e}"


# ── Tool declaration (auto-discovered by core/action_loader.py) ──────────────
TOOL = {
    "name": "computer_control",
    "description": (
        "High-precision computer and browser control for multi-step GUI automation: type, click, "
        "hotkeys, scroll, move mouse, screenshots, and pixel-perfect element finding and clicking. "
        "Supports natural-language target descriptions (e.g., 'Create post', 'Share', 'Search') with "
        "4-tier grounding (UIA accessibility tree, native OCR text centroid, Set-of-Mark tagging, "
        "and normalized [0..1000] spatial vision). Essential for executing multi-step tasks such as "
        "navigating web apps, drafting and publishing posts, filling forms, and managing desktop windows "
        "in synergy with robotics_screen_monitor."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "type | smart_type | click | double_click | right_click | hotkey | press | scroll | move | copy | paste | screenshot | wait | clear_field | focus_window | screen_find | screen_click | random_data | user_data"
            },
            "text": {
                "type": "STRING",
                "description": "Text to type or paste"
            },
            "x": {
                "type": "INTEGER",
                "description": "X coordinate"
            },
            "y": {
                "type": "INTEGER",
                "description": "Y coordinate"
            },
            "keys": {
                "type": "STRING",
                "description": "Key combination e.g. 'ctrl+c'"
            },
            "key": {
                "type": "STRING",
                "description": "Single key e.g. 'enter'"
            },
            "direction": {
                "type": "STRING",
                "description": "up | down | left | right"
            },
            "amount": {
                "type": "INTEGER",
                "description": "Scroll amount (default: 3)"
            },
            "seconds": {
                "type": "NUMBER",
                "description": "Seconds to wait"
            },
            "title": {
                "type": "STRING",
                "description": "Window title for focus_window"
            },
            "description": {
                "type": "STRING",
                "description": "Element description for screen_find/screen_click/click/move (e.g. 'Create post', 'Share')"
            },
            "type": {
                "type": "STRING",
                "description": "Data type for random_data"
            },
            "field": {
                "type": "STRING",
                "description": "Field for user_data: name|email|city"
            },
            "clear_first": {
                "type": "BOOLEAN",
                "description": "Clear field before typing (default: true)"
            },
            "path": {
                "type": "STRING",
                "description": "Save path for screenshot"
            }
        },
        "required": [
            "action"
        ]
    },
    "handler": computer_control,
}
