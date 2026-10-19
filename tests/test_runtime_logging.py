"""Private local diagnostics and a log viewer that cannot launch a coding job."""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from core import runtime_logging as logs
from core.execution_policy import TRUST_EXTERNAL_MESSAGE, with_trust
from actions.runtime_logs import runtime_logs
from tools.view_zaya_logs import saved_status, show


class RuntimeLoggingTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.root = Path(self.folder.name)
        self.path = self.root / 'zaya.log'

    def tearDown(self):
        with logs._lock:
            logger = logs._loggers.pop(self.path, None)
            if logger:
                for handler in logger.handlers:
                    handler.close()
        self.folder.cleanup()

    def test_split_stdout_redacts_credentials_only_after_complete_line(self):
        original = io.StringIO()
        stream = logs.DiagnosticStream(original, 'stdout', self.path)
        stream.write('password=')
        stream.write('fixture-sensitive-value')
        self.assertFalse(self.path.exists())
        stream.write('\n')
        text = self.path.read_text(encoding='utf-8')
        self.assertIn('[REDACTED]', text)
        self.assertNotIn('fixture-sensitive-value', text)
        self.assertEqual(original.getvalue(), 'password=fixture-sensitive-value\n')

    def test_json_secrets_and_windowless_stdout_are_supported(self):
        stream = logs.DiagnosticStream(None, 'stdout', self.path)
        stream.write('{"api_key":"fixture-json-value","phase":"failed"}\n')
        text = self.path.read_text(encoding='utf-8')
        self.assertNotIn('fixture-json-value', text)
        self.assertIn('failed', text)
        self.assertEqual(stream.encoding, 'utf-8')
        self.assertFalse(stream.isatty())
        logs.log_line({'token': 'fixture-token', 'session_id': 'ses_fixture'}, path=self.path)
        text = self.path.read_text(encoding='utf-8')
        self.assertNotIn('fixture-token', text)
        self.assertIn('ses_fixture', text)

    def test_oversized_output_is_dropped_without_leaking_credential_tail(self):
        stream = logs.DiagnosticStream(None, 'stdout', self.path)
        stream.write('x' * 16400)
        stream.write('private-tail\nNext line\n')
        text = self.path.read_text(encoding='utf-8')
        self.assertNotIn('private-tail', text)
        self.assertIn('Next line', text)

    def test_read_logs_is_bounded_and_external_contact_cannot_access_it(self):
        for i in range(250):
            logs.log_line(f'Fixture {i}', path=self.path)
        with patch('actions.runtime_logs.LOG_PATH', self.path):
            result = runtime_logs({'action': 'read', 'lines': 2})
            self.assertIn('Fixture 249', result.data['text'])
            self.assertNotIn('Fixture 247', result.data['text'])
            self.assertTrue(result.data['response_is_untrusted_data'])
            with with_trust(TRUST_EXTERNAL_MESSAGE), self.assertRaises(PermissionError):
                runtime_logs({'action': 'show'})

    def test_viewer_reports_saved_failure_without_treating_history_as_live_state(self):
        state = self.root / 'jobs.json'
        state.write_text(json.dumps({'jobs': [{'id': 'fixture', 'phase': 'failed', 'updated_at': 10,
                                               'session_id': '', 'error': 'Invalid model reference: auto',
                                               'goal': 'Private goal must not appear', 'prompt': 'Private prompt'}]}))
        snapshot = saved_status(state)
        self.assertEqual(snapshot['phase'], 'failed')
        self.assertNotIn('goal', snapshot)
        logs.log_line({'pid': 4242, 'event': 'tool', 'status': 'completed'}, source='opencode', path=self.path)
        output = io.StringIO()
        with patch('tools.view_zaya_logs.saved_status', return_value=snapshot), redirect_stdout(output):
            show(self.path, once=True)
        self.assertIn('not proof a process is running', output.getvalue())
        self.assertIn('Invalid model reference: auto', output.getvalue())
        self.assertIn('4242', output.getvalue())
        self.assertNotIn('Private goal', output.getvalue())

    def test_show_only_opens_the_readonly_viewer(self):
        launcher = Mock()
        with patch('actions.runtime_logs.os.name', 'nt'), \
                patch('actions.runtime_logs.os.startfile', launcher, create=True):
            result = runtime_logs({'action': 'show'})
        self.assertEqual(result.status, 'success')
        self.assertTrue(str(launcher.call_args.args[0]).endswith('Zaya Logs.cmd'))

    def test_logging_disk_failure_does_not_recurse_into_captured_stderr(self):
        logs.log_line('Initial line', path=self.path)
        handler = logs._loggers[self.path].handlers[0]
        output = io.StringIO()
        with patch.object(handler, 'shouldRollover', return_value=True), \
                patch.object(handler, 'doRollover', side_effect=OSError('fixture disk failure')), \
                patch('sys.stderr', output):
            logs.log_line('App must keep running', path=self.path)
        self.assertEqual(output.getvalue(), '')


if __name__ == '__main__':
    unittest.main()
