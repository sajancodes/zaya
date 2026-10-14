import unittest
from core.tool_result import ToolResult, normalize, truncate


class ResultTests(unittest.TestCase):
    def test_legacy_is_not_verified(self):
        self.assertEqual(normalize('Message sent').status, 'partial')
        self.assertFalse(normalize('Message sent').data['verified'])

    def test_structured_roundtrip(self):
        r = ToolResult('success', 'Done', evidence=[{'exit_code': 0}])
        self.assertEqual(normalize(r.to_dict()), r)
        with self.assertRaises(ValueError):
            ToolResult('imagined', 'Done')

    def test_utf8_head_tail_truncation(self):
        text, shortened = truncate('start' + '🙂' * 300 + 'end', 200)
        self.assertTrue(shortened)
        self.assertTrue(text.startswith('start'))
        self.assertTrue(text.endswith('end'))
        self.assertLess(len(text.encode()), 220)
