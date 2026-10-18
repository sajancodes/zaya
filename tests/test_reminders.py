"""Persistent reminders, notification failures, and real due-to-voice delivery."""
import asyncio
from contextlib import suppress
from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

from actions import reminder as action
from core.execution_policy import TRUST_EXTERNAL_MESSAGE, with_trust
from core.reminders import ReminderStore, notify_desktop, notify_scheduled


class ReminderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='zaya-reminder-test-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.now = [time.time()]
        self.store = ReminderStore(self.root / 'reminders.db', clock=lambda: self.now[0])
        self.addCleanup(self.store.close)
        for target, value in [('actions.reminder.get_reminders', self.store), ('actions.reminder._scripts_dir', self.root)]:
            stub = patch(target, return_value=value)
            stub.start()
            self.addCleanup(stub.stop)

    def test_relative_delay_uses_clock_at_call_and_persists_before_registration(self):
        def register(target, name, path, message):
            self.assertEqual(len(self.store.list()), 1)
            self.assertTrue(path.exists())
            return name
        with patch('actions.reminder.time.time', return_value=self.now[0]), patch('actions.reminder._get_os', return_value='windows'), patch('actions.reminder._schedule_windows', side_effect=register):
            result = action.reminder({'delay_seconds': 60, 'message': 'Take a break'})
        self.assertEqual(result.status, 'success')
        item = result.data['reminder']
        self.assertEqual(item['due_at'], self.now[0] + 60)
        self.assertIsNone(self.store.next_due())
        self.now[0] += 60
        due = self.store.next_due()
        self.assertIn('Take a break', due['summary'])
        reopened = ReminderStore(self.store.path, clock=lambda: self.now[0])
        try:
            self.assertEqual(reopened.next_due()['id'], item['id'])
        finally:
            reopened.close()

    def test_two_reminders_at_same_time_do_not_overwrite_each_other(self):
        with patch('actions.reminder._get_os', return_value='windows'), patch('actions.reminder._schedule_windows', side_effect=lambda t, n, *a: n) as register:
            one = action.reminder({'delay_seconds': 60, 'message': 'First'})
            two = action.reminder({'delay_seconds': 60, 'message': 'Second'})
        self.assertNotEqual(one.data['reminder']['scheduler_id'], two.data['reminder']['scheduler_id'])
        self.assertEqual(register.call_count, 2)
        self.assertEqual(len(list(self.root.glob('*.py'))), 2)

    def test_failed_registration_is_partial_but_keeps_spoken_reminder(self):
        with patch('actions.reminder._get_os', return_value='windows'), patch('actions.reminder._schedule_windows', return_value=''):
            result = action.reminder({'delay_seconds': 1, 'message': 'Keep this'})
        self.assertEqual(result.status, 'partial')
        self.assertTrue(result.side_effect)
        self.assertTrue(result.data['reminder']['error'])
        self.now[0] += 2
        self.assertIsNotNone(self.store.next_due())

    def test_voice_failure_retries_and_submission_is_not_claimed_as_heard(self):
        first = self.store.create('One', self.now[0])
        second = self.store.create('Two', self.now[0] + 1)
        self.store.voice_failed(first, RuntimeError('offline'))
        self.assertIsNone(self.store.next_due())
        self.now[0] += 2
        self.assertEqual(self.store.next_due()['id'], second['id'])
        self.store.voice_queued(second)
        self.now[0] += 30
        self.assertEqual(self.store.next_due()['id'], first['id'])
        self.assertEqual(self.store.get(second['id'])['state'], 'voice_queued')
        self.assertNotIn('heard', self.store.get(second['id']))

    def test_cancel_and_owner_only_status(self):
        item = self.store.create('Do not announce', self.now[0])
        result = action.reminder({'action': 'cancel', 'id': item['id']})
        self.assertEqual(result.data['reminder']['state'], 'cancelled')
        self.assertIsNone(self.store.next_due())
        with with_trust(TRUST_EXTERNAL_MESSAGE), patch('actions.reminder.get_reminders') as get_store:
            for operation in ('create', 'status', 'list', 'cancel'):
                with self.assertRaises(PermissionError):
                    action.reminder({'action': operation})
            get_store.assert_not_called()

    def test_invalid_and_past_dates_do_not_save_any_reminders(self):
        for args in ({'delay_seconds': -1}, {'delay_seconds': float('nan')},
                     {'date': '2000-01-01', 'time': '12:00'}, {'date': 'bad', 'time': 'bad'}):
            with self.subTest(args=args):
                result = action.reminder({**args, 'message': 'bad request'})
                self.assertEqual(result.status, 'failed')
        self.assertEqual(self.store.list(), [])

    def test_desktop_failures_are_persisted_and_not_reported_as_delivery(self):
        item = self.store.create('Test', time.time() - 1)
        with patch('core.reminders.notify_desktop', side_effect=RuntimeError('notifier unavailable')):
            self.assertFalse(notify_scheduled(item['id'], self.store.path, 'windows'))
        self.assertIsNone(self.store.get(item['id'])['desktop_notified_at'])
        self.assertIn('notifier unavailable', self.store.get(item['id'])['error'])
        with patch('core.reminders.notify_desktop'):
            self.assertTrue(notify_scheduled(item['id'], self.store.path, 'windows'))
        self.assertIsNotNone(self.store.get(item['id'])['desktop_notified_at'])
        self.assertIsNotNone(self.store.next_due())  # Desktop submission does not consume voice.

    def test_generated_callback_keeps_failed_script_and_exits_nonzero(self):
        item = self.store.create('Test', time.time() - 1)
        script = action._write_notify_script('failure', item['id'], self.store.path)
        code = '''import runpy
from unittest.mock import patch
with patch('core.reminders.notify_desktop', side_effect=RuntimeError('notifier failed')):
    runpy.run_path(SCRIPT, run_name='__main__')
'''.replace('SCRIPT', repr(str(script)))
        result = subprocess.run([sys.executable, '-c', code], capture_output=True, timeout=15,
                                **({'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}))
        self.assertEqual(result.returncode, 1)
        self.assertTrue(script.exists())
        self.assertIn('notifier failed', self.store.get(item['id'])['error'])

    @unittest.skipUnless(os.name == 'nt', 'Windows desktop notification')
    def test_windows_message_is_stdin_data_and_backend_error_raises(self):
        message = '"; Stop-Computer; $(bad) & <private>'
        with patch('core.reminders.shutil.which', return_value='powershell.exe'), patch('core.reminders.subprocess.run', return_value=SimpleNamespace(returncode=0)) as run:
            notify_desktop(message, 'windows')
        self.assertNotIn(message, str(run.call_args.args[0]))
        self.assertEqual(json.loads(run.call_args.kwargs['input'])['message'], message)
        with patch('core.reminders.shutil.which', return_value='powershell.exe'), patch('core.reminders.subprocess.run', return_value=SimpleNamespace(returncode=1, stderr='failed', stdout='')):
            with self.assertRaises(RuntimeError):
                notify_desktop('test', 'windows')


class ReminderVoiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        from tests.test_live_listening import agent
        self.live = agent()
        self.live.session = SimpleNamespace(send_client_content=AsyncMock())
        self.live._last_user_speech = time.monotonic() - 30
        self.live._owner_epoch = 0
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.now = time.time()
        self.store = ReminderStore(Path(self.tmp.name) / 'reminders.db')
        self.addCleanup(self.store.close)
        self.item = self.store.create('Time for water', self.now - 1)
        stub = patch('core.reminders.get_reminders', return_value=self.store)
        stub.start()
        self.addCleanup(stub.stop)

    async def run_tick(self, synth):
        from services.whatsapp.store import WhatsAppStore
        wa = WhatsAppStore()
        self.addCleanup(wa.db.close)
        service = SimpleNamespace(start=Mock(), close=Mock(), store=wa)
        ticks = 0

        async def tick(seconds):
            nonlocal ticks
            ticks += 1
            if ticks > 1:
                raise asyncio.CancelledError
        with patch('services.whatsapp.service.get_service', return_value=service), patch('core.notification_voice.synthesize_notice', new=synth), patch('main.asyncio.sleep', new=tick):
            with suppress(asyncio.CancelledError):
                await self.live._operator_notifications()

    async def test_due_reminder_reaches_audio_even_when_wake_word_is_asleep(self):
        self.live._wake_enabled, self.live._awake = True, False
        synth = AsyncMock(return_value=(b'audio', 'Sir, your reminder: Time for water'))
        await self.run_tick(synth)
        self.assertEqual(self.live.audio_in_queue.get_nowait(), b'audio')
        self.assertIsNotNone(self.store.get(self.item['id'])['voice_queued_at'])
        self.assertIsNone(self.store.next_due())
        self.assertEqual(synth.call_args.kwargs, {'mode': 'reminder'})
        self.live.session.send_client_content.assert_not_called()
        self.assertFalse(self.live._awake)  # Reminder speech does not open the microphone.

    async def test_failed_speech_is_not_consumed_and_has_retry_evidence(self):
        await self.run_tick(AsyncMock(side_effect=RuntimeError('voice offline')))
        item = self.store.get(self.item['id'])
        self.assertIsNone(item['voice_queued_at'])
        self.assertIn('Voice delivery failed', item['error'])
        self.assertGreater(item['voice_retry_at'], self.now)
        self.assertTrue(self.live.audio_in_queue.empty())

    async def test_owner_speech_during_synthesis_keeps_reminder_pending(self):
        async def synth(*args, **kwargs):
            self.live._owner_epoch += 1
            return b'audio', 'reminder'
        await self.run_tick(synth)
        self.assertIsNone(self.store.get(self.item['id'])['voice_queued_at'])
        self.assertIsNotNone(self.store.next_due())
        self.assertTrue(self.live.audio_in_queue.empty())

    async def test_cancel_during_synthesis_prevents_announcement(self):
        async def synth(*args, **kwargs):
            self.store.cancel(self.item['id'])
            return b'audio', 'reminder'
        await self.run_tick(synth)
        self.assertIsNone(self.store.get(self.item['id'])['voice_queued_at'])
        self.assertTrue(self.live.audio_in_queue.empty())


@unittest.skipUnless(os.name == 'nt' and os.environ.get('ZAYA_REMINDER_SCHEDULER_SMOKE') == '1', 'opt-in real Windows scheduler check')
class RealReminderSchedulerTests(unittest.TestCase):
    def test_windows_scheduler_runs_callback_and_records_submission(self):
        import uuid
        with tempfile.TemporaryDirectory(prefix='zaya-scheduler-smoke-') as folder:
            root = Path(folder)
            store = ReminderStore(root / 'reminders.db')
            name = 'ZayaReminder_Test_' + uuid.uuid4().hex[:12]
            try:
                due = time.time() + 5
                item = store.create('Scheduler test only', due)
                with patch('actions.reminder._scripts_dir', return_value=root):
                    script = action._write_notify_script(name, item['id'], store.path)
                # Test actual OS scheduling and callback persistence without a
                # physical popup or sound during the automated regression run.
                source = script.read_text().replace('from core.reminders import notify_scheduled',
                    'import core.reminders as reminder_backend\nreminder_backend.notify_desktop = lambda *args: None\nfrom core.reminders import notify_scheduled')
                script.write_text(source, encoding='utf-8')
                self.assertEqual(action._schedule_windows(datetime.fromtimestamp(due), name, script, 'test'), name)
                deadline = time.monotonic() + 40
                while time.monotonic() < deadline and store.get(item['id'])['desktop_notified_at'] is None:
                    time.sleep(.25)
                self.assertIsNotNone(store.get(item['id'])['desktop_notified_at'], store.get(item['id'])['error'])
                self.assertFalse(script.exists())
            finally:
                subprocess.run(['schtasks', '/Delete', '/TN', name, '/F'], capture_output=True, timeout=20,
                               creationflags=subprocess.CREATE_NO_WINDOW)
                store.close()


if __name__ == '__main__':
    unittest.main()
