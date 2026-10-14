"""Bounded operator execution; retry proven safe failures without side effects."""
from __future__ import annotations
import asyncio
import contextvars
import time
from core import audit
from core.event_bus import bus
from core.task_runtime import TaskRuntime
from core.tool_result import ToolResult, normalize
from core.execution_policy import require_owner

current_task = contextvars.ContextVar('zaya_current_task', default=None)
current_request = contextvars.ContextVar('zaya_current_request', default='')


class Operator:
    def __init__(self, runtime: TaskRuntime):
        self.runtime = runtime

    async def execute(self, name: str, invoke, request_id: str = '', goal: str = '') -> ToolResult:
        require_owner()
        cached = self.runtime.cached(request_id) if request_id else None
        if cached:
            return cached
        task = self.runtime.create(goal or name)
        task_token, request_token = current_task.set(task.id), current_request.set(request_id)
        started = time.monotonic()
        try:
            for attempt in range(task.max_attempts):
                self.runtime.attempt(task.id, name)
                bus.publish('tool.started', tool=name, task_id=task.id, attempt=attempt + 1)
                try:
                    result = normalize(await invoke())
                except asyncio.CancelledError:
                    self.runtime.transition(task.id, 'cancelled')
                    raise
                except Exception as error:
                    result = ToolResult('failed', f'{name} failed: {audit.redact(str(error))}')
                if self.runtime.get(task.id).state not in {'completed', 'failed', 'cancelled'}:
                    self.runtime.transition(task.id, 'verifying', evidence=result.evidence)
                if result.status == 'failed' and result.retryable and not result.side_effect and attempt + 1 < task.max_attempts:
                    continue
                if self.runtime.get(task.id).state not in {'completed', 'failed', 'cancelled'}:
                    self.runtime.finish(task.id, result)
                if request_id and result.status == 'success':
                    self.runtime.remember(request_id, result)
                bus.publish('tool.failed' if result.status == 'failed' else 'tool.completed',
                            tool=name, task_id=task.id, status=result.status)
                audit.write({'task_id': task.id, 'tool': name, 'status': result.status,
                             'duration_ms': int((time.monotonic() - started) * 1000), 'evidence': result.evidence})
                return result
        finally:
            current_task.reset(task_token)
            current_request.reset(request_token)
