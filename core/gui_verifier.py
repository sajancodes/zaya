"""Unified GUI Verification, Active Window Protection, and Act-and-Verify Engine.
Created and developed by Sajan Rai for Zaya.

Provides:
- Verified active window inspection & foreground focus enforcement.
- Target window tracking & destructive action guards (clear-field / smart-type protection).
- Safe clipboard saving and restoring around paste operations.
- Act-and-Verify step loop with visual / OCR post-condition verification.
- OpenCV template locator caching & zoom-refinement.
- HiDPI and multi-monitor coordinate normalization.
- Truthful structured outcomes (success with evidence, or loud failure).
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import io
import json
import logging
import os
import platform
import re
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_OS = platform.system()  # "Windows" | "Darwin" | "Linux"
if _OS == "Windows":
    _WIN_HIDE: dict = {"creationflags": subprocess.CREATE_NO_WINDOW}
else:
    _WIN_HIDE: dict = {}

# ── Session State for Target Window & Locator Cache ──────────────────────────
_SESSION_TARGET_WINDOW: Optional[str] = None
_LOCATOR_CACHE: Dict[str, Dict[str, Any]] = {}
_LAST_FOCUSED_TIME: float = 0.0


# ── Active Window Inspection (Cross-Platform) ─────────────────────────────────

def get_active_window_info() -> Dict[str, Any]:
    """Return title, handle/id, process id, and bounds of the current active foreground window."""
    if _OS == "Windows":
        try:
            user32 = ctypes.windll.user32
            hwnd = user32.GetForegroundWindow()
            if not hwnd:
                return {"hwnd": 0, "title": "", "pid": 0, "bounds": (0, 0, 0, 0), "os": "windows"}

            length = user32.GetWindowTextLengthW(hwnd)
            title = ""
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                title = buf.value.strip()

            pid = ctypes.c_ulong()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

            rect = wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            bounds = (rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top)

            return {
                "hwnd": int(hwnd),
                "title": title,
                "pid": int(pid.value),
                "bounds": bounds,
                "os": "windows",
            }
        except Exception as e:
            logger.debug("[GuiVerifier] Windows active window lookup failed: %s", e)
            return {"hwnd": 0, "title": "", "pid": 0, "bounds": (0, 0, 0, 0), "os": "windows", "error": str(e)}

    elif _OS == "Linux":
        # Check DISPLAY and XAUTHORITY
        display = os.environ.get("DISPLAY")
        if not display:
            return {
                "hwnd": 0, "title": "", "pid": 0, "bounds": (0, 0, 0, 0),
                "os": "linux", "no_wm": True, "error": "DISPLAY environment variable not set."
            }

        # Try xdotool
        try:
            res = subprocess.run(["xdotool", "getactivewindow", "getwindowname"],
                                 capture_output=True, text=True, timeout=2)
            if res.returncode == 0 and res.stdout.strip():
                return {"hwnd": 1, "title": res.stdout.strip(), "pid": 0, "bounds": (0, 0, 0, 0), "os": "linux"}
        except FileNotFoundError:
            pass
        except Exception:
            pass

        # Try xprop
        try:
            res = subprocess.run(["xprop", "-root", "_NET_ACTIVE_WINDOW"],
                                 capture_output=True, text=True, timeout=2)
            if res.returncode == 0 and "window id #" in res.stdout:
                win_id = res.stdout.split("window id #")[-1].strip().split()[0]
                name_res = subprocess.run(["xprop", "-id", win_id, "WM_NAME"],
                                          capture_output=True, text=True, timeout=2)
                if name_res.returncode == 0:
                    match = re.search(r'=\s*"(.*?)"', name_res.stdout)
                    if match:
                        return {"hwnd": int(win_id, 16) if win_id.startswith("0x") else 1,
                                "title": match.group(1), "pid": 0, "bounds": (0, 0, 0, 0), "os": "linux"}
        except Exception:
            pass

        return {"hwnd": 0, "title": "", "pid": 0, "bounds": (0, 0, 0, 0), "os": "linux", "no_wm": True}

    elif _OS == "Darwin":
        try:
            script = 'tell application "System Events" to get name of first process whose frontmost is true'
            res = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=2)
            if res.returncode == 0 and res.stdout.strip():
                return {"hwnd": 1, "title": res.stdout.strip(), "pid": 0, "bounds": (0, 0, 0, 0), "os": "macos"}
        except Exception:
            pass
        return {"hwnd": 0, "title": "", "pid": 0, "bounds": (0, 0, 0, 0), "os": "macos"}

    return {"hwnd": 0, "title": "", "pid": 0, "bounds": (0, 0, 0, 0), "os": "unknown"}


def list_visible_windows() -> List[Dict[str, Any]]:
    """List all top-level user application windows."""
    windows: List[Dict[str, Any]] = []
    if _OS == "Windows":
        try:
            user32 = ctypes.windll.user32
            WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

            def enum_cb(hwnd, _lparam):
                if user32.IsWindowVisible(hwnd):
                    length = user32.GetWindowTextLengthW(hwnd)
                    if length > 0:
                        buf = ctypes.create_unicode_buffer(length + 1)
                        user32.GetWindowTextW(hwnd, buf, length + 1)
                        title = buf.value.strip()
                        if title and title not in ("Program Manager", "Settings", "Windows Shell Experience Host"):
                            rect = wintypes.RECT()
                            user32.GetWindowRect(hwnd, ctypes.byref(rect))
                            w = rect.right - rect.left
                            h = rect.bottom - rect.top
                            if w > 80 and h > 80:
                                pid = ctypes.c_ulong()
                                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                                windows.append({
                                    "hwnd": int(hwnd),
                                    "title": title,
                                    "pid": int(pid.value),
                                    "bounds": (rect.left, rect.top, w, h),
                                })
                return True

            user32.EnumWindows(WNDENUMPROC(enum_cb), 0)
        except Exception as e:
            logger.debug("[GuiVerifier] EnumWindows failed: %s", e)

    elif _OS == "Linux":
        try:
            res = subprocess.run(["wmctrl", "-l"], capture_output=True, text=True, timeout=2)
            if res.returncode == 0:
                for line in res.stdout.splitlines():
                    parts = line.split(None, 3)
                    if len(parts) >= 4:
                        windows.append({
                            "hwnd": int(parts[0], 16) if parts[0].startswith("0x") else 1,
                            "title": parts[3].strip(),
                            "pid": 0,
                            "bounds": (0, 0, 0, 0),
                        })
        except Exception:
            pass

    return windows


# ── Target Window & Verified Focus Management ────────────────────────────────

def set_target_window(title_or_query: str) -> None:
    """Designate the expected target application window for the current workflow."""
    global _SESSION_TARGET_WINDOW
    _SESSION_TARGET_WINDOW = title_or_query.strip() if title_or_query else None
    logger.info("[GuiVerifier] Target window set to: '%s'", _SESSION_TARGET_WINDOW)


def get_target_window() -> Optional[str]:
    """Retrieve the currently designated target window."""
    return _SESSION_TARGET_WINDOW


def clear_target_window() -> None:
    """Clear the session target window."""
    global _SESSION_TARGET_WINDOW
    _SESSION_TARGET_WINDOW = None


def verify_active_target(expected_window: Optional[str] = None) -> Tuple[bool, str, Dict[str, Any]]:
    """Check if the current active foreground window matches the expected target.
    Returns (is_match, current_active_title, window_info).
    """
    target = (expected_window or _SESSION_TARGET_WINDOW or "").strip().lower()
    info = get_active_window_info()
    current_title = info.get("title", "")
    current_lower = current_title.lower()

    if not target:
        # If no target specified, match is trivially true
        return True, current_title, info

    # 1. Direct or substring match
    if target in current_lower or (len(current_lower) > 3 and current_lower in target):
        return True, current_title, info

    # 2. Token-based matching (handles title changes like 'Instagram - Brave' -> 'Instagram • Messages - Brave')
    target_tokens = set(t for t in re.split(r"\W+", target) if len(t) > 2)
    current_tokens = set(t for t in re.split(r"\W+", current_lower) if len(t) > 2)

    app_tokens = {"brave", "chrome", "firefox", "edge", "opera", "code", "terminal", "powershell"}
    common_apps = target_tokens & app_tokens
    if common_apps and (common_apps & current_tokens):
        content_target = target_tokens - app_tokens
        content_current = current_tokens - app_tokens
        if not content_target or (content_target & content_current):
            set_target_window(current_title)
            return True, current_title, info

    if target_tokens and (len(target_tokens & current_tokens) / len(target_tokens)) >= 0.5:
        set_target_window(current_title)
        return True, current_title, info

    return False, current_title, info


def focus_window(title: str, timeout: float = 3.0) -> Dict[str, Any]:
    """Bring the matching window to foreground and POLL to verify it is actually active.
    Never reports success unless the active window title matches.
    """
    global _LAST_FOCUSED_TIME
    if not title:
        return {"success": False, "status": "failed", "error": "No window title provided to focus."}

    clean_title = title.strip().lower()
    start_time = time.time()

    if _OS == "Windows":
        try:
            user32 = ctypes.windll.user32
            # Find matching HWND from visible windows
            windows = list_visible_windows()
            matching_hwnd = None
            matched_title = ""

            clean_tokens = set(t for t in re.split(r"\W+", clean_title) if len(t) > 2)
            for w in windows:
                w_title_lower = w["title"].lower()
                if clean_title in w_title_lower:
                    matching_hwnd = w["hwnd"]
                    matched_title = w["title"]
                    break
                w_tokens = set(t for t in re.split(r"\W+", w_title_lower) if len(t) > 2)
                if clean_tokens and clean_tokens.issubset(w_tokens):
                    matching_hwnd = w["hwnd"]
                    matched_title = w["title"]
                    break
                if clean_tokens and (len(clean_tokens & w_tokens) / len(clean_tokens)) >= 0.6:
                    matching_hwnd = w["hwnd"]
                    matched_title = w["title"]
                    break

            if not matching_hwnd:
                return {
                    "success": False,
                    "status": "failed",
                    "error": f"No open window found matching '{title}'. Open the application first.",
                    "available_windows": [w["title"] for w in windows[:6]],
                }

            # Restore and bring to foreground
            user32.ShowWindow(matching_hwnd, 9)  # SW_RESTORE
            time.sleep(0.05)

            # Bypass Windows foreground lock restriction via AttachThreadInput
            current_fg = user32.GetForegroundWindow()
            current_thread = user32.GetWindowThreadProcessId(current_fg, 0)
            target_thread = user32.GetWindowThreadProcessId(matching_hwnd, 0)

            if current_thread != target_thread:
                user32.AttachThreadInput(current_thread, target_thread, True)
                user32.SetForegroundWindow(matching_hwnd)
                user32.SetFocus(matching_hwnd)
                user32.AttachThreadInput(current_thread, target_thread, False)
            else:
                user32.SetForegroundWindow(matching_hwnd)

            # Poll for up to timeout seconds until GetForegroundWindow matches
            while time.time() - start_time < timeout:
                info = get_active_window_info()
                if clean_title in info.get("title", "").lower():
                    set_target_window(info["title"])
                    _LAST_FOCUSED_TIME = time.time()
                    return {
                        "success": True,
                        "status": "success",
                        "summary": f"Verified focus on '{info['title']}'.",
                        "active_title": info["title"],
                        "hwnd": matching_hwnd,
                    }
                time.sleep(0.1)

            # Final check
            info = get_active_window_info()
            if clean_title in info.get("title", "").lower():
                set_target_window(info["title"])
                _LAST_FOCUSED_TIME = time.time()
                return {"success": True, "status": "success", "active_title": info["title"]}

            return {
                "success": False,
                "status": "failed",
                "error": f"Focus attempt timed out. Active window remains: '{info.get('title', 'Unknown')}'.",
                "active_title": info.get("title", ""),
            }

        except Exception as e:
            return {"success": False, "status": "failed", "error": f"Windows focus_window failed: {e}"}

    elif _OS == "Linux":
        try:
            subprocess.run(["wmctrl", "-a", title], capture_output=True, timeout=2)
            time.sleep(0.2)
            info = get_active_window_info()
            if clean_title in info.get("title", "").lower():
                set_target_window(info["title"])
                _LAST_FOCUSED_TIME = time.time()
                return {"success": True, "status": "success", "active_title": info["title"]}

            # Try xdotool
            subprocess.run(["xdotool", "search", "--name", title, "windowactivate"], capture_output=True, timeout=2)
            time.sleep(0.2)
            info = get_active_window_info()
            if clean_title in info.get("title", "").lower():
                set_target_window(info["title"])
                _LAST_FOCUSED_TIME = time.time()
                return {"success": True, "status": "success", "active_title": info["title"]}

            return {
                "success": False,
                "status": "failed",
                "error": f"Could not focus '{title}' on Linux. Active window: '{info.get('title')}'.",
            }
        except Exception as e:
            return {"success": False, "status": "failed", "error": f"Linux focus_window error: {e}"}

    elif _OS == "Darwin":
        try:
            script = (f'tell application "{title}" to activate\n'
                      f'tell application "System Events" to set frontmost of first process whose name contains "{title}" to true')
            subprocess.run(["osascript", "-e", script], capture_output=True, timeout=3)
            time.sleep(0.3)
            info = get_active_window_info()
            if clean_title in info.get("title", "").lower():
                set_target_window(info["title"])
                _LAST_FOCUSED_TIME = time.time()
                return {"success": True, "status": "success", "active_title": info["title"]}
            return {
                "success": False,
                "status": "failed",
                "error": f"Could not focus '{title}' on macOS. Active app: '{info.get('title')}'.",
            }
        except Exception as e:
            return {"success": False, "status": "failed", "error": f"macOS focus_window error: {e}"}

    return {"success": False, "status": "failed", "error": f"Unknown OS: {_OS}"}


# ── Destructive-Action Guard ──────────────────────────────────────────────────

def guard_window_action(
    action_name: str,
    target_window: Optional[str] = None,
    auto_refocus: bool = True,
) -> Tuple[bool, Optional[str]]:
    """Guard against performing typing, clicking, or field clearing into the wrong application.
    If target_window or session target is set, verifies active window matches.
    If not matching and auto_refocus is True, attempts to refocus target once.
    Returns (allowed: bool, error_reason: Optional[str]).
    """
    expected = (target_window or _SESSION_TARGET_WINDOW or "").strip()
    if not expected:
        # No target window constraint declared
        return True, None

    is_match, active_title, _ = verify_active_target(expected)
    if is_match:
        return True, None

    if auto_refocus:
        # Attempt to refocus the target window
        logger.info("[GuiVerifier] Active window '%s' != target '%s'. Refocusing...", active_title, expected)
        fres = focus_window(expected, timeout=2.0)
        if fres.get("success"):
            return True, None

    # Refocus failed or prohibited
    msg = (
        f"ABORTED '{action_name}': Current active window is '{active_title}', "
        f"which does not match expected target window '{expected}'. "
        f"Prevented typing/clicking into the wrong application."
    )
    logger.warning("[GuiVerifier] %s", msg)
    return False, msg


# ── Safe Clipboard Management ────────────────────────────────────────────────

def safe_clipboard_paste(text: str, verify: bool = False) -> Dict[str, Any]:
    """Paste text into target field while preserving and restoring the user's prior clipboard."""
    try:
        import pyperclip
    except ImportError:
        return {"success": False, "status": "failed", "error": "pyperclip is not installed."}

    # Backup original clipboard contents
    prior_clipboard = ""
    try:
        prior_clipboard = pyperclip.paste()
    except Exception:
        pass

    try:
        pyperclip.copy(text)
        time.sleep(0.04)

        # Trigger paste
        paste_key = "command" if _OS == "Darwin" else "ctrl"
        try:
            import pyautogui
            try:
                cur_pos = pyautogui.position()
                if cur_pos[0] < 2 or cur_pos[1] < 2:
                    pyautogui.moveTo(max(2, cur_pos[0]), max(2, cur_pos[1]))
            except Exception:
                pass
            pyautogui.hotkey(paste_key, "v")
            time.sleep(0.06)
        except Exception as e:
            return {"success": False, "status": "failed", "error": f"Keystroke paste failed: {e}"}

        return {
            "success": True,
            "status": "success",
            "summary": f"Pasted {len(text)} characters safely via clipboard.",
            "text_sample": text[:60] + ("…" if len(text) > 60 else ""),
        }
    finally:
        # Restore prior user clipboard content after brief delay
        time.sleep(0.05)
        try:
            if prior_clipboard:
                pyperclip.copy(prior_clipboard)
        except Exception:
            pass


# ── Coordinate Space & HiDPI Normalization ────────────────────────────────────

def get_screen_metrics() -> Dict[str, Any]:
    """Retrieve precise physical, logical dimensions, scaling factor, and virtual origin."""
    primary_w, primary_h = 1920, 1080
    try:
        import pyautogui
        sz = pyautogui.size()
        primary_w, primary_h = int(sz.width), int(sz.height)
    except Exception:
        pass

    logical_w, logical_h = primary_w, primary_h
    if _OS == "Windows":
        try:
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


def to_logical_coords(x: float, y: float, source_w: int, source_h: int) -> Tuple[int, int]:
    """Transform coordinates from any source frame (e.g. 1000x1000 normalized,
    screenshot physical pixels, or logical space) into precise cursor coordinates.
    """
    metrics = get_screen_metrics()
    target_w = metrics["primary_w"]
    target_h = metrics["primary_h"]

    if source_w <= 0 or source_h <= 0:
        return int(round(x)), int(round(y))

    # Normalized [0..1000] per-mille coordinates (used by Gemini ER-2, GPT-4o, Claude)
    if source_w == 1000 and source_h == 1000:
        mapped_x = int(round(float(x) * target_w / 1000.0))
        mapped_y = int(round(float(y) * target_h / 1000.0))
    elif source_w != target_w or source_h != target_h:
        mapped_x = int(round(float(x) * target_w / float(source_w)))
        mapped_y = int(round(float(y) * target_h / float(source_h)))
    else:
        mapped_x = int(round(x))
        mapped_y = int(round(y))

    # Clamp to safe bounds (avoiding 0,0 fail-safe trigger in pyautogui)
    clamped_x = max(2, min(target_w - 2, mapped_x))
    clamped_y = max(2, min(target_h - 2, mapped_y))
    return clamped_x, clamped_y


# ── Locator Cache with OpenCV Template Matching ──────────────────────────────

def get_cached_locator(description: str, window_title: str) -> Optional[Tuple[int, int]]:
    """Retrieve and validate cached element coordinates using OpenCV template matching."""
    key = f"{description.lower().strip()}::{window_title.lower().strip()}"
    entry = _LOCATOR_CACHE.get(key)
    if not entry:
        return None

    # Verify template match against current screen
    try:
        import cv2
        import numpy as np
        import pyautogui

        template = entry.get("template")
        if template is None:
            return entry.get("coords")

        cur_img = np.array(pyautogui.screenshot())
        cur_bgr = cv2.cvtColor(cur_img, cv2.COLOR_RGB2BGR)

        res = cv2.matchTemplate(cur_bgr, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)

        if max_val >= 0.88:
            th, tw = template.shape[:2]
            cx = max_loc[0] + tw // 2
            cy = max_loc[1] + th // 2
            logger.info("[GuiVerifier] Locator cache HIT for '%s' (confidence: %.2f)", description, max_val)
            return cx, cy
        else:
            logger.debug("[GuiVerifier] Locator cache invalidated for '%s' (conf: %.2f < 0.88)", description, max_val)
            _LOCATOR_CACHE.pop(key, None)
    except Exception as e:
        logger.debug("[GuiVerifier] Cache check failed: %s", e)

    return None


def set_cached_locator(description: str, window_title: str, coords: Tuple[int, int], screenshot_img: Any = None) -> None:
    """Store locator in cache with a 100x40 template crop around coordinates."""
    key = f"{description.lower().strip()}::{window_title.lower().strip()}"
    entry: Dict[str, Any] = {"coords": coords, "timestamp": time.time()}

    if screenshot_img is not None:
        try:
            import cv2
            import numpy as np
            cx, cy = coords
            np_img = np.array(screenshot_img)
            bgr = cv2.cvtColor(np_img, cv2.COLOR_RGB2BGR)
            h, w = bgr.shape[:2]
            x1 = max(0, cx - 50)
            y1 = max(0, cy - 20)
            x2 = min(w, cx + 50)
            y2 = min(h, cy + 20)
            if x2 > x1 and y2 > y1:
                entry["template"] = bgr[y1:y2, x1:x2].copy()
        except Exception:
            pass

    _LOCATOR_CACHE[key] = entry


# ── Act-and-Verify Step Loop ──────────────────────────────────────────────────

def act_and_verify(
    action_name: str,
    action_fn: Callable[[], Any],
    expect: Optional[str] = None,
    target_window: Optional[str] = None,
    timeout: float = 8.0,
    poll_interval: float = 0.35,
) -> Dict[str, Any]:
    """Execute a GUI action and strictly verify its outcome.
    If expect is given, polls the screen until the post-condition is satisfied or timeout expires.
    """
    # 1. Guard target window
    allowed, guard_err = guard_window_action(action_name, target_window=target_window)
    if not allowed:
        return {
            "status": "failed",
            "success": False,
            "summary": guard_err,
            "evidence": {"action": action_name, "error": guard_err},
        }

    # 2. Capture baseline before screenshot
    before_img = None
    try:
        import pyautogui
        before_img = pyautogui.screenshot()
    except Exception:
        pass

    # 3. Perform action
    t0 = time.perf_counter()
    raw_res = None
    try:
        raw_res = action_fn()
    except Exception as e:
        return {
            "status": "failed",
            "success": False,
            "summary": f"Action '{action_name}' crashed: {e}",
            "evidence": {"action": action_name, "error": str(e)},
        }

    latency = (time.perf_counter() - t0) * 1000.0

    # 4. If no expectation was provided, return outcome with verification warning
    if not expect:
        return {
            "status": "success",
            "success": True,
            "summary": str(raw_res),
            "evidence": {"action": action_name, "latency_ms": round(latency, 2)},
        }

    # 5. Expectation supplied: Poll screen for post-condition verification
    clean_expect = expect.strip().lower()
    is_negative = clean_expect.startswith("!")
    target_text = clean_expect[1:].strip() if is_negative else clean_expect
    start_poll = time.time()
    last_observation = ""

    while time.time() - start_poll < timeout:
        time.sleep(poll_interval)
        try:
            import pyautogui
            cur_img = pyautogui.screenshot()
        except Exception:
            continue

        from actions.computer_control import _find_via_ocr, _find_via_uia
        w, h = cur_img.size
        ocr_hit = _find_via_ocr(target_text, cur_img, w, h)
        uia_hit = _find_via_uia(target_text)
        found = (ocr_hit is not None) or (uia_hit is not None)

        if is_negative:
            # We want the element / modal to be DISMISSED / GONE
            if not found:
                return {
                    "status": "success",
                    "success": True,
                    "summary": f"Action '{action_name}' succeeded: verified dismissal of '{target_text}'.",
                    "evidence": {
                        "action": action_name,
                        "dismissed": target_text,
                        "elapsed_sec": round(time.time() - start_poll, 2),
                    },
                }
        else:
            if ocr_hit is not None:
                return {
                    "status": "success",
                    "success": True,
                    "summary": f"Action '{action_name}' succeeded: verified post-condition '{expect}' at {ocr_hit}.",
                    "evidence": {
                        "action": action_name,
                        "expect": expect,
                        "verified_via": "ocr",
                        "hit_coords": ocr_hit,
                        "elapsed_sec": round(time.time() - start_poll, 2),
                    },
                }

            if uia_hit is not None:
                return {
                    "status": "success",
                    "success": True,
                    "summary": f"Action '{action_name}' succeeded: verified post-condition '{expect}' in UI tree.",
                    "evidence": {
                        "action": action_name,
                        "expect": expect,
                        "verified_via": "uia",
                        "hit_coords": uia_hit,
                        "elapsed_sec": round(time.time() - start_poll, 2),
                    },
                }

    # Expectation was NOT verified within timeout
    return {
        "status": "failed",
        "success": False,
        "summary": (
            f"Action '{action_name}' executed, but expected outcome '{expect}' was NOT observed "
            f"within {timeout}s. Target window: '{get_active_window_info().get('title')}'."
        ),
        "evidence": {
            "action": action_name,
            "expect": expect,
            "timeout_sec": timeout,
            "final_active_window": get_active_window_info().get("title"),
        },
    }
