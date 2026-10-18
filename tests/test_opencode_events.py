"""Offline checks for the event stream consumed by coding-job narration."""
import json
import unittest

from core.opencode_events import Tally, parse_line


class OpenCodeEventTests(unittest.TestCase):
    def test_text_and_session_are_extracted(self):
        event = parse_line(json.dumps({
            'type': 'text', 'sessionID': 'ses_example',
            'part': {'text': 'I found a problem.'},
        }))
        self.assertEqual((event.kind, event.session_id, event.text),
                         ('text', 'ses_example', 'I found a problem.'))

    def test_edit_metadata_and_failed_tool_are_recorded(self):
        tally = Tally()
        tally.add(parse_line(json.dumps({
            'type': 'tool_use', 'sessionID': 'ses_example',
            'part': {'tool': 'edit', 'state': {'status': 'completed',
                'input': {'path': 'src/app.py'},
                'metadata': {'files': [{'file': 'src/app.py', 'additions': 2, 'deletions': 1}]}}},
        })))
        tally.add(parse_line(json.dumps({
            'type': 'tool_use', 'part': {'tool': 'shell', 'state': {
                'status': 'error', 'input': {'command': 'pytest'}, 'output': 'failed'}},
        })))
        self.assertEqual(tally.session_id, 'ses_example')
        self.assertEqual((tally.changed, tally.additions, tally.deletions), (['src/app.py'], 2, 1))
        self.assertEqual((tally.failures, tally.last_error), (1, 'failed'))

    def test_noise_and_malformed_lines_are_ignored(self):
        for line in ('', 'not json', '{bad json', '[]', '{}'):
            with self.subTest(line=line):
                self.assertIsNone(parse_line(line))


if __name__ == '__main__':
    unittest.main()
