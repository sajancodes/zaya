import unittest
from unittest.mock import patch
from memory import config_manager
from core import gemini


class VoiceTests(unittest.TestCase):
    def test_nika_is_default_and_supported_option(self):
        with patch.object(config_manager, 'load_api_keys', return_value={}):
            self.assertEqual(config_manager.get_voice(), 'Nika')
        self.assertIn('Nika', config_manager.AVAILABLE_VOICES)

    def test_nika_never_falls_back_to_incompatible_live_model(self):
        with patch.object(config_manager, 'get_voice', return_value='Nika'):
            self.assertIn('3.8', gemini.live_model())

    def test_live_default_is_centralized(self):
        self.assertEqual(gemini.LIVE_MODELS[0], 'models/gemini-3.8-live')
