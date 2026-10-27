import unittest
from unittest.mock import patch, MagicMock
from actions.screen_peeler import screen_peeler, extract_text_from_region

class TestScreenPeeler(unittest.TestCase):
    @patch("actions.screen_peeler.pyperclip.copy")
    @patch("actions.screen_peeler.extract_text_from_region")
    def test_screen_peeler_success(self, mock_extract, mock_copy):
        mock_extract.return_value = "def test_func():\n    return True"
        
        result = screen_peeler({"region": [100, 100, 500, 400]})
        
        self.assertIn("def test_func()", result)
        mock_copy.assert_called_with("def test_func():\n    return True")

    def test_screen_peeler_empty_region(self):
        with patch("actions.screen_peeler.extract_text_from_region", return_value=""):
            result = screen_peeler({"action": "full"})
            self.assertIn("No text could be extracted", result)

if __name__ == "__main__":
    unittest.main()
