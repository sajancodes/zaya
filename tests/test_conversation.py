import asyncio
from contextlib import suppress
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

from core.execution_policy import trust_context, TRUST_EXTERNAL_MESSAGE
from memory.conversation_store import ConversationStore, HANDLE_SECONDS, resume_scope


class ConversationTests(unittest.TestCase):
    def test_pre_recovery_provider_checkpoint_is_ignored_without_losing_chat(self):
        import hashlib
        import json
        with tempfile.TemporaryDirectory() as folder:
            store = ConversationStore(Path(folder) / 'chat.db')
            chat_id = store.chat_id
            store.append('user', 'Keep this conversation.')
            old_scope = hashlib.sha256(json.dumps(['model', 'Nika', 'key']).encode()).hexdigest()
            store.save_handle('stuck-provider-handle', old_scope)
            self.assertIsNone(store.handle(resume_scope('model', 'Nika', 'key')))
            self.assertEqual(store.chat_id, chat_id)
            self.assertEqual(len(store.recent()), 1)

    def test_reopening_keeps_same_chat_and_full_archive(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'chat.db'
            first = ConversationStore(path)
            first.append('user', 'Remember the blue bicycle.')
            first.append('model', 'I will remember it.')
            first.update(operator_scope='original-request', operator_goal='remember bicycle')
            second = ConversationStore(path)
            self.assertEqual(first.chat_id, second.chat_id)
            self.assertEqual(second.recent()[0]['text'], 'Remember the blue bicycle.')
            self.assertEqual(second.state()['operator_scope'], 'original-request')

    def test_expired_or_changed_provider_token_does_not_erase_history(self):
        with tempfile.TemporaryDirectory() as folder:
            now = [10000.0]
            store = ConversationStore(Path(folder) / 'chat.db', lambda: now[0])
            scope = resume_scope('model', 'Nika', 'private-key')
            store.append('user', 'Keep our conversation.')
            store.save_handle('private-handle', scope)
            self.assertEqual(store.handle(scope), 'private-handle')
            self.assertIsNone(store.handle(resume_scope('model', 'other-voice', 'private-key')))
            self.assertIsNone(store.handle(resume_scope('model', 'Nika', 'different-key')))
            now[0] += HANDLE_SECONDS + 1
            self.assertIsNone(store.handle(scope))
            store.clear_handle()
            self.assertTrue(store.recent())
            self.assertNotIn('private-handle', str(store.restore_content()))

    def test_partial_speech_is_durable_without_duplicate_fragments(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'chat.db'
            store = ConversationStore(path)
            ident = store.record('user', 'Please remember')
            store.record('user', 'Please remember my blue bicycle', ident)
            reopened = ConversationStore(path)
            self.assertEqual(len(reopened.recent()), 1)
            self.assertEqual(reopened.recent()[0]['text'], 'Please remember my blue bicycle')

    def test_context_is_bounded_but_older_turns_remain_searchable(self):
        with tempfile.TemporaryDirectory() as folder:
            store = ConversationStore(Path(folder) / 'chat.db')
            store.append('user', 'Ancient bicycle discussion with 100% certainty')
            for i in range(60):
                store.append('model', f'Later turn {i}')
            self.assertEqual(len(store.recent()), 40)
            self.assertEqual(len(store.search('bicycle')), 1)
            self.assertEqual(len(store.search('%')), 1)  # Literal, not SQL wildcard.
            self.assertLessEqual(sum(len(row['text']) for row in store.recent(max_chars=20)), 20)
            self.assertIn('HISTORICAL CONTEXT ONLY', str(store.restore_content()))

    def test_external_contact_cannot_read_owner_chat(self):
        from actions.conversation_history import conversation_history
        token = trust_context.set(TRUST_EXTERNAL_MESSAGE)
        try:
            with self.assertRaises(PermissionError):
                conversation_history({'query': 'private'})
        finally:
            trust_context.reset(token)


class ConversationIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        from tests.test_live_listening import agent
        self.folder = tempfile.TemporaryDirectory()
        self.path = Path(self.folder.name) / 'chat.db'
        self.live = agent()
        self.live._conversation = ConversationStore(self.path)
        self.live._resume_scope = resume_scope('fixture', 'Nika', 'fixture-key')
        self.live._resume_handle = None
        self.live._asst_name = 'Zaya'
        self.live._session_log = []
        self.live._dashboard = None
        self.live._last_out_logged = ''
        self.live._vision_close_pending = False

    async def asyncTearDown(self):
        self.folder.cleanup()

    async def test_on_demand_history_recall_is_capped_at_five_and_does_not_replay_actions(self):
        from actions.conversation_history import conversation_history
        live = self.live
        for index in range(20):
            live._conversation.append('user', f'Old command {index}')
        with patch('actions.conversation_history.ConversationStore', return_value=live._conversation):
            result = conversation_history({})
            self.assertEqual(len(result.data['messages']), 5)
            self.assertEqual(result.data['messages'][0]['text'], 'Old command 15')
            self.assertEqual(len(conversation_history({'query': 'Old'}).data['messages']), 5)
        self.assertIn('historical context only', result.summary)
        self.assertEqual(len(live._conversation.recent()), 20)

    async def test_typed_turn_is_saved_before_delivery_and_survives_restart(self):
        live = self.live

        async def sent(**kwargs):
            self.assertEqual(ConversationStore(self.path).recent()[0]['text'], 'My bicycle is blue')

        live.session = SimpleNamespace(send_client_content=AsyncMock(side_effect=sent))
        await live._send_owner_text('My bicycle is blue')
        self.assertEqual(ConversationStore(self.path).chat_id, live._conversation.chat_id)

    async def test_voice_transcript_and_reply_are_saved_across_close(self):
        live = self.live
        events = [SimpleNamespace(input_transcription=SimpleNamespace(text='Remember blue bicycle'),
                                  output_transcription=None, interrupted=False, turn_complete=False),
                  SimpleNamespace(input_transcription=None, output_transcription=SimpleNamespace(text='I remember.'),
                                  interrupted=False, turn_complete=True)]

        async def responses():
            for content in events:
                yield SimpleNamespace(server_content=content, data=None, tool_call=None)
            await asyncio.Event().wait()

        live.session = SimpleNamespace(receive=responses)
        task = asyncio.create_task(live._receive_audio())
        try:
            for _ in range(50):
                if len(live._conversation.recent()) == 2:
                    break
                await asyncio.sleep(.01)
            self.assertEqual([row['role'] for row in ConversationStore(self.path).recent()], ['user', 'model'])
        finally:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    async def test_provider_checkpoint_is_saved_and_unsafe_checkpoint_is_cleared(self):
        live = self.live
        for resumable in (True, False):
            done = asyncio.Event()

            async def responses():
                yield SimpleNamespace(server_content=None, data=None, tool_call=None,
                                      session_resumption_update=SimpleNamespace(resumable=resumable, new_handle='fixture-handle'))
                done.set()
                await asyncio.Event().wait()

            live.session = SimpleNamespace(receive=responses)
            task = asyncio.create_task(live._receive_audio())
            try:
                await asyncio.wait_for(done.wait(), 2)
                saved = ConversationStore(self.path).handle(live._resume_scope)
                self.assertEqual(saved, 'fixture-handle' if resumable else None)
            finally:
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task

    async def test_closing_mid_reply_keeps_partial_chat(self):
        live = self.live
        delivered = asyncio.Event()

        async def responses():
            content = SimpleNamespace(input_transcription=SimpleNamespace(text='Remember this unfinished thought'),
                                      output_transcription=SimpleNamespace(text='I was explaining'),
                                      interrupted=False, turn_complete=False)
            yield SimpleNamespace(server_content=content, data=None, tool_call=None)
            delivered.set()
            await asyncio.Event().wait()

        live.session = SimpleNamespace(receive=responses)
        task = asyncio.create_task(live._receive_audio())
        await asyncio.wait_for(delivered.wait(), 2)
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
        self.assertEqual([row['role'] for row in ConversationStore(self.path).recent()], ['user', 'model'])

    async def test_new_process_does_not_load_a_saved_provider_checkpoint_or_history(self):
        from main import JarvisLive
        from google.genai import types
        live = self.live
        live._enhanced_live = True
        live._operator_notifications = AsyncMock()
        scope = resume_scope('offline-test', 'Nika', 'fixture-key')
        live._conversation.save_handle('saved-checkpoint', scope)
        live._resume_scope = None
        live._build_config = Mock(side_effect=lambda: types.LiveConnectConfig(
            session_resumption=types.SessionResumptionConfig(handle=live._resume_handle)))
        entered = asyncio.Event()
        client = Mock()

        async def enter(*_):
            entered.set()
            await asyncio.Event().wait()

        class Connection:
            __aenter__ = enter
            async def __aexit__(self, *_):
                pass

        client.aio.live.connect.return_value = Connection()
        with patch('main.confirm_gate.bind'), patch('main.set_trim_notifier'), \
                patch('main.audio_devices.configure'), patch('main.audio_devices.prefetch'), \
                patch('dashboard.server.DashboardServer', side_effect=RuntimeError('offline fixture')), \
                patch('main._gemini.live_model', return_value='offline-test'), patch('main.get_voice', return_value='Nika'), \
                patch('main._get_api_key', return_value='fixture-key'), patch('main.genai.Client', return_value=client):
            task = asyncio.create_task(JarvisLive.run(live))
            try:
                await asyncio.wait_for(entered.wait(), 2)
                self.assertEqual(client.aio.live.connect.call_args.kwargs['config'].session_resumption.handle,
                                 None)
            finally:
                live.shutdown()
                with suppress(asyncio.CancelledError):
                    await task
