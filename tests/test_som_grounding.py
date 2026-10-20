"""Tests for Set-of-Mark (SoM), OpenCV visual detection, and 3-tier UI element grounding."""
import io
import unittest
from unittest.mock import MagicMock, patch
from PIL import Image

from actions.screen_processor import compute_dhash, hamming_distance, frame_changed
from actions.computer_control import (
    _screen_find,
    _find_via_uia,
    _find_via_som,
    _find_via_coordinates,
    _detect_visual_candidates,
)


class TestGroundingAndVision(unittest.TestCase):
    def test_dhash_and_hamming(self):
        img1 = Image.new("RGB", (100, 100), color=(255, 255, 255))
        buf1 = io.BytesIO()
        img1.save(buf1, format="PNG")
        bytes1 = buf1.getvalue()

        img2 = Image.new("RGB", (100, 100), color=(0, 0, 0))
        buf2 = io.BytesIO()
        img2.save(buf2, format="PNG")
        bytes2 = buf2.getvalue()

        h1 = compute_dhash(bytes1)
        h2 = compute_dhash(bytes2)
        self.assertIsNotNone(h1)
        self.assertIsNotNone(h2)

        # Distance between identical images is 0
        self.assertEqual(hamming_distance(h1, h1), 0)

    def test_frame_changed(self):
        img1 = Image.new("RGB", (64, 64), color=(20, 20, 20))
        buf1 = io.BytesIO()
        img1.save(buf1, format="PNG")
        bytes1 = buf1.getvalue()

        # Create checkerboard pattern image
        img2 = Image.new("RGB", (64, 64), color=(255, 255, 255))
        for y in range(0, 64, 8):
            for x in range(0, 64, 8):
                if (x // 8 + y // 8) % 2 == 0:
                    for py in range(y, min(64, y + 8)):
                        for px in range(x, min(64, x + 8)):
                            img2.putpixel((px, py), (0, 0, 0))
        buf2 = io.BytesIO()
        img2.save(buf2, format="PNG")
        bytes2 = buf2.getvalue()

        # Initial frame always registers change
        src = "test_cam_source"
        self.assertTrue(frame_changed(src, bytes1, threshold=4))

        # Same frame without change returns False
        self.assertFalse(frame_changed(src, bytes1, threshold=4))

        # Distinct pattern frame returns True
        self.assertTrue(frame_changed(src, bytes2, threshold=4))

    def test_detect_visual_candidates_opencv(self):
        # Create an image with distinct buttons
        img = Image.new("RGB", (800, 600), color=(240, 240, 240))
        # Draw two high contrast rectangles simulating buttons
        from PIL import ImageDraw
        draw = ImageDraw.Draw(img)
        draw.rectangle([100, 100, 250, 160], fill=(50, 50, 200), outline=(0, 0, 0))
        draw.rectangle([400, 300, 550, 360], fill=(50, 200, 50), outline=(0, 0, 0))

        cands = _detect_visual_candidates(img, 800, 600, max_candidates=10)
        self.assertGreaterEqual(len(cands), 2)
        # Verify centers are inside button regions
        centers = [c["center"] for c in cands]
        has_first = any(95 <= pt[0] <= 255 and 95 <= pt[1] <= 165 for pt in centers)
        has_second = any(395 <= pt[0] <= 555 and 295 <= pt[1] <= 365 for pt in centers)
        self.assertTrue(has_first)
        self.assertTrue(has_second)

    def test_som_strict_json_validation(self):
        img = Image.new("RGB", (400, 300), color=(255, 255, 255))
        # Fake candidate. The accessibility-tree harvest is patched out too:
        # it reads the LIVE desktop, so without this the test's result
        # depended on whatever windows happened to be open on the machine
        # running it (and it failed outright on Windows).
        with patch("actions.computer_control._detect_uia_candidates", return_value=[]), \
             patch("actions.computer_control._detect_visual_candidates") as mock_cand:
            mock_cand.return_value = [
                {"box": (50, 50, 150, 100), "center": (100, 75)},
                {"box": (200, 50, 300, 100), "center": (250, 75)},
            ]

            # 1. Valid JSON matching tag 2
            mock_resp = MagicMock()
            mock_resp.text = '{"id": 2}'
            with patch("core.gemini.call", return_value=mock_resp):
                pt = _find_via_som("Green button", img, 400, 300)
                self.assertEqual(pt, (250, 75))

            # 2. Valid JSON with null id -> not found
            mock_resp_null = MagicMock()
            mock_resp_null.text = '{"id": null}'
            with patch("core.gemini.call", return_value=mock_resp_null):
                pt_null = _find_via_som("Nonexistent", img, 400, 300)
                self.assertIsNone(pt_null)

            # 3. Invalid tag id outside range
            mock_resp_out = MagicMock()
            mock_resp_out.text = '{"id": 99}'
            with patch("core.gemini.call", return_value=mock_resp_out):
                pt_out = _find_via_som("Out of range", img, 400, 300)
                self.assertIsNone(pt_out)

    def test_screen_find_tier_a_uia(self):
        with patch("actions.computer_control._find_via_uia") as mock_uia:
            mock_uia.return_value = (150, 250)
            coords = _screen_find("Save Button")
            self.assertEqual(coords, (150, 250))
            mock_uia.assert_called_once_with("Save Button")

    def test_screen_find_tier_b_som_fallback(self):
        with patch("actions.computer_control._find_via_uia", return_value=None), \
             patch("actions.computer_control._require_pyautogui"), \
             patch("actions.computer_control.pyautogui.size", return_value=(1920, 1080)), \
             patch("actions.computer_control.pyautogui.screenshot", return_value=Image.new("RGB", (100, 100))), \
             patch("actions.computer_control._find_via_som", return_value=(300, 400)) as mock_som:
            coords = _screen_find("Submit")
            self.assertEqual(coords, (300, 400))
            mock_som.assert_called_once()

    def test_screen_find_tier_c_coordinate_fallback(self):
        with patch("actions.computer_control._find_via_uia", return_value=None), \
             patch("actions.computer_control._require_pyautogui"), \
             patch("actions.computer_control.pyautogui.size", return_value=(1920, 1080)), \
             patch("actions.computer_control.pyautogui.screenshot", return_value=Image.new("RGB", (100, 100))), \
             patch("actions.computer_control._find_via_som", return_value=None), \
             patch("actions.computer_control._find_via_coordinates", return_value=(500, 600)) as mock_coord:
            coords = _screen_find("Settings Icon")
            self.assertEqual(coords, (500, 600))
            mock_coord.assert_called_once()


if __name__ == "__main__":
    unittest.main()
