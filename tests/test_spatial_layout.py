"""Tests for Spatial Layout Engine and Action.
Created and developed by Sajan Rai for Zaya.
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, Dict, List
import pytest

from core.execution_policy import TRUST_EXTERNAL_MESSAGE, with_trust
from core.spatial_layout import SpatialLayoutEngine
from actions.spatial_layout_action import spatial_layout


@pytest.fixture
def temp_layout_engine(monkeypatch):
    mock_windows = [
        {"hwnd": 1001, "title": "Visual Studio Code - Zaya", "bounds": {"x": 0, "y": 0, "width": 800, "height": 600}},
        {"hwnd": 1002, "title": "Google Chrome - GitHub", "bounds": {"x": 800, "y": 0, "width": 800, "height": 600}},
        {"hwnd": 1003, "title": "Windows Terminal", "bounds": {"x": 0, "y": 600, "width": 800, "height": 400}},
    ]
    moved = []

    def mock_set_geom(hwnd: int, x: int, y: int, w: int, h: int) -> bool:
        moved.append({"hwnd": hwnd, "x": x, "y": y, "w": w, "h": h})
        return True

    monkeypatch.setattr("core.spatial_layout._list_visible_windows", lambda: mock_windows)
    monkeypatch.setattr("core.spatial_layout._get_work_area", lambda: (0, 0, 1920, 1080))
    monkeypatch.setattr("core.spatial_layout._set_window_geometry", mock_set_geom)

    with tempfile.TemporaryDirectory() as td:
        storage_path = Path(td) / "test_layouts.json"
        engine = SpatialLayoutEngine(storage_path=storage_path)
        yield engine, moved


def test_apply_developer_split(temp_layout_engine):
    engine, moved = temp_layout_engine
    res = engine.apply_preset("developer_split")
    assert res["preset"] == "developer_split"
    assert res["arranged_count"] == 3
    assert len(moved) == 3
    # Check primary 60% width
    assert moved[0]["w"] == int(1920 * 0.60)
    assert moved[0]["h"] == 1080


def test_apply_dual_split(temp_layout_engine):
    engine, moved = temp_layout_engine
    moved.clear()
    res = engine.apply_preset("dual_split")
    assert res["arranged_count"] == 2
    assert moved[0]["w"] == 1920 // 2
    assert moved[1]["x"] == 1920 // 2


def test_apply_focus_center(temp_layout_engine):
    engine, moved = temp_layout_engine
    moved.clear()
    res = engine.apply_preset("focus_center")
    assert res["arranged_count"] == 1
    assert moved[0]["w"] == int(1920 * 0.80)


def test_save_and_restore_layout(temp_layout_engine):
    engine, moved = temp_layout_engine
    save_res = engine.save_current_layout("coding_setup")
    assert save_res["windows_captured"] == 3

    # Re-open with new engine instance
    engine2 = SpatialLayoutEngine(storage_path=engine.storage_path)
    layouts = engine2.list_layouts()
    assert "coding_setup" in layouts["custom_layouts"]

    moved.clear()
    restore_res = engine2.restore_layout("coding_setup")
    assert restore_res["restored_count"] == 3
    assert len(moved) == 3


def test_spatial_layout_action(temp_layout_engine, monkeypatch):
    engine, _ = temp_layout_engine
    monkeypatch.setattr("actions.spatial_layout_action.get_spatial_layout_engine", lambda: engine)

    # Apply preset
    res_apply = spatial_layout({"action": "apply_preset", "preset": "developer_split"})
    assert res_apply.status == "success"

    # List
    res_list = spatial_layout({"action": "list"})
    assert res_list.status == "success"
    assert "developer_split" in res_list.data["presets"]

    # Unauthorized access check
    with with_trust(TRUST_EXTERNAL_MESSAGE):
        with pytest.raises(PermissionError):
            spatial_layout({"action": "apply_preset"})
