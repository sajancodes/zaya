"""Tests for Visual UI Graph & Actionable Screen Click Anchors (Cycle 70).
Created and developed by Sajan Rai for Zaya.
"""
from __future__ import annotations

import json
from unittest.mock import patch
import pytest

from core.visual_ui_graph import VisualUIGraph, UIAnchor
from actions.visual_anchor_action import handle_visual_anchors


class TestVisualUIGraph:
    def test_build_and_index_elements(self):
        graph = VisualUIGraph()
        elements = [
            {"label": "Submit", "bbox": [100, 200, 80, 30], "confidence": 0.95},
            {"label": "Search Google", "bbox": [300, 400, 200, 40], "confidence": 0.98},
            {"label": "Settings Icon", "bbox": [1800, 50, 32, 32]},
        ]
        anchors = graph.build_from_elements(elements, screen_size=(1920, 1080))
        assert len(anchors) == 3

        # Check anchor IDs and coordinates
        a1 = graph.find_anchor("1")
        assert a1 is not None
        assert a1.label == "Submit"
        assert a1.element_type == "button"
        assert a1.center == (140, 215)

        a2 = graph.find_anchor("Search Google")
        assert a2 is not None
        assert a2.id == 2
        assert a2.element_type == "input"

        a3 = graph.find_anchor("Settings Icon")
        assert a3 is not None
        assert a3.element_type == "icon"

    def test_find_anchor_fuzzy_and_case_insensitive(self):
        graph = VisualUIGraph()
        elements = [
            {"label": "Save Changes", "bbox": [50, 50, 100, 40]},
            {"label": "Discard Draft", "bbox": [200, 50, 100, 40]},
        ]
        graph.build_from_elements(elements)

        found = graph.find_anchor("save")
        assert found is not None
        assert found.label == "Save Changes"

        found_exact = graph.find_anchor("Discard Draft")
        assert found_exact is not None
        assert found_exact.label == "Discard Draft"

        assert graph.find_anchor("NonExistent") is None

    def test_resolve_click_target_bounds_checking(self):
        graph = VisualUIGraph()
        elements = [
            {"label": "Valid Button", "bbox": [100, 100, 50, 20]},
            {"label": "Offscreen Button", "bbox": [3000, 3000, 50, 20]},
        ]
        graph.build_from_elements(elements, screen_size=(1920, 1080))

        ok, coords, msg = graph.resolve_click_target("Valid Button")
        assert ok is True
        assert coords == (125, 110)

        ok2, coords2, msg2 = graph.resolve_click_target("Offscreen Button")
        assert ok2 is False
        assert coords2 is None
        assert "outside screen bounds" in msg2


class TestVisualAnchorAction:
    def test_action_build_and_list(self):
        elements = [
            {"label": "OK", "bbox": [500, 500, 60, 30]},
            {"label": "Cancel", "bbox": [600, 500, 60, 30]},
        ]
        build_res = handle_visual_anchors(action="build", elements_json=json.dumps(elements))
        build_data = json.loads(build_res)
        assert build_data["status"] == "success"
        assert build_data["count"] == 2

        list_res = handle_visual_anchors(action="list")
        list_data = json.loads(list_res)
        assert list_data["count"] == 2
        assert list_data["anchors"][0]["label"] == "OK"

    def test_action_resolve_and_click(self):
        elements = [{"label": "Login", "bbox": [400, 300, 100, 40]}]
        handle_visual_anchors(action="build", elements_json=json.dumps(elements))

        res_str = handle_visual_anchors(action="resolve", target="Login")
        res_data = json.loads(res_str)
        assert res_data["status"] == "success"
        assert res_data["center"] == [450, 320]

        import sys
        from unittest.mock import MagicMock
        fake_pyautogui = MagicMock()
        with patch.dict(sys.modules, {"pyautogui": fake_pyautogui}):
            click_str = handle_visual_anchors(action="click", target="Login")
            click_data = json.loads(click_str)
            assert click_data["status"] == "success"
            assert click_data["clicked"] == [450, 320]
            fake_pyautogui.click.assert_called_once_with(450, 320)
