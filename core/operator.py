"""Bounded operator execution; retry proven safe failures without side effects."""
from __future__ import annotations
import asyncio
import contextvars
import time
from core import audit
from core.event_bus import bus
from core.task_runtime import TaskRuntime
from core.tool_result import ToolResult, normalize
from core.tools.loop_guard import LoopGuard
from core.tools.repeat_guard import RepeatGuard
from core.execution_policy import require_owner, trust_context, TRUST_AUTHENTICATED_REMOTE_OWNER

current_task = contextvars.ContextVar('zaya_current_task', default=None)
current_request = contextvars.ContextVar('zaya_current_request', default='')

_repeat_guard = RepeatGuard()
_loop_guard = LoopGuard()


class Operator:
    def __init__(self, runtime: TaskRuntime):
        self.runtime = runtime

    async def execute(self, name: str, invoke, request_id: str = '', goal: str = '',
                      source: str = '', trust_level: str = '',
                      arguments: dict | None = None) -> ToolResult:
        require_owner()
        current_trust = trust_context.get()
        actual_trust = trust_level or current_trust
        actual_source = source or ('dashboard' if actual_trust == TRUST_AUTHENTICATED_REMOTE_OWNER else 'local_desktop')
        scope = request_id.split(':', 1)[0] if request_id else ''
        # Count even a cached/reused duplicate before returning it. Otherwise a
        # model can loop forever on a proven result without ever touching the
        # execution path that enforces the loop budget.
        loop = _loop_guard.check(scope, name, arguments)
        if not loop.allowed:
            return ToolResult('partial', loop.reason, {'loop_limited': True, 'tool': name},
                              retryable=False)
        cached = self.runtime.cached(request_id) if request_id else None
        if cached:
            return cached
        reused = _repeat_guard.reuse(request_id, name, arguments)
        if reused is not None:
            return reused
        if request_id and not self.runtime.claim_request(request_id):
            # Check again after the atomic claim: the first invocation may
            # have completed between our first cache read and this reservation.
            return self.runtime.cached(request_id) or ToolResult(
                'partial', 'This request is already running or its earlier outcome is uncertain. It was not repeated.',
                {'request_reserved': True}, retryable=False)
        task = self.runtime.create(goal or name, source=actual_source, trust_level=actual_trust)
        task_token, request_token = current_task.set(task.id), current_request.set(request_id)
        started = time.monotonic()
        uncertain = False
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
                    uncertain = True
                    result = ToolResult('failed', f'{name} failed: {audit.redact(str(error))}')
                if self.runtime.get(task.id).state not in {'completed', 'failed', 'cancelled'}:
                    self.runtime.transition(task.id, 'verifying', evidence=result.evidence)
                if result.status == 'failed' and result.retryable and not result.side_effect and attempt + 1 < task.max_attempts:
                    continue
                if self.runtime.get(task.id).state not in {'completed', 'failed', 'cancelled'}:
                    self.runtime.finish(task.id, result)
                if request_id and result.status == 'success':
                    # A proven success is safe to reuse for the identical
                    # request even when it has no persistent side effect.
                    self.runtime.remember(request_id, result)
                    _repeat_guard.remember(request_id, name, result, arguments)
                if result.status == 'waiting_confirmation':
                    result.data = {**result.data, 'runtime_task_id': task.id}
                elif request_id and not result.side_effect and not uncertain:
                    self.runtime.release_request(request_id)
                bus.publish('tool.failed' if result.status == 'failed' else 'tool.completed',
                            tool=name, task_id=task.id, status=result.status)
                audit.write({'task_id': task.id, 'tool': name, 'status': result.status,
                             'duration_ms': int((time.monotonic() - started) * 1000), 'evidence': result.evidence,
                             'source': actual_source, 'trust_level': actual_trust})
                return result
        finally:
            current_task.reset(task_token)
            current_request.reset(request_token)
