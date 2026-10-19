"""Reproductions for the owner's October 19 robustness report."""
import io
import json
import os
import sqlite3
import subprocess
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import Mock, patch

from core import confirm
from core.mobile_bridge import AudioListener
from core.shell_session import ShellSessions, split_command, terminate_tree
from core.task_runtime import TaskRuntime
from core.tool_result import ToolResult


class TaskRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.runtime = TaskRuntime()
        self.addCleanup(self.runtime.db.close)

    def test_unknown_tool_status_fails_with_evidence_instead_of_crashing(self):
        task = self.runtime.create('Fixture work')
        tool_result = ToolResult('failed', 'Unsupported result', evidence=[{'observed': 1}])
        tool_result.status = 'custom_status'  # Defensive handling of a mutated legacy result.
        result = self.runtime.finish(task.id, tool_result)
        self.assertEqual(result.state, 'failed')
        self.assertEqual(result.error, 'Unsupported result')
        self.assertEqual(result.evidence, [{'observed': 1}])

    def test_late_success_preserves_cancellation_and_records_side_effect(self):
        task = self.runtime.create('Fixture work')
        self.runtime.transition(task.id, 'cancelled')
        with patch('core.task_runtime.bus.publish') as publish:
            result = self.runtime.finish(task.id, ToolResult('success', 'Changed before cancel arrived', side_effect=True))
        publish.assert_not_called()  # No duplicate completion alert from a late result.
        self.assertEqual(result.state, 'cancelled')
        self.assertEqual(len(result.side_effects), 1)

    def test_concurrent_completions_do_not_lose_evidence(self):
        task = self.runtime.create('Fixture work')
        with ThreadPoolExecutor(max_workers=4) as workers:
            list(workers.map(lambda i: self.runtime.finish(task.id,
                ToolResult('success', 'Finished', evidence=[{'item': i}])), range(12)))
        self.assertEqual(len(self.runtime.get(task.id).evidence), 12)

    def test_schema_drift_and_damaged_rows_cannot_brick_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'runtime.db'
            db = sqlite3.connect(path)
            db.execute('CREATE TABLE runtime_tasks (id TEXT PRIMARY KEY, payload TEXT NOT NULL)')
            db.executemany('INSERT INTO runtime_tasks VALUES (?, ?)', [
                ('old', json.dumps({'future_field': True, 'state': 'executing', 'id': 'wrong'})),
                ('damaged', '{broken'),
                ('nulls', json.dumps({'state': None, 'evidence': None, 'side_effects': None})),
            ])
            db.commit(); db.close()
            recovered = TaskRuntime(path)
            try:
                self.assertEqual(len(recovered.list()), 3)
                self.assertEqual(recovered.get('old').id, 'old')
                self.assertEqual(recovered.get('old').state, 'paused')
                self.assertEqual(recovered.get('nulls').evidence, [])
                self.assertEqual(recovered.get('damaged').state, 'paused')
            finally:
                recovered.db.close()


class ProcessCleanupTests(unittest.TestCase):
    @unittest.skipUnless(os.name == 'nt', 'Windows taskkill fallback')
    def test_taskkill_timeout_falls_back_to_child_kill(self):
        process = Mock(pid=123, poll=Mock(return_value=None))
        with patch('core.shell_session.subprocess.run', side_effect=subprocess.TimeoutExpired('taskkill', 10)):
            terminate_tree(process)
        process.kill.assert_called_once()

    def test_child_that_survives_cleanup_returns_timeout_and_releases_session(self):
        process = Mock(pid=123, returncode=None, stdout=io.BytesIO(b''), stderr=io.BytesIO(b''))
        process.wait.side_effect = subprocess.TimeoutExpired('fixture', 1)
        sessions = ShellSessions()
        with patch('core.shell_session.subprocess.Popen', return_value=process), \
                patch('core.shell_session.terminate_tree'):
            result = sessions.run_argv(['fixture'], Path.cwd(), timeout=.1, session_id='fixture')
        self.assertEqual(result.status, 'failed')
        self.assertTrue(result.data['timed_out'])
        self.assertIsNone(result.data['exit_code'])
        self.assertNotIn('fixture', sessions.processes)

    def test_quoted_arguments_and_windows_paths_are_not_split_or_unescaped(self):
        self.assertEqual(split_command('python main.py --name "my project"'),
                         ['python', 'main.py', '--name', 'my project'])
        if os.name == 'nt':
            self.assertEqual(split_command(r'"C:\Program Files\Python\python.exe" "C:\work here\main.py"'),
                             [r'C:\Program Files\Python\python.exe', r'C:\work here\main.py'])
        self.assertEqual(split_command('   '), [])


class ConfirmationRaceTests(unittest.TestCase):
    def test_old_expiry_cannot_cancel_or_hide_new_confirmation(self):
        old = confirm._Pending('old', 'Old', '', Mock(), 0)
        current = confirm._Pending('new', 'New', '', Mock(), 0)
        hide = Mock()
        with patch.object(confirm, '_pending', current), patch.object(confirm, '_hide_cb', hide):
            confirm.resolve(False, expected=old)
            self.assertIs(confirm._pending, current)
            hide.assert_not_called()
            current.run.assert_not_called()


class AudioBudgetTests(unittest.TestCase):
    def test_single_oversized_frame_is_dropped_without_discarding_valid_audio(self):
        listener = AudioListener(max_bytes=8, maxlen=2)
        listener.push(b'12')
        listener.push(b'x' * 10)
        self.assertEqual(listener.pending_bytes(), 2)
        self.assertEqual(listener.dropped, 1)
        self.assertEqual(listener.drain(), [b'12'])

    def test_byte_and_frame_eviction_account_for_the_same_oldest_frame(self):
        listener = AudioListener(max_bytes=6, maxlen=2)
        for data in (b'12', b'34', b'5678'):
            listener.push(data)
        self.assertEqual(listener.pending_bytes(), 6)
        self.assertEqual(listener.dropped, 1)
        self.assertEqual(listener.drain(), [b'34', b'5678'])
        self.assertEqual(listener.pending_bytes(), 0)


class ExistingBehaviorTests(unittest.TestCase):
    def test_dev_agent_uses_shared_key_abstraction(self):
        from actions import dev_agent
        with patch.object(dev_agent.gemini, 'api_key', return_value='fixture') as lookup:
            self.assertEqual(dev_agent._get_api_key(), 'fixture')
        lookup.assert_called_once()

    def test_dev_agent_runs_quoted_arguments_as_one_value(self):
        from actions import dev_agent
        with patch.object(dev_agent.subprocess, 'run', return_value=Mock(stdout='ok', stderr='')) as run:
            dev_agent._run_project('python main.py --name "my project"', Path.cwd())
        self.assertEqual(run.call_args.args[0][-1], 'my project')

    def test_empty_whatsapp_chat_has_numeric_watermark(self):
        from services.whatsapp.handler import ReplyWorker
        from services.whatsapp.store import WhatsAppStore
        store = WhatsAppStore()
        worker = ReplyWorker(store, Mock())
        try:
            self.assertEqual(worker._incoming_version('empty'), 0)
        finally:
            worker.close()
            worker.pool.shutdown(wait=True)
            store.db.close()

    def test_browser_log_uses_summary_without_serializing_result_data(self):
        from actions.browser_control import _log
        player = Mock()
        with patch('builtins.print') as output:
            _log(player, ToolResult('failed', 'Browser unavailable', data={'private': 'fixture'}))
        self.assertEqual(output.call_args.args, ('[Browser] Browser unavailable',))
        self.assertNotIn('fixture', player.write_log.call_args.args[0])
