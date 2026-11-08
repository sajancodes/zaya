"""Intelligent Spatial Multi-Window Layout Orchestrator for Zaya.
Created and developed by Sajan Rai.

Provides high-level workspace layout presets (developer_split, dual_split, quad_grid,
focus_center) and custom layout persistence for Jarvis-grade multi-window control.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from actions.window_manager import (
    _get_work_area,
    _list_visible_windows,
    _set_window_geometry,
)
from core.runtime_paths import mutable_path

logger = logging.getLogger(__name__)

_LAYOUTS_PATH = mutable_path(Path(__file__).resolve().parent.parent / "memory" / "workspace_layouts.json")


class SpatialLayoutEngine:
    """Manages workspace spatial window tiling, presets, and layout snapshots."""

    PRESETS = ("developer_split", "dual_split", "quad_grid", "focus_center")

    def __init__(self, storage_path: Optional[Path] = None) -> None:
        self.storage_path = storage_path or _LAYOUTS_PATH
        self._lock = threading.RLock()
        self._custom_layouts: dict[str, list[dict[str, Any]]] = {}
        self._load()

    def _load(self) -> None:
        with self._lock:
            if self.storage_path.exists():
                try:
                    self._custom_layouts = json.loads(self.storage_path.read_text(encoding="utf-8"))
                except Exception as exc:
                    logger.warning("Failed to load custom workspace layouts: %s", exc)

    def _save(self) -> None:
        with self._lock:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            self.storage_path.write_text(json.dumps(self._custom_layouts, indent=2), encoding="utf-8")

    def apply_preset(self, preset_name: str) -> dict[str, Any]:
        """Apply a predefined multi-window arrangement to visible top-level windows."""
        clean_name = preset_name.strip().lower()
        if clean_name not in self.PRESETS:
            raise ValueError(f"Unknown preset '{preset_name}'. Valid presets are: {', '.join(self.PRESETS)}.")

        windows = _list_visible_windows()
        if not windows:
            return {"preset": clean_name, "arranged": 0, "summary": "No visible windows to arrange."}

        wl, wt, ww, wh = _get_work_area()
        arranged = []

        if clean_name == "dual_split":
            # Left 50%, Right 50%
            half_w = ww // 2
            if len(windows) >= 1:
                _set_window_geometry(windows[0]["hwnd"], wl, wt, half_w, wh)
                arranged.append({"title": windows[0]["title"], "slot": "left_half"})
            if len(windows) >= 2:
                _set_window_geometry(windows[1]["hwnd"], wl + half_w, wt, half_w, wh)
                arranged.append({"title": windows[1]["title"], "slot": "right_half"})

        elif clean_name == "developer_split":
            # Primary on left 60%, secondary top right (40%w x 50%h), tertiary bottom right (40%w x 50%h)
            main_w = int(ww * 0.60)
            side_w = ww - main_w
            half_h = wh // 2
            if len(windows) >= 1:
                _set_window_geometry(windows[0]["hwnd"], wl, wt, main_w, wh)
                arranged.append({"title": windows[0]["title"], "slot": "code_primary_60pct"})
            if len(windows) >= 2:
                _set_window_geometry(windows[1]["hwnd"], wl + main_w, wt, side_w, half_h)
                arranged.append({"title": windows[1]["title"], "slot": "preview_top_right"})
            if len(windows) >= 3:
                _set_window_geometry(windows[2]["hwnd"], wl + main_w, wt + half_h, side_w, half_h)
                arranged.append({"title": windows[2]["title"], "slot": "terminal_bottom_right"})

        elif clean_name == "quad_grid":
            # Four equal quadrants
            half_w = ww // 2
            half_h = wh // 2
            slots = [
                ("top_left", wl, wt),
                ("top_right", wl + half_w, wt),
                ("bottom_left", wl, wt + half_h),
                ("bottom_right", wl + half_w, wt + half_h),
            ]
            for (slot_name, sx, sy), win in zip(slots, windows[:4]):
                _set_window_geometry(win["hwnd"], sx, sy, half_w, half_h)
                arranged.append({"title": win["title"], "slot": slot_name})

        elif clean_name == "focus_center":
            # Center primary window with 80% width and 85% height
            fw = int(ww * 0.80)
            fh = int(wh * 0.85)
            fx = wl + (ww - fw) // 2
            fy = wt + (wh - fh) // 2
            if len(windows) >= 1:
                _set_window_geometry(windows[0]["hwnd"], fx, fy, fw, fh)
                arranged.append({"title": windows[0]["title"], "slot": "focus_center_85pct"})

        summary = f"Applied '{clean_name}' spatial layout to {len(arranged)} window(s)."
        return {
            "preset": clean_name,
            "arranged_count": len(arranged),
            "arranged_windows": arranged,
            "summary": summary,
        }

    def save_current_layout(self, layout_name: str) -> dict[str, Any]:
        """Capture current visible windows coordinates and save as a custom named preset."""
        clean_name = layout_name.strip().lower()
        windows = _list_visible_windows()
        snapshot = [
            {"title": w["title"], "bounds": w["bounds"]}
            for w in windows
        ]
        with self._lock:
            self._custom_layouts[clean_name] = snapshot
            self._save()

        return {
            "name": clean_name,
            "windows_captured": len(snapshot),
            "summary": f"Saved layout '{clean_name}' with {len(snapshot)} window position(s).",
        }

    def restore_layout(self, layout_name: str) -> dict[str, Any]:
        """Restore window geometries from a saved custom layout."""
        clean_name = layout_name.strip().lower()
        with self._lock:
            saved = self._custom_layouts.get(clean_name)
        if not saved:
            raise KeyError(f"Custom layout '{clean_name}' not found.")

        current_windows = _list_visible_windows()
        restored = []

        for item in saved:
            t_sub = item["title"].lower()
            bounds = item["bounds"]
            # Match current window by title substring
            for cur in current_windows:
                if t_sub in cur["title"].lower() or cur["title"].lower() in t_sub:
                    _set_window_geometry(cur["hwnd"], bounds["x"], bounds["y"], bounds["width"], bounds["height"])
                    restored.append({"title": cur["title"], "bounds": bounds})
                    break

        return {
            "name": clean_name,
            "restored_count": len(restored),
            "restored_windows": restored,
            "summary": f"Restored {len(restored)} window(s) from layout '{clean_name}'.",
        }

    def list_layouts(self) -> dict[str, Any]:
        with self._lock:
            return {
                "presets": list(self.PRESETS),
                "custom_layouts": list(self._custom_layouts.keys()),
            }


_layout_engine: Optional[SpatialLayoutEngine] = None
_layout_lock = threading.Lock()


def get_spatial_layout_engine() -> SpatialLayoutEngine:
    global _layout_engine
    with _layout_lock:
        if _layout_engine is None:
            _layout_engine = SpatialLayoutEngine()
        return _layout_engine
