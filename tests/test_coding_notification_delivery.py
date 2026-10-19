"""Actual archive contract, cancellation races and quiet development updates."""
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import AsyncMock, Mock, patch

from actions.coding_job import coding_job
from core.coding_jobs import CodingJobs
from core.task_runtime import TaskRuntime
from memory.conversation_store import ConversationStore
from tests.test_coding_jobs import CompleteSupervisor, Process, record, wait_for
from tests import test_coding_voice as voice_cases


class DeliveryTests(unittest.IsolatedAsyncioTestCase):
    def live(self):
        return voice_cases.CodingVoiceTests.live(self)

    async def test_real_conversation_archive_accepts_notice_exactly_once(self):
        with tempfile.TemporaryDirectory() as folder:
            live = self.live()
            live._conversation = ConversationStore(Path(folder) / 'chat.db')
            item = {'summary': 'The checks passed.'}
            with patch('core.notification_voice.synthesize_notice', new=AsyncMock(return_value=(b'voice', item['summary']))):
                self.assertTrue(await live._deliver_owner_notice(item, coding=True))
            turns = live._conversation.recent()
            self.assertEqual(turns[-1]['role'], 'model')
            self.assertEqual(turns[-1]['text'], item['summary'])
            self.assertEqual(live.audio_in_queue.qsize(), 1)

    async def test_archive_failure_after_queued_audio_is_still_delivered(self):
        live = self.live()
        live._conversation = Mock()
        live._conversation.append.side_effect = ValueError('fixture archive failure')
        with patch('core.notification_voice.synthesize_notice', new=AsyncMock(return_value=(b'voice', 'Checks passed.'))):
            self.assertTrue(await live._deliver_owner_notice({'summary': 'Checks passed.'}, coding=True))
        self.assertEqual(live.audio_in_queue.qsize(), 1)

    async def test_stop_during_synthesis_invalidates_inflight_notice(self):
        with tempfile.TemporaryDirectory() as folder:
            jobs = CodingJobs(Path(folder) / 'jobs.json')
            jobs._notice('Checks passed.')
            item = jobs.next_notice()
            live = self.live()
            async def synth(*_args, **_kwargs):
                jobs.stop()
                return b'old speech', 'Checks passed.'
            with patch('core.coding_jobs.get_jobs', return_value=jobs), patch('core.notification_voice.synthesize_notice', new=synth):
                self.assertFalse(await live._deliver_owner_notice(item, coding=True))
            self.assertTrue(live.audio_in_queue.empty())
            self.assertIsNone(jobs.next_notice())


class QuietUpdateTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.now = [1000.0]
        self.runtime = TaskRuntime()
        self.addCleanup(self.runtime.db.close)
        self.jobs = CodingJobs(self.root / 'jobs.json', runtime=self.runtime, clock=lambda: self.now[0])
        self.addCleanup(self.jobs.close)

    def test_interval_coalesces_changes_and_delivered_notice_never_repeats(self):
        self.jobs.configure_updates(interval_seconds=150)
        self.jobs._notice('First change.')
        self.now[0] += 100
        self.jobs._notice('Second change.')
        self.assertIsNone(self.jobs.next_notice())
        self.now[0] += 50
        item = self.jobs.next_notice()
        self.assertEqual(item['summary'], 'Second change.')
        self.jobs.delivered(item)
        self.jobs._notice('Second change.')
        self.now[0] += 151
        self.assertIsNone(self.jobs.next_notice())

    def test_stop_without_active_job_clears_orphaned_announcements(self):
        self.jobs._notice('Old planning notice.')
        with patch('actions.coding_job.get_jobs', return_value=self.jobs):
            first = coding_job({'action': 'stop'})
            second = coding_job({'action': 'stop'})
        self.assertEqual(first.status, 'success')
        self.assertEqual(second.status, 'success')
        self.assertFalse(first.data['process_running'])
        self.assertIsNone(self.jobs.next_notice())

    def test_closing_opencode_clears_worker_notices_and_reports_verified_absence(self):
        from actions.process_terminate import terminate_app
        self.jobs._notice('Old planning notice.')
        with patch('core.coding_jobs.get_jobs', return_value=self.jobs), \
                patch('actions.process_terminate._find_matches', return_value=('opencode.exe', [])):
            result = terminate_app({'app': 'OpenCode'})
        self.assertEqual(result.status, 'success')
        self.assertEqual(result.evidence[0]['matched_processes'], 0)
        self.assertIsNone(self.jobs.next_notice())
        self.jobs._notice('Late result must stay silent.')
        self.assertIsNone(self.jobs.next_notice())

    def test_silence_and_interval_survive_restart_without_replaying(self):
        self.jobs.configure_updates(enabled=False, interval_seconds=180)
        self.jobs._notice('Should be silent.')
        reopened = CodingJobs(self.jobs._path)
        self.assertEqual(reopened.update_settings(), {'enabled': False, 'interval_seconds': 180})
        self.assertIsNone(reopened.next_notice())
        with self.assertRaises(ValueError):
            self.jobs.configure_updates(interval_seconds=5)

    def test_voice_failures_back_off_and_stop_after_two_attempts(self):
        self.jobs._notice('Checks passed.')
        item = self.jobs.next_notice()
        self.jobs.notice_failed(item)
        self.assertIsNone(self.jobs.next_notice())
        self.now[0] += 150
        self.assertEqual(self.jobs.next_notice()['id'], item['id'])
        self.jobs.notice_failed(item)
        self.now[0] += 150
        self.assertIsNone(self.jobs.next_notice())

    def test_stop_during_planning_prevents_cli_launch_and_reports_pending_truthfully(self):
        entered, release = threading.Event(), threading.Event()
        planner = Mock()
        def prepare(*args):
            entered.set()
            release.wait(timeout=5)
            return CompleteSupervisor().prepare(*args)
        planner.prepare.side_effect = prepare
        self.jobs._supervisor = planner
        (self.root / 'app.py').write_text('pass')
        with patch('core.coding_projects.APPROVED_ROOTS', (self.root,)), patch('core.coding_jobs.subprocess.Popen') as launch:
            self.jobs.start(str(self.root), 'Inspect app.py')
            try:
                self.assertTrue(entered.wait(2))
                with patch('actions.coding_job.get_jobs', return_value=self.jobs):
                    status = coding_job({'action': 'status'})
                    stopped = coding_job({'action': 'stop'})
                self.assertFalse(status.data['process_running'])
                self.assertIsNone(status.data['pid'])
                self.assertEqual(stopped.status, 'partial')
                self.assertTrue(stopped.data['cancellation_requested'])
            finally:
                release.set()
                wait_for(self.jobs)
            launch.assert_not_called()
            self.assertIsNone(self.jobs.next_notice())

    def test_auto_model_uses_cli_defaults_and_failed_status_reports_error(self):
        (self.root / 'app.py').write_text('pass')
        self.jobs._supervisor = CompleteSupervisor()
        from core.opencode_cli import CliInfo
        with patch('core.coding_projects.APPROVED_ROOTS', (self.root,)), \
                patch('core.opencode_cli.resolve', return_value=CliInfo(Path('opencode.exe'), '2.0.32')), \
                patch('core.coding_jobs.subprocess.Popen', return_value=Process(record('error', error='Fixture provider failure'))) as launch:
            job = self.jobs.start(str(self.root), 'Inspect', agent='default', model='auto')
            wait_for(self.jobs)
        self.assertNotIn('--model', launch.call_args.args[0])
        self.assertNotIn('--agent', launch.call_args.args[0])
        self.assertEqual(job.phase, 'failed')
        with patch('actions.coding_job.get_jobs', return_value=self.jobs):
            result = coding_job({'action': 'status'})
        self.assertFalse(result.data['process_running'])
        self.assertIn('Error:', result.summary)
        job.session_id = 'ses_saved_fixture'
        job.model = 'auto'  # Older saved jobs may contain the old invalid value.
        with patch('core.coding_projects.APPROVED_ROOTS', (self.root,)), \
                patch('core.opencode_cli.resolve', return_value=CliInfo(Path('opencode.exe'), '2.0.32')), \
                patch('core.coding_jobs.subprocess.Popen', return_value=Process(record('text', text='Resumed.'))) as launch:
            self.jobs.resume('Retry with installed settings.')
            wait_for(self.jobs)
        self.assertNotIn('--model', launch.call_args.args[0])

    def test_completed_edits_are_announced_but_search_and_running_edits_are_silent(self):
        from core.opencode_cli import CliInfo
        entered, release = threading.Event(), threading.Event()
        supervisor = Mock()
        supervisor.prepare.side_effect = CompleteSupervisor().prepare
        def review(*args):
            entered.set()
            release.wait(timeout=5)
            return {'decision': 'complete'}
        supervisor.review.side_effect = review
        self.jobs._supervisor = supervisor
        (self.root / 'app.py').write_text('pass')
        stream = record('tool_use', tool='read', state={'status': 'completed', 'input': {'path': 'app.py'}})
        stream += record('tool_use', tool='edit', state={'status': 'running', 'input': {'path': 'app.py'}})
        stream += record('tool_use', tool='edit', state={'status': 'completed', 'input': {'path': 'app.py'}})
        stream += record('text', text='Changes ready.')
        with patch('core.coding_projects.APPROVED_ROOTS', (self.root,)), \
                patch('core.opencode_cli.resolve', return_value=CliInfo(Path('opencode.exe'), '2.0.32')), \
                patch('core.coding_jobs.subprocess.Popen', return_value=Process(stream)):
            self.jobs.start(str(self.root), 'Fix app.py')
            try:
                self.assertTrue(entered.wait(2))
                self.assertEqual(len(self.jobs._notices), 1)
                self.assertIn('completed changes in 1 file', self.jobs._notices[0]['summary'])
                self.assertIsNone(self.jobs.next_notice())
                self.now[0] += 150
                self.assertIn('completed changes', self.jobs.next_notice()['summary'])
            finally:
                release.set()
                wait_for(self.jobs)


if __name__ == '__main__':
    unittest.main()
