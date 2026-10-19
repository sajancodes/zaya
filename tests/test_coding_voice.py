"""Coding notices use isolated voice and preserve owner priority."""
import time
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

from core.tool_result import ToolResult
from tests.test_live_listening import agent


class CodingVoiceTests(unittest.IsolatedAsyncioTestCase):
    def live(self):
        live = agent()
        live._last_user_speech = time.monotonic() - 30
        live._owner_epoch = 0
        live.session = SimpleNamespace(send_client_content=AsyncMock())
        return live

    async def test_notice_reaches_audio_without_prompting_main_session(self):
        live = self.live()
        item = {'summary': "I've got the file."}
        with patch('core.notification_voice.synthesize_notice', new=AsyncMock(return_value=(b'voice', item['summary']))) as synth:
            self.assertTrue(await live._deliver_owner_notice(item, coding=True))
        synth.assert_awaited_once_with(item['summary'], coding=True)
        self.assertEqual(live.audio_in_queue.get_nowait(), b'voice')
        self.assertTrue(live._notification_active)
        live.session.send_client_content.assert_not_called()

    async def test_owner_interrupt_during_synthesis_retains_notice_for_retry(self):
        live = self.live()

        async def synth(*args, **kwargs):
            live._owner_epoch += 1
            return b'voice', 'notice'

        with patch('core.notification_voice.synthesize_notice', new=synth):
            self.assertFalse(await live._deliver_owner_notice({'summary': 'notice'}, coding=True))
        self.assertTrue(live.audio_in_queue.empty())
        live.ui.write_log.assert_not_called()

    async def test_legacy_live_coding_calls_route_to_opencode(self):
        live = self.live()
        live._action_registry = Mock()
        live._action_registry.scheduling.return_value = None
        live._plugin_registry = Mock()
        live._plugin_registry.scheduling.return_value = None
        for name in ('dev_agent', 'code_helper'):
            with self.subTest(name=name), patch('actions.coding_job.coding_job', return_value=ToolResult('success', 'started')) as coding:
                fc = SimpleNamespace(name=name, id='fixture', args={'project_name': 'demo', 'description': 'Fix it'})
                await live._execute_tool_impl(fc, owner_goal='Fix the bug in demo')
                expected = {'action': 'start', 'project': 'demo', 'task': 'Fix it'}
                if name == 'dev_agent':
                    expected['create_project'] = True
                coding.assert_called_once_with(expected, owner_request='Fix the bug in demo')
        live._action_registry.run.assert_not_called()
        live._plugin_registry.run.assert_not_called()

    async def test_actual_owner_request_is_preserved_when_live_model_paraphrases_task(self):
        live = self.live()
        live._action_registry = Mock()
        live._action_registry.scheduling.return_value = None
        live._plugin_registry = Mock()
        live._plugin_registry.scheduling.return_value = None
        fc = SimpleNamespace(name='coding_job', id='fixture', args={
            'action': 'start', 'project': 'calculator', 'task': 'Create a calculator script. Create a calculator script.',
            'create_project': True})
        with patch('actions.coding_job.coding_job', return_value=ToolResult('success', 'started')) as coding:
            await live._execute_tool_impl(fc, owner_goal='Make a simple calculator.')
        self.assertEqual(coding.call_args.kwargs['owner_request'], 'Make a simple calculator.')

    async def test_live_installation_request_keeps_setup_mode_and_home_directory(self):
        live = self.live()
        live._action_registry = Mock()
        live._action_registry.scheduling.return_value = None
        live._plugin_registry = Mock()
        live._plugin_registry.scheduling.return_value = None
        goal = 'Use OpenCode to install Android Studio and essential development components.'
        args = {'action': 'start', 'purpose': 'setup', 'project': '~', 'task': goal}
        fc = SimpleNamespace(name='coding_job', id='setup-fixture', args=args)
        with patch('actions.coding_job.coding_job', return_value=ToolResult('success', 'started')) as coding:
            await live._execute_tool_impl(fc, owner_goal=goal)
        coding.assert_called_once_with(args, owner_request=goal)


if __name__ == '__main__':
    unittest.main()
