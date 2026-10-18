import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from actions.avatar_expression import avatar_expression
from core.zayabar_config import DEFAULT_TONES, emotion_tones


class EmotionalDeliveryTests(unittest.TestCase):
    def test_one_selection_drives_face_and_voice(self):
        with patch('actions.avatar_expression.bus.publish') as publish:
            for emotion in DEFAULT_TONES:
                result = avatar_expression({'emotion': emotion})
                self.assertEqual(result.status, 'success')
                self.assertEqual(result.data['emotion'], emotion)
                self.assertTrue(result.data['voice_tone'])
                self.assertEqual(publish.call_args.kwargs['voice_tone'], result.data['voice_tone'])
                self.assertEqual(publish.call_args.kwargs['emotion'], emotion)
            self.assertEqual(avatar_expression({'emotion': 'unknown'}).status, 'failed')

    def test_custom_tones_and_invalid_config_fallback(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'zayabar.json'
            path.write_text(json.dumps({'emotion_tones': {'happy': 'Bright and bubbly'}}))
            self.assertEqual(emotion_tones(path)['happy'], 'Bright and bubbly')
            self.assertEqual(emotion_tones(path)['sad'], DEFAULT_TONES['sad'])
            path.write_text('{bad json')
            self.assertEqual(emotion_tones(path), DEFAULT_TONES)

    def test_personality_is_expressive_and_keeps_truth_and_trust(self):
        prompt = (Path(__file__).resolve().parents[1] / 'core' / 'prompt.txt').read_text(encoding='utf-8')
        self.assertIn('Jarvis-like manner', prompt)
        self.assertIn('face and delivery consistent', prompt)
        self.assertIn('answer honestly', prompt)
        self.assertIn('Tool evidence and runtime state', prompt)
        self.assertIn('untrusted data', prompt)
