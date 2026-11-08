"""Window Organizer & Snap Layout Manager.
Created and developed by Sajan Rai for Zaya.

Provides programmatic Win32 window snapping, multi-window tiling, centering,
minimizing/maximizing, and foreground focus with precise pixel work-area awareness.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import json
import os
from typing import Any, Dict, List, Optional, Tuple

from core.execution_policy import require_owner

# Win32 Constants
SPI_GETWORKAREA = 0x0030
SWP_NOZORDER = 0x0004
SWP_SHOWWINDOW = 0x0040
SW_RESTORE = 9
SW_MAXIMIZE = 3
SW_MINIMIZE = 6


def _get_work_area() -> Tuple[int, int, int, int]:
    """Return primary monitor work area (left, top, width, height) excluding taskbar."""
    if os.name != "nt":
        return (0, 0, 1920, 1080)

    try:
        user32 = ctypes.windll.user32
        rect = wintypes.RECT()
        user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(rect), 0)
        return (rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top)
    except Exception:
        return (0, 0, 1920, 1080)


def _get_foreground_window() -> int:
    """Return handle of current active foreground window."""
    if os.name != "nt":
        return 0
    try:
        return int(ctypes.windll.user32.GetForegroundWindow())
    except Exception:
        return 0


def _get_window_title(hwnd: int) -> str:
    """Return window title for a given HWND."""
    if os.name != "nt":
        return ""
    try:
        user32 = ctypes.windll.user32
        length = user32.GetWindowTextLengthW(hwnd)
        if length > 0:
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            return buf.value.strip()
    except Exception:
        pass
    return ""


def _list_visible_windows() -> List[Dict[str, Any]]:
    """List all top-level, visible user application windows."""
    windows: List[Dict[str, Any]] = []
    if os.name != "nt":
        return windows

    try:
        user32 = ctypes.windll.user32
        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

        def enum_cb(hwnd, _lparam):
            if user32.IsWindowVisible(hwnd):
                title = _get_window_title(hwnd)
                # Filter empty titles and core background overlays
                if title and title not in ("Program Manager", "Settings", "Windows Shell Experience Host"):
                    rect = wintypes.RECT()
                    user32.GetWindowRect(hwnd, ctypes.byref(rect))
                    w = rect.right - rect.left
                    h = rect.bottom - rect.top
                    if w > 100 and h > 100:
                        pid = ctypes.c_ulong()
                        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                        windows.append({
                            "hwnd": int(hwnd),
                            "title": title,
                            "pid": pid.value,
                            "bounds": {"x": rect.left, "y": rect.top, "width": w, "height": h},
                        })
            return True

        user32.EnumWindows(WNDENUMPROC(enum_cb), 0)
    except Exception:
        pass

    return windows


def _find_window_by_title(query: str) -> Optional[int]:
    """Find the best matching visible window handle by title substring."""
    clean_query = query.lower().strip()
    windows = _list_visible_windows()
    for w in windows:
        if clean_query in w["title"].lower():
            return w["hwnd"]
    return None


def _set_window_geometry(hwnd: int, x: int, y: int, width: int, height: int) -> bool:
    """Restore and move window to target bounds."""
    if os.name != "nt" or not hwnd:
        return False
    try:
        user32 = ctypes.windll.user32
        user32.ShowWindow(hwnd, SW_RESTORE)
        res = user32.SetWindowPos(hwnd, 0, x, y, width, height, SWP_NOZORDER | SWP_SHOWWINDOW)
        return bool(res)
    except Exception:
        return False


def _snap_window(hwnd: int, position: str) -> Dict[str, Any]:
    """Snap window to predefined grid coordinates."""
    pos = position.lower().strip()
    wl, wt, ww, wh = _get_work_area()
    half_w = ww // 2
    half_h = wh // 2

    coords = {
        "left": (wl, wt, half_w, wh),
        "left_half": (wl, wt, half_w, wh),
        "right": (wl + half_w, wt, half_w, wh),
        "right_half": (wl + half_w, wt, half_w, wh),
        "top": (wl, wt, ww, half_h),
        "top_half": (wl, wt, ww, half_h),
        "bottom": (wl, wt + half_h, ww, half_h),
        "bottom_half": (wl, wt + half_h, ww, half_h),
        "top_left": (wl, wt, half_w, half_h),
        "top_right": (wl + half_w, wt, half_w, half_h),
        "bottom_left": (wl, wt + half_h, half_w, half_h),
        "bottom_right": (wl + half_w, wt + half_h, half_w, half_h),
        "center": (wl + int(ww * 0.15), wt + int(wh * 0.15), int(ww * 0.70), int(wh * 0.70)),
    }

    target_geo = coords.get(pos, coords["center"])
    success = _set_window_geometry(hwnd, *target_geo)
    title = _get_window_title(hwnd) or f"Window #{hwnd}"

    return {
        "success": success,
        "hwnd": hwnd,
        "title": title,
        "position": pos,
        "bounds": {"x": target_geo[0], "y": target_geo[1], "width": target_geo[2], "height": target_geo[3]},
    }


def _tile_windows(limit: int = 2, orientation: str = "vertical") -> Dict[str, Any]:
    """Tile the top N visible application windows side-by-side or stacked."""
    windows = _list_visible_windows()
    if not windows:
        return {"success": False, "message": "No active windows found to tile."}

    to_tile = windows[:limit]
    wl, wt, ww, wh = _get_work_area()
    n = len(to_tile)
    tiled = []

    if orientation == "horizontal":
        h_slice = wh // n
        for i, w in enumerate(to_tile):
            _set_window_geometry(w["hwnd"], wl, wt + (i * h_slice), ww, h_slice)
            tiled.append(w["title"])
    else:  # vertical side-by-side (default)
        w_slice = ww // n
        for i, w in enumerate(to_tile):
            _set_window_geometry(w["hwnd"], wl + (i * w_slice), wt, w_slice, wh)
            tiled.append(w["title"])

    return {
        "success": True,
        "count": len(tiled),
        "orientation": orientation,
        "windows": tiled,
    }


def window_manager(parameters: dict, **_kwargs) -> str:
    """Dispatches window positioning, snapping, tiling, and focus management."""
    require_owner()
    action = str(parameters.get("action") or "snap").lower().strip()
    target_title = parameters.get("target") or parameters.get("window_title")
    hwnd = parameters.get("hwnd")

    # Resolve HWND if specified or fallback to active foreground window
    if hwnd is not None:
        target_hwnd = int(hwnd)
    elif target_title:
        target_hwnd = _find_window_by_title(target_title) or 0
    else:
        target_hwnd = _get_foreground_window()

    # 1. Snap Window
    if action == "snap":
        pos = str(parameters.get("position") or "left").lower().strip()
        if not target_hwnd:
            return json.dumps({"status": "error", "message": "No active or matching window found to snap."}, indent=2)
        res = _snap_window(target_hwnd, pos)
        summary = f"Snapped '{res['title']}' to {res['position']} (bounds: {res['bounds']['width']}x{res['bounds']['height']})."
        return json.dumps({"status": "success", "summary": summary, "data": res}, indent=2)

    # 2. Center Window
    if action == "center":
        if not target_hwnd:
            return json.dumps({"status": "error", "message": "No active window found to center."}, indent=2)
        res = _snap_window(target_hwnd, "center")
        summary = f"Centered '{res['title']}' on screen."
        return json.dumps({"status": "success", "summary": summary, "data": res}, indent=2)

    # 3. Maximize Window
    if action == "maximize":
        if not target_hwnd:
            return json.dumps({"status": "error", "message": "No active window found to maximize."}, indent=2)
        try:
            ctypes.windll.user32.ShowWindow(target_hwnd, SW_MAXIMIZE)
            title = _get_window_title(target_hwnd) or "Active window"
            return json.dumps({"status": "success", "summary": f"Maximized '{title}'.", "data": {"hwnd": target_hwnd}}, indent=2)
        except Exception as e:
            return json.dumps({"status": "error", "message": f"Failed to maximize window: {e}"}, indent=2)

    # 4. Minimize Window
    if action == "minimize":
        if not target_hwnd:
            return json.dumps({"status": "error", "message": "No active window found to minimize."}, indent=2)
        try:
            ctypes.windll.user32.ShowWindow(target_hwnd, SW_MINIMIZE)
            title = _get_window_title(target_hwnd) or "Active window"
            return json.dumps({"status": "success", "summary": f"Minimized '{title}'.", "data": {"hwnd": target_hwnd}}, indent=2)
        except Exception as e:
            return json.dumps({"status": "error", "message": f"Failed to minimize window: {e}"}, indent=2)

    # 5. Restore Window
    if action == "restore":
        if not target_hwnd:
            return json.dumps({"status": "error", "message": "No active window found to restore."}, indent=2)
        try:
            ctypes.windll.user32.ShowWindow(target_hwnd, SW_RESTORE)
            title = _get_window_title(target_hwnd) or "Active window"
            return json.dumps({"status": "success", "summary": f"Restored '{title}'.", "data": {"hwnd": target_hwnd}}, indent=2)
        except Exception as e:
            return json.dumps({"status": "error", "message": f"Failed to restore window: {e}"}, indent=2)

    # 6. Focus / Bring to Foreground
    if action in ("focus", "activate"):
        if not target_hwnd:
            return json.dumps({"status": "error", "message": f"Window '{target_title}' not found."}, indent=2)
        try:
            ctypes.windll.user32.ShowWindow(target_hwnd, SW_RESTORE)
            ctypes.windll.user32.SetForegroundWindow(target_hwnd)
            title = _get_window_title(target_hwnd) or "Target window"
            return json.dumps({"status": "success", "summary": f"Brought '{title}' to foreground.", "data": {"hwnd": target_hwnd}}, indent=2)
        except Exception as e:
            return json.dumps({"status": "error", "message": f"Failed to focus window: {e}"}, indent=2)

    # 7. Tile Windows
    if action == "tile":
        count = max(2, min(int(parameters.get("count") or 2), 4))
        orient = str(parameters.get("orientation") or "vertical").lower().strip()
        tiled = _tile_windows(count, orient)
        if tiled.get("success"):
            summary = f"Tiled {tiled['count']} windows {tiled['orientation']}ly: " + ", ".join(tiled['windows'])
            return json.dumps({"status": "success", "summary": summary, "data": tiled}, indent=2)
        return json.dumps({"status": "error", "message": tiled.get("message", "Tiling failed.")}, indent=2)

    # 8. List Open Windows
    if action in ("list", "windows"):
        windows = _list_visible_windows()
        summary = f"Found {len(windows)} visible open application window(s)."
        return json.dumps({"status": "success", "summary": summary, "data": windows}, indent=2)

    return json.dumps({
        "status": "error",
        "message": f"Unknown action '{action}'. Choose from: snap, center, maximize, minimize, restore, tile, focus, list."
    }, indent=2)


TOOL = {
    "name": "window_manager",
    "description": "Snap, center, tile, maximize, minimize, and organize application windows across the desktop with native Win32 work-area geometry.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["snap", "center", "maximize", "minimize", "restore", "tile", "focus", "list"],
                "description": "Window management operation (default: 'snap').",
            },
            "position": {
                "type": "STRING",
                "enum": ["left", "right", "top", "bottom", "top_left", "top_right", "bottom_left", "bottom_right", "center"],
                "description": "Grid position to snap the window to.",
            },
            "target": {
                "type": "STRING",
                "description": "Window title or substring to target (default: active foreground window).",
            },
            "hwnd": {
                "type": "INTEGER",
                "description": "Specific window handle (HWND) to target.",
            },
            "count": {
                "type": "INTEGER",
                "description": "Number of windows to tile (2 to 4, default: 2).",
            },
            "orientation": {
                "type": "STRING",
                "enum": ["vertical", "horizontal"],
                "description": "Tiling orientation (default: 'vertical').",
            },
        },
    },
    "handler": window_manager,
}
