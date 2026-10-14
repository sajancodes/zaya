import unittest
from unittest.mock import AsyncMock
from core.operator import Operator
from core.task_runtime import TaskRuntime
from core.tool_result import ToolResult
from core.execution_policy import trust_context, TRUST_WEB_CONTENT


class OperatorTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.runtime = TaskRuntime()
        self.operator = Operator(self.runtime)

    async def asyncTearDown(self):
        self.runtime.db.close()

    async def test_retry_is_bounded_and_only_for_safe_failed_steps(self):
        invoke = AsyncMock(return_value=ToolResult('failed', 'temporary', retryable=True))
        result = await self.operator.execute('fetch', invoke)
        self.assertEqual(result.status, 'failed')
        self.assertEqual(invoke.await_count, 3)
        side_effect = AsyncMock(return_value=ToolResult('failed', 'unknown send', retryable=True, side_effect=True))
        await self.operator.execute('send', side_effect)
        self.assertEqual(side_effect.await_count, 1)

    async def test_successful_call_id_not_repeated(self):
        invoke = AsyncMock(return_value=ToolResult('success', 'verified', evidence=[{'id': 'one'}], side_effect=True))
        await self.operator.execute('send', invoke, request_id='same')
        await self.operator.execute('send', invoke, request_id='same')
        self.assertEqual(invoke.await_count, 1)

    async def test_web_content_cannot_authorize_tools(self):
        invoke = AsyncMock()
        token = trust_context.set(TRUST_WEB_CONTENT)
        try:
            with self.assertRaises(PermissionError):
                await self.operator.execute('terminal', invoke)
            invoke.assert_not_awaited()
        finally:
            trust_context.reset(token)

    async def test_readonly_queries_are_refreshed(self):
        invoke = AsyncMock(return_value=ToolResult('success', 'current state'))
        await self.operator.execute('status', invoke, request_id='read')
        await self.operator.execute('status', invoke, request_id='read')
        self.assertEqual(invoke.await_count, 2)
