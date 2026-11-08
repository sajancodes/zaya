"""Unit tests for Window Organizer & Snap Layout Manager.
Created and developed by Sajan Rai for Zaya.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch
import pytest

from actions.window_manager import (
    TOOL,
    _find_window_by_title,
    _get_foreground_window,
    _get_window_title,
    _get_work_area,
    _list_visible_windows,
    _set_window_geometry,
    _snap_window,
    _tile_windows,
    window_manager,
)
from core.execution_policy import TRUST_EXTERNAL_MESSAGE, TRUST_LOCAL_OWNER, with_trust
from core.fast_reflex import FastReflexRouter
from core.tools.routing import ToolRouter


def test_window_manager_requires_owner():
    with with_trust(TRUST_EXTERNAL_MESSAGE):
        with pytest.raises(PermissionError):
            window_manager({"action": "list"})


def test_window_manager_work_area():
    wl, wt, ww, wh = _get_work_area()
    assert ww > 0
    assert wh > 0


def test_window_manager_list():
    with with_trust(TRUST_LOCAL_OWNER):
        res_raw = window_manager({"action": "list"})
        res = json.loads(res_raw)
        assert res["status"] == "success"
        assert isinstance(res["data"], list)


def test_window_manager_snap_mocked():
    with patch("actions.window_manager._get_foreground_window", return_value=12345), \
         patch("actions.window_manager._set_window_geometry", return_value=True), \
         patch("actions.window_manager._get_window_title", return_value="Test Editor"):
        with with_trust(TRUST_LOCAL_OWNER):
            res_raw = window_manager({"action": "snap", "position": "left"})
            res = json.loads(res_raw)
            assert res["status"] == "success"
            assert "Snapped 'Test Editor' to left" in res["summary"]
            assert res["data"]["position"] == "left"


def test_window_manager_center_mocked():
    with patch("actions.window_manager._get_foreground_window", return_value=12345), \
         patch("actions.window_manager._set_window_geometry", return_value=True), \
         patch("actions.window_manager._get_window_title", return_value="Test Editor"):
        with with_trust(TRUST_LOCAL_OWNER):
            res_raw = window_manager({"action": "center"})
            res = json.loads(res_raw)
            assert res["status"] == "success"
            assert "Centered 'Test Editor' on screen" in res["summary"]


def test_window_manager_maximize_mocked():
    with patch("actions.window_manager._get_foreground_window", return_value=12345), \
         patch("ctypes.windll.user32.ShowWindow", return_value=1), \
         patch("actions.window_manager._get_window_title", return_value="Browser"):
        with with_trust(TRUST_LOCAL_OWNER):
            res_raw = window_manager({"action": "maximize"})
            res = json.loads(res_raw)
            assert res["status"] == "success"
            assert "Maximized 'Browser'" in res["summary"]


def test_window_manager_tile_mocked():
    mock_windows = [
        {"hwnd": 101, "title": "Editor A", "pid": 1, "bounds": {"x": 0, "y": 0, "width": 500, "height": 500}},
        {"hwnd": 102, "title": "Terminal B", "pid": 2, "bounds": {"x": 500, "y": 0, "width": 500, "height": 500}},
    ]
    with patch("actions.window_manager._list_visible_windows", return_value=mock_windows), \
         patch("actions.window_manager._set_window_geometry", return_value=True):
        with with_trust(TRUST_LOCAL_OWNER):
            res_raw = window_manager({"action": "tile", "count": 2, "orientation": "vertical"})
            res = json.loads(res_raw)
            assert res["status"] == "success"
            assert "Tiled 2 windows vertically" in res["summary"]
            assert res["data"]["count"] == 2


def test_tool_declaration_schema():
    assert TOOL["name"] == "window_manager"
    assert "snap" in TOOL["parameters"]["properties"]["action"]["enum"]
    assert "center" in TOOL["parameters"]["properties"]["action"]["enum"]
    assert "tile" in TOOL["parameters"]["properties"]["action"]["enum"]
    assert callable(TOOL["handler"])


def test_fast_reflex_window_manager():
    router = FastReflexRouter()
    
    intent, score = router.match("snap left")
    assert intent == "WINDOW_SNAP_LEFT"
    assert score >= 0.88

    intent, score = router.match("snap right")
    assert intent == "WINDOW_SNAP_RIGHT"
    assert score >= 0.88

    intent, score = router.match("center window")
    assert intent == "WINDOW_CENTER"
    assert score >= 0.88

    intent, score = router.match("maximize window")
    assert intent == "WINDOW_MAXIMIZE"
    assert score >= 0.88

    with patch("actions.window_manager._get_foreground_window", return_value=12345), \
         patch("actions.window_manager._set_window_geometry", return_value=True), \
         patch("actions.window_manager._get_window_title", return_value="Active Code"):
        res = router.execute_intent("WINDOW_SNAP_LEFT")
        assert res.matched is True
        assert "Window snapped to the left" in res.ack


def test_tool_router_maps_window_manager():
    router = ToolRouter()
    declarations = [
        {"name": "window_manager", "description": "snap and tile windows"},
        {"name": "web_search", "description": "search web"},
    ]
    routed = router.route("snap this window to the left and center layout", declarations)
    names = [d["name"] for d in routed.declarations]
    assert "window_manager" in names
