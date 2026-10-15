import asyncio
import unittest
from unittest.mock import patch
from core import confirm
from core.operator import Operator
from core.task_runtime import TaskRuntime
from core.tool_result import ToolResult
from actions.terminal_exec import terminal_exec


class ConfirmationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        mode = patch('memory.config_manager.get_auto_execute_enabled', return_value=False)
        mode.start()
        self.addCleanup(mode.stop)

    async def test_model_cannot_confirm_and_real_cancel_updates_runtime(self):
        runtime = TaskRuntime()
        confirm.bind(lambda *_: None, lambda: None)
        try:
            with patch('core.task_runtime.get_runtime', return_value=runtime), patch('actions.terminal_exec.sessions.run') as run:
                result = await Operator(runtime).execute('terminal_exec', lambda: asyncio.to_thread(terminal_exec, {'command': 'git reset --hard', 'confirmed': True}))
                self.assertEqual(result.status, 'waiting_confirmation')
                run.assert_not_called()
                confirm.resolve(False)
                self.assertEqual(runtime.list()[0].state, 'cancelled')
        finally:
            confirm.bind(None, None)
            runtime.db.close()

    async def test_real_approval_records_verified_result_and_call_cache(self):
        runtime = TaskRuntime()
        confirm.bind(lambda *_: None, lambda: None)
        try:
            with patch('core.task_runtime.get_runtime', return_value=runtime), patch('actions.terminal_exec.sessions.run', return_value=ToolResult('success', 'approved', evidence=[{'exit_code': 0}], side_effect=True)) as run:
                result = await Operator(runtime).execute('terminal_exec', lambda: asyncio.to_thread(terminal_exec, {'command': 'git reset --hard'}), request_id='approval-test')
                self.assertEqual(result.status, 'waiting_confirmation')
                confirm.resolve(True)
                for _ in range(100):
                    if runtime.cached('approval-test'):
                        break
                    await asyncio.sleep(.01)
                self.assertEqual(runtime.list()[0].state, 'completed')
                run.assert_called_once()
                self.assertEqual(runtime.cached('approval-test').status, 'success')
        finally:
            confirm.bind(None, None)
            runtime.db.close()
