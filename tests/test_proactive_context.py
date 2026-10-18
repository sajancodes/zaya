"""Contextual check-ins are varied, bounded, grounded and tool-free."""
import json
import random
import time
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from actions.proactive import ProactiveEngine


class ProactiveContextTests(unittest.TestCase):
    def engine(self):
        self.now = [0.0]
        return ProactiveEngine(clock=lambda: self.now[0], rng=random.Random(7))

    def test_random_quiet_period_cooldown_and_no_repeated_context(self):
        engine = self.engine()
        self.assertFalse(engine.should_trigger(0))
        self.assertTrue(144 <= engine._silence_target <= 252)
        self.now[0] = engine._silence_target + 1
        self.assertTrue(engine.should_trigger(0))
        self.assertTrue(engine.build_prompt(recent_turns=['User: I am fixing Zaya.']))
        engine.mark_triggered()
        self.assertFalse(engine.should_trigger(0))
        self.now[0] += engine._cooldown_target + 1
        self.assertTrue(engine.should_trigger(0))
        self.assertEqual(engine.build_prompt(recent_turns=['User: I am fixing Zaya.']), '')
        self.assertTrue(engine.build_prompt(recent_turns=['User: I finished the reminder fix.']))

    def test_cold_start_is_quiet_and_archive_memory_is_never_added(self):
        engine = self.engine()
        self.assertEqual(engine.build_prompt(memory={'old private history': 'not for unsolicited chat'}), '')
        turns = ['User: old item 1', 'User: old item 2', 'User: current 1', 'Zaya: current 2',
                 'User: current 3', 'Zaya: current 4', 'User: current 5']
        prompt = engine.build_prompt(memory={'private': 'archive secret'}, recent_turns=turns)
        context = json.loads(prompt.split('Quoted context:\n', 1)[1])
        self.assertEqual(len(context['recent_session']), 5)
        self.assertNotIn('old item', prompt)
        self.assertNotIn('archive secret', prompt)
        self.assertNotIn('old private history', prompt)

    def test_activity_age_changes_do_not_retrigger_same_callback(self):
        engine = self.engine()
        prompt = engine.build_prompt(current_activity=[{'summary': 'Sajan is listening to music.', 'age_seconds': 10}])
        self.assertTrue(prompt)
        engine.mark_triggered()
        self.assertEqual(engine.build_prompt(current_activity=[{'summary': 'Sajan is listening to music.', 'age_seconds': 60}]), '')


class ProactiveVoiceIntegrationTests(unittest.IsolatedAsyncioTestCase):
    def live(self):
        from tests.test_live_listening import agent
        live = agent()
        live.session = SimpleNamespace(send_client_content=AsyncMock())
        live._last_user_speech = time.monotonic() - 1000
        live._owner_epoch = 0
        live._session_log = ['User: I have been fixing Zaya reminders.']
        live._proactive = ProactiveEngine(min_silence_secs=0, check_cooldown=0, rng=random.Random(2))
        return live

    async def test_callback_uses_isolated_voice_and_does_not_load_history_or_prompt_main(self):
        live = self.live()
        reminders = SimpleNamespace(next_due=Mock(return_value=None))
        with patch('core.reminders.get_reminders', return_value=reminders), patch('main.list_monitors', return_value=[]), \
                patch('core.session_activity.activity.snapshot', return_value=[]), \
                patch('core.notification_voice.synthesize_notice', new=AsyncMock(return_value=(b'checkin', 'How is the fix coming along, sir?'))) as synth, \
                patch('memory.conversation_store.ConversationStore') as archive:
            self.assertTrue(await live._proactive_checkin())
        self.assertEqual(synth.call_args.kwargs, {'mode': 'checkin'})
        self.assertIn('Zaya reminders', synth.call_args.args[0])
        self.assertEqual(live.audio_in_queue.get_nowait(), b'checkin')
        live.session.send_client_content.assert_not_called()
        archive.assert_not_called()

    async def test_owner_request_mute_sleep_and_due_reminder_block_checkins(self):
        for block in ('owner', 'mute', 'sleep', 'reminder'):
            live = self.live()
            if block == 'owner':
                live._owner_request_pending = True
            elif block == 'mute':
                live.ui.muted = True
            elif block == 'sleep':
                live._wake_enabled, live._awake = True, False
            reminders = SimpleNamespace(next_due=Mock(return_value={'id': 'due'} if block == 'reminder' else None))
            with self.subTest(block=block), patch('core.reminders.get_reminders', return_value=reminders), patch('core.notification_voice.synthesize_notice', new=AsyncMock()) as synth:
                self.assertFalse(await live._proactive_checkin())
                synth.assert_not_called()

    async def test_typed_owner_context_is_available_without_reloading_archive(self):
        live = self.live()
        live._session_log = []
        await live._send_owner_text('I fixed the reminder bug.')
        self.assertEqual(live._session_log, ['User: I fixed the reminder bug.'])

    async def test_context_and_reminder_voice_sessions_have_no_operator_tools(self):
        from core.notification_voice import _synthesize_once
        for mode in ('checkin', 'reminder'):
            async def responses():
                yield SimpleNamespace(data=b'voice', server_content=SimpleNamespace(
                    output_transcription=SimpleNamespace(text='A short notice, sir.'), turn_complete=True))
            session = SimpleNamespace(send_client_content=AsyncMock(), receive=responses)
            context = MagicMock()
            context.__aenter__ = AsyncMock(return_value=session)
            context.__aexit__ = AsyncMock(return_value=False)
            client = MagicMock()
            client.aio.live.connect.return_value = context
            client.aio.aclose = AsyncMock()
            with self.subTest(mode=mode), patch('core.notification_voice.genai.Client', return_value=client):
                self.assertEqual(await _synthesize_once('Quoted notice.', verbatim=False, key='test-key', mode=mode),
                                 (b'voice', 'A short notice, sir.'))
            config = client.aio.live.connect.call_args.kwargs['config']
            self.assertEqual(config.tools, [])
            self.assertIn('Zaya', str(config.system_instruction))
            self.assertIn('Sajan Rai', str(config.system_instruction))
            client.aio.aclose.assert_awaited_once()


if __name__ == '__main__':
    unittest.main()
