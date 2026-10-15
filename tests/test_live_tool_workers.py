"""Incoming owner speech must not wait for slow or canceled tool work."""
import asyncio
from contextlib import suppress
from types import SimpleNamespace as NS
import unittest
from unittest.mock import AsyncMock

from google.genai import types
from tests.test_live_listening import agent


class ToolWorkerTests(unittest.IsolatedAsyncioTestCase):
    async def test_receive_continues_and_canceled_duplicate_call_is_not_resent(self):
        live = agent()
        live._conversation = None
        live._operator_scope, live._operator_goal = 'original', 'Original song on Brave'
        started, release, observed = asyncio.Event(), asyncio.Event(), asyncio.Event()
        fc = types.FunctionCall(id='one', name='video_player', args={'action': 'play'})

        async def execute(call, **kwargs):
            self.assertEqual(kwargs, {'owner_scope': 'original', 'owner_goal': 'Original song on Brave'})
            started.set()
            await release.wait()
            return types.FunctionResponse(id=call.id, name=call.name, response={'result': 'done'})

        live._execute_tool = AsyncMock(side_effect=execute)
        live._flush_pending_vision = AsyncMock()

        async def receive():
            yield NS(server_content=None, data=None, tool_call=NS(function_calls=[fc]))
            await started.wait()
            live._operator_scope, live._operator_goal = 'new', 'New owner command'
            yield NS(server_content=None, data=b'new owner response', tool_call=None,
                     tool_call_cancellation=NS(ids=['one']))
            yield NS(server_content=None, data=None, tool_call=NS(function_calls=[fc]))
            observed.set()
            await asyncio.Event().wait()

        live.session = NS(receive=receive, send_tool_response=AsyncMock())
        receiver = asyncio.create_task(live._receive_audio())
        try:
            await asyncio.wait_for(observed.wait(), 2)
            self.assertEqual(live.audio_in_queue.get_nowait(), b'new owner response')
            self.assertFalse(release.is_set())
            release.set()
            await asyncio.sleep(.02)
            live._execute_tool.assert_awaited_once()
            live.session.send_tool_response.assert_not_awaited()
        finally:
            receiver.cancel()
            with suppress(asyncio.CancelledError):
                await receiver

    async def test_successful_batch_returns_results_and_closing_cancels_workers(self):
        live = agent()
        started = asyncio.Event()
        canceled = asyncio.Event()

        async def execute(call, **_kwargs):
            if call.id == 'slow':
                started.set()
                try:
                    await asyncio.Event().wait()
                finally:
                    canceled.set()
            return types.FunctionResponse(id=call.id, name=call.name, response={'result': 'done'})

        live._execute_tool = execute
        live._flush_pending_vision = AsyncMock()
        live.session = NS(send_tool_response=AsyncMock())
        call = types.FunctionCall(id='fast', name='avatar_expression', args={})
        await live._run_tool_batch([call], set(), 'scope', 'goal')
        self.assertEqual(live.session.send_tool_response.call_args.kwargs['function_responses'][0].id, 'fast')

        async def receive():
            yield NS(server_content=None, data=None, tool_call=NS(function_calls=[
                types.FunctionCall(id='slow', name='video_player', args={})]))
            await asyncio.Event().wait()

        live.session.receive = receive
        receiver = asyncio.create_task(live._receive_audio())
        await asyncio.wait_for(started.wait(), 2)
        receiver.cancel()
        with suppress(asyncio.CancelledError):
            await receiver
        self.assertTrue(canceled.is_set())
