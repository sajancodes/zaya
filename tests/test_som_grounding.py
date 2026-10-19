"""Tests for Set-of-Mark (SoM) and 3-tier UI element grounding and frame_changed."""
import io
import unittest
from unittest.mock import MagicMock, patch
from PIL import Image

from actions.screen_processor import compute_dhash, hamming_distance, frame_changed
from actions.computer_control import _screen_find, _find_via_uia, _find_via_som, _find_via_coordinates


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
