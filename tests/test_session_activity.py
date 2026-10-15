import json
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

from core.execution_policy import TRUST_EXTERNAL_MESSAGE, trust_context
from core.session_activity import SessionActivity
from core.tool_result import ToolResult
from services.whatsapp.models import Message
from services.whatsapp.policy import generate_reply


class ActivityTests(unittest.TestCase):
    def test_current_media_and_project_expire_or_clear_without_private_context(self):
        now = [10.0]
        activity = SessionActivity(lambda: now[0])
        activity.set('project', 'Sajan is working on a project.', seconds=60)
        activity.media('Sanam — Apna Dil Toh Awara', True)
        self.assertEqual(len(activity.snapshot()), 2)
        now[0] += 61
        self.assertEqual(len(activity.snapshot()), 1)
        self.assertIn('Sanam', activity.snapshot()[0]['summary'])
        activity.media('', False)
        self.assertEqual(activity.snapshot(), [])

    def test_paths_credentials_and_links_are_not_shared(self):
        activity = SessionActivity()
        for text in ['password=private-value', r'Editing C:\Users\owner\secret.txt', 'Reading https://private.example/account', 'Email owner@example.com']:
            with self.subTest(text=text), self.assertRaises(ValueError):
                activity.set('other', text)
        activity.media('https://private.example/stream?token=private', True)
        self.assertNotIn('private', str(activity.snapshot()))

    def test_external_contact_cannot_change_activity_but_reply_can_read_allowed_summary(self):
        activity = SessionActivity()
        activity.media('Sanam songs', True)
        message = Message('fixture', '123@s.whatsapp.net', 'contact', 'What is he doing?', 1)
        with patch('core.session_activity.activity', activity), \
                patch('core.gemini.as_json', return_value={'reply': 'He is listening to Sanam.', 'needs_owner': False}) as model:
            token = trust_context.set(TRUST_EXTERNAL_MESSAGE)
            try:
                with self.assertRaises(PermissionError):
                    activity.set('other', 'He is elsewhere.')
                with self.assertRaises(PermissionError):
                    activity.clear()
                generate_reply(message, [])
            finally:
                trust_context.reset(token)
        payload = json.loads(model.call_args.args[0])
        self.assertIn('Sanam', str(payload['shared_current_activity']))
        self.assertEqual(model.call_args.kwargs['config'].tools, [])
        self.assertNotIn('history', payload)

    def test_owner_activity_tool_updates_and_clears_public_summary(self):
        from actions.session_activity import session_activity
        activity = SessionActivity()
        with patch('actions.session_activity.activity', activity):
            result = session_activity({'action': 'set', 'kind': 'project', 'summary': 'Sajan is working on Zaya.'})
            self.assertEqual(result.status, 'success')
            self.assertIn('Zaya', str(result.data))
            self.assertEqual(session_activity({'action': 'clear'}).data['activities'], [])


class ActivityToolIntegrationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        runtime = patch('core.task_runtime.get_runtime', return_value=Mock())
        runtime.start()
        self.addCleanup(runtime.stop)

    async def test_successful_project_work_updates_activity_but_failed_work_does_not(self):
        from tests.test_live_listening import agent
        live = agent()
        activity = SessionActivity()
        fc = SimpleNamespace(name='code_helper', id='fixture', args={})
        with patch('core.session_activity.activity', activity), \
                patch('core.operator.Operator.execute', new=AsyncMock(return_value=ToolResult('failed', 'failed'))):
            await live._execute_tool(fc)
            self.assertEqual(activity.snapshot(), [])
        with patch('core.session_activity.activity', activity), \
                patch('core.operator.Operator.execute', new=AsyncMock(return_value=ToolResult('success', 'done'))):
            await live._execute_tool(fc)
        self.assertEqual(activity.snapshot()[0]['kind'], 'project')
