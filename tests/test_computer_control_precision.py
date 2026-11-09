"""Tests for high-precision computer control, DPI scaling, and multi-tier grounding."""
import json
import unittest
from unittest.mock import MagicMock, patch
from PIL import Image

import actions.computer_control as cc


class TestComputerControlPrecision(unittest.TestCase):

    def test_screen_metrics_structure(self):
        metrics = cc.get_screen_metrics()
        self.assertIn("primary_w", metrics)
        self.assertIn("primary_h", metrics)
        self.assertIn("logical_w", metrics)
        self.assertIn("logical_h", metrics)
        self.assertIn("scale_x", metrics)
        self.assertIn("scale_y", metrics)
        self.assertGreater(metrics["primary_w"], 0)
        self.assertGreater(metrics["primary_h"], 0)

    @patch("actions.computer_control.get_screen_metrics")
    def test_to_logical_coords_normalized_1000(self, mock_metrics):
        # Primary display 1920x1080
        mock_metrics.return_value = {
            "primary_w": 1920,
            "primary_h": 1080,
            "logical_w": 1536,
            "logical_h": 864,
            "scale_x": 1.25,
            "scale_y": 1.25,
        }
        # Center of normalized [0..1000] space
        cx, cy = cc.to_logical_coords(500, 500, 1000, 1000)
        self.assertEqual(cx, 960)
        self.assertEqual(cy, 540)

        # Top-left corner
        tl_x, tl_y = cc.to_logical_coords(0, 0, 1000, 1000)
        self.assertEqual(tl_x, 0)
        self.assertEqual(tl_y, 0)

        # Bottom-right corner (clamped to target_w - 1, target_h - 1)
        br_x, br_y = cc.to_logical_coords(1000, 1000, 1000, 1000)
        self.assertEqual(br_x, 1919)
        self.assertEqual(br_y, 1079)

    @patch("actions.computer_control.get_screen_metrics")
    def test_to_logical_coords_screenshot_scaling(self, mock_metrics):
        mock_metrics.return_value = {
            "primary_w": 1920,
            "primary_h": 1080,
            "logical_w": 1920,
            "logical_h": 1080,
            "scale_x": 1.0,
            "scale_y": 1.0,
        }
        # 4K screenshot (3840x2160) mapped to 1080p
        mapped_x, mapped_y = cc.to_logical_coords(1920, 1080, 3840, 2160)
        self.assertEqual(mapped_x, 960)
        self.assertEqual(mapped_y, 540)

    @patch("actions.computer_control.subprocess.run")
    @patch("actions.computer_control.get_screen_metrics")
    def test_find_via_ocr_exact_match(self, mock_metrics, mock_subproc):
        mock_metrics.return_value = {
            "primary_w": 1920,
            "primary_h": 1080,
            "logical_w": 1920,
            "logical_h": 1080,
            "scale_x": 1.0,
            "scale_y": 1.0,
        }
        mock_res = MagicMock()
        mock_res.returncode = 0
        mock_res.stdout = json.dumps([
            {
                "text": "Create post",
                "words": [
                    {"text": "Create", "x": 200, "y": 300, "w": 60, "h": 24},
                    {"text": "post", "x": 265, "y": 300, "w": 45, "h": 24},
                ]
            }
        ])
        mock_subproc.return_value = mock_res

        dummy_img = Image.new("RGB", (1920, 1080))
        coords = cc._find_via_ocr("Create post", dummy_img, 1920, 1080)
        self.assertIsNotNone(coords)
        # Bounding box is from x=200 to x=310, y=300 to y=324. Center: x=255, y=312
        self.assertEqual(coords, (255, 312))

    @patch("actions.computer_control.get_screen_metrics")
    @patch("core.gemini.call")
    def test_find_via_coordinates_normalized_point(self, mock_gemini, mock_metrics):
        mock_metrics.return_value = {
            "primary_w": 1920,
            "primary_h": 1080,
            "logical_w": 1920,
            "logical_h": 1080,
            "scale_x": 1.0,
            "scale_y": 1.0,
        }
        mock_resp = MagicMock()
        mock_resp.text = json.dumps({"point": [400, 600], "label": "Share"})
        mock_gemini.return_value = mock_resp

        coords = cc._find_via_coordinates("Share", b"dummy_bytes", 1920, 1080)
        self.assertIsNotNone(coords)
        # norm_x = 600 (60% of 1920 = 1152), norm_y = 400 (40% of 1080 = 432)
        self.assertEqual(coords, (1152, 432))

    @patch("actions.computer_control.get_screen_metrics")
    @patch("core.gemini.call")
    def test_find_via_coordinates_bbox(self, mock_gemini, mock_metrics):
        mock_metrics.return_value = {
            "primary_w": 1920,
            "primary_h": 1080,
            "logical_w": 1920,
            "logical_h": 1080,
            "scale_x": 1.0,
            "scale_y": 1.0,
        }
        mock_resp = MagicMock()
        # [ymin, xmin, ymax, xmax]
        mock_resp.text = json.dumps({"box_2d": [200, 100, 400, 500]})
        mock_gemini.return_value = mock_resp

        coords = cc._find_via_coordinates("Submit button", b"dummy_bytes", 1920, 1080)
        self.assertIsNotNone(coords)
        # Center: norm_y = 300 (30% of 1080 = 324), norm_x = 300 (30% of 1920 = 576)
        self.assertEqual(coords, (576, 324))

    @patch("actions.computer_control.get_screen_metrics")
    @patch("core.gemini.call")
    def test_find_via_coordinates_not_found(self, mock_gemini, mock_metrics):
        mock_metrics.return_value = {"primary_w": 1920, "primary_h": 1080, "logical_w": 1920, "logical_h": 1080, "scale_x": 1.0, "scale_y": 1.0}
        mock_resp = MagicMock()
        mock_resp.text = '{"point": null}'
        mock_gemini.return_value = mock_resp

        coords = cc._find_via_coordinates("Nonexistent element", b"dummy_bytes", 1920, 1080)
        self.assertIsNone(coords)

    @patch("actions.computer_control._screen_find")
    @patch("actions.computer_control._click")
    def test_computer_control_auto_resolves_description(self, mock_click, mock_screen_find):
        mock_screen_find.return_value = (850, 420)
        mock_click.return_value = "Clicked (850, 420) [left]"

        # Call action="click" without x and y, but with description
        res = cc.computer_control({"action": "click", "description": "Create post"})
        mock_screen_find.assert_called_with("Create post")
        mock_click.assert_called_with(850, 420, "left", 1)
        self.assertIn("Clicked (850, 420)", res)

    @patch("actions.computer_control._screen_find")
    def test_computer_control_element_not_found_message(self, mock_screen_find):
        mock_screen_find.return_value = None

        res = cc.computer_control({"action": "click", "description": "Missing button"})
        self.assertEqual(res, "Element not found on screen: 'Missing button'")

    @patch("actions.computer_control._click")
    def test_computer_control_explicit_coords(self, mock_click):
        mock_click.return_value = "Clicked (100, 200) [left]"

        res = cc.computer_control({"action": "click", "x": 100, "y": 200})
        mock_click.assert_called_with(100, 200, "left", 1)
        self.assertIn("Clicked (100, 200)", res)

    @patch("actions.computer_control._screen_find")
    @patch("actions.computer_control._move")
    def test_computer_control_move_auto_resolves(self, mock_move, mock_screen_find):
        mock_screen_find.return_value = (500, 600)
        mock_move.return_value = "Mouse → (500, 600)"

        res = cc.computer_control({"action": "move", "label": "Search bar"})
        mock_screen_find.assert_called_with("Search bar")
        mock_move.assert_called_with(500, 600)
        self.assertIn("Mouse → (500, 600)", res)

    def test_tool_declaration(self):
        self.assertEqual(cc.TOOL["name"], "computer_control")
        self.assertEqual(cc.TOOL["handler"], cc.computer_control)
        props = cc.TOOL["parameters"]["properties"]
        self.assertIn("action", props)
        self.assertIn("description", props)
        self.assertIn("x", props)
        self.assertIn("y", props)


if __name__ == "__main__":
    unittest.main()
