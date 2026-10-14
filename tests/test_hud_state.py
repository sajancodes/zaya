import unittest
from core.hud_state import label


class HUDStateTests(unittest.TestCase):
    def test_real_state_is_shown(self):
        self.assertEqual(label({'event': 'task.updated', 'task': {'active_step': 'git_control', 'state': 'verifying'}}), 'Git operation · verifying')
        self.assertIn('awaiting complete feed', label({'event': 'whatsapp.mode.changed', 'mode': 'auto'}))
