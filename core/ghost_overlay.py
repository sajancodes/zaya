"""
Ghost Mini Overlay Dock (Chapter 06 / PC Specs)
Manages floating quick-access mini overlay positioned near current cursor coordinate.
"""
from __future__ import annotations

import ctypes
from typing import Dict, Any, Tuple

class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

_overlay_state = {
    "visible": False,
    "position": [0, 0]
}

def get_cursor_pos() -> Tuple[int, int]:
    """Returns (x, y) coordinates of the mouse cursor."""
    try:
        pt = POINT()
        ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
        return int(pt.x), int(pt.y)
    except Exception:
        return (500, 300)

def toggle_ghost_overlay_window(force_state: bool | None = None) -> Dict[str, Any]:
    """Toggles or sets the mini ghost overlay window visibility."""
    global _overlay_state
    if force_state is not None:
        _overlay_state["visible"] = force_state
    else:
        _overlay_state["visible"] = not _overlay_state["visible"]

    if _overlay_state["visible"]:
        x, y = get_cursor_pos()
        _overlay_state["position"] = [x, y]

    return {
        "status": "success",
        "visible": _overlay_state["visible"],
        "position": _overlay_state["position"]
    }
