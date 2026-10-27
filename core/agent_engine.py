"""Zaya Master Agent Engine: Goal-Oriented Planning, Safe Tool Execution,
Dependency-Aware Multi-Step Orchestration, User Approval, and Self-Recovery.
"""
from __future__ import annotations

import concurrent.futures
import copy
import re
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Callable

from core import audit
from core.event_bus import bus
from core.execution_policy import (
    TRUST_LOCAL_OWNER,
    TRUST_TOOL_OUTPUT,
    classify,
    get_trust,
    require_owner,
    with_trust,
)
from core.task_runtime import Task, TaskRuntime, get_runtime
from core.tool_result import ToolResult, normalize


class StepStatus:
    PENDING = 'PENDING'
    RUNNING = 'RUNNING'
    WAITING_FOR_APPROVAL = 'WAITING_FOR_APPROVAL'
    SUCCEEDED = 'SUCCEEDED'
    FAILED = 'FAILED'
    CANCELLED = 'CANCELLED'
    SKIPPED = 'SKIPPED'


TERMINAL_STEP_STATUSES = {
    StepStatus.SUCCEEDED,
    StepStatus.FAILED,
    StepStatus.CANCELLED,
    StepStatus.SKIPPED,
}


class PlanValidationError(ValueError):
    """Raised when a task plan is structurally invalid or contains cycles."""


class PlanExecutionError(RuntimeError):
    """Raised when plan execution encounters an unrecoverable error."""


# Tools known to perform irreversible or externally visible actions
CONSEQUENTIAL_TOOLS = {
    'send_message',
    'compose_sms',
    'reply_notification',
    'initiate_call',
    'phone_call',
    'delete_file',
    'remove_file',
    'write_file',
    'purchase',
    'financial_transfer',
    'wipe_data',
    'restart_system',
}


@dataclass
class PlanStep:
    id: str
    description: str
    tool: str
    arguments: dict[str, Any] = field(default_factory=dict)
    depends_on: list[str] = field(default_factory=list)
    status: str = StepStatus.PENDING
    timeout: float = 15.0
    max_retries: int = 0
    requires_approval: bool = False
    consequential: bool = False
    approved: bool = False
    expected_output: str | None = None
    output: Any = None
    error: str | None = None
    attempts: int = 0
    retryable: bool = False
    uncertain: bool = False
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    completed_at: float | None = None

    def __post_init__(self) -> None:
        # Automatically mark known consequential operations
        if self.tool in CONSEQUENTIAL_TOOLS:
            self.consequential = True
            if not self.approved:
                self.requires_approval = True
        elif self.tool in {'terminal_exec', 'shell_exec'} and 'command' in self.arguments:
            cmd = str(self.arguments.get('command', ''))
            try:
                decision = classify(cmd)
                if decision.level in {'confirm', 'deny'}:
                    self.consequential = True
                    if not self.approved:
                        self.requires_approval = True
            except Exception:
                # If trust check fails or command is unclassified, require approval
                self.consequential = True
                if not self.approved:
                    self.requires_approval = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PlanStep:
        clean = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**clean)


@dataclass
class Plan:
    plan_id: str
    goal: str
    steps: list[PlanStep]
    status: str = 'PENDING'
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    overall_timeout: float = 60.0
    metadata: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            'plan_id': self.plan_id,
            'goal': self.goal,
            'status': self.status,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'overall_timeout': self.overall_timeout,
            'metadata': self.metadata,
            'error': self.error,
            'steps': [s.to_dict() for s in self.steps],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Plan:
        steps_data = data.get('steps', [])
        steps = [PlanStep.from_dict(s) if isinstance(s, dict) else s for s in steps_data]
        return cls(
            plan_id=data['plan_id'],
            goal=data['goal'],
            steps=steps,
            status=data.get('status', 'PENDING'),
            created_at=data.get('created_at', time.time()),
            updated_at=data.get('updated_at', time.time()),
            overall_timeout=data.get('overall_timeout', 60.0),
            metadata=data.get('metadata', {}),
            error=data.get('error'),
        )

    def explain(self) -> str:
        """Explains the plan steps in natural human language."""
        lines = [f"Plan for: \"{self.goal}\""]
        for i, s in enumerate(self.steps, 1):
            req_appr = " [Requires Approval]" if s.requires_approval or s.consequential else ""
            deps = f" (after {', '.join(s.depends_on)})" if s.depends_on else ""
            lines.append(f"  Step {i} ({s.id}): {s.description}{deps}{req_appr}")
        return "\n".join(lines)

    def progress_summary(self) -> str:
        """Returns clear, human status description of current plan execution."""
        total = len(self.steps)
        succeeded = [s for s in self.steps if s.status == StepStatus.SUCCEEDED]
        waiting = [s for s in self.steps if s.status == StepStatus.WAITING_FOR_APPROVAL]
        running = [s for s in self.steps if s.status == StepStatus.RUNNING]
        failed = [s for s in self.steps if s.status == StepStatus.FAILED]
        cancelled = [s for s in self.steps if s.status == StepStatus.CANCELLED]

        if waiting:
            return f"Waiting for your approval before executing: {waiting[0].description}"
        if running:
            idx = self.steps.index(running[0]) + 1
            return f"Step {idx} of {total}: {running[0].description}"
        if failed:
            return f"Execution stopped at step {failed[0].id}: {failed[0].error}"
        if cancelled:
            return f"Plan was cancelled. Completed {len(succeeded)} of {total} steps."
        if len(succeeded) == total:
            return f"All {total} steps completed successfully."
        return f"Plan progress: {len(succeeded)}/{total} steps finished."


def validate_plan(plan: Plan) -> list[str]:
    """Validates plan structure, dependencies, and checks for dependency cycles.
    Returns step IDs in topologically sorted execution order.
    """
    if not plan.plan_id or not isinstance(plan.plan_id, str):
        raise PlanValidationError("Plan ID must be a non-empty string.")
    if not plan.goal or not isinstance(plan.goal, str):
        raise PlanValidationError("Plan goal must be a non-empty string.")
    if not plan.steps:
        raise PlanValidationError("Plan must contain at least one step.")

    step_ids = set()
    graph: dict[str, list[str]] = {}

    for step in plan.steps:
        if not step.id or not isinstance(step.id, str):
            raise PlanValidationError("Each step must have a non-empty ID.")
        if step.id in step_ids:
            raise PlanValidationError(f"Duplicate step ID found: '{step.id}'")
        if not step.tool or not isinstance(step.tool, str):
            raise PlanValidationError(f"Step '{step.id}' must specify a valid tool name.")
        if not isinstance(step.arguments, dict):
            raise PlanValidationError(f"Step '{step.id}' arguments must be a dictionary.")

        step_ids.add(step.id)
        graph[step.id] = list(step.depends_on)

    # Validate that all dependencies exist and check for self-dependency
    for step_id, deps in graph.items():
        for dep in deps:
            if dep == step_id:
                raise PlanValidationError(f"Step '{step_id}' cannot depend on itself.")
            if dep not in step_ids:
                raise PlanValidationError(f"Step '{step_id}' depends on non-existent step '{dep}'.")

    # Cycle detection via topological sort (Kahn's algorithm)
    in_degree = {s_id: 0 for s_id in step_ids}
    adj: dict[str, list[str]] = {s_id: [] for s_id in step_ids}
    for s_id, deps in graph.items():
        for dep in deps:
            adj[dep].append(s_id)
            in_degree[s_id] += 1

    queue = [s_id for s_id, deg in in_degree.items() if deg == 0]
    sorted_order: list[str] = []

    while queue:
        node = queue.pop(0)
        sorted_order.append(node)
        for neighbor in adj[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if len(sorted_order) != len(step_ids):
        # Nodes remaining with in_degree > 0 indicate a cycle
        cycle_nodes = [s_id for s_id, deg in in_degree.items() if deg > 0]
        raise PlanValidationError(f"Dependency cycle detected involving steps: {cycle_nodes}")

    return sorted_order


def interpolate_arguments(arguments: dict[str, Any], completed_steps: dict[str, PlanStep]) -> dict[str, Any]:
    """Resolves dynamic argument templates like `{{steps.step_1.output.key}}`
    from earlier successfully completed steps.
    """
    resolved = copy.deepcopy(arguments)

    pattern = re.compile(r'\{\{steps\.([a-zA-Z0-9_-]+)\.(output|data)(?:\.([a-zA-Z0-9_.-]+))?\}\}')

    def _replace_val(val: Any) -> Any:
        if isinstance(val, str):
            match = pattern.fullmatch(val.strip())
            if match:
                step_id, field_type, key_path = match.groups()
                if step_id not in completed_steps:
                    raise PlanExecutionError(f"Argument template references uncompleted step '{step_id}'.")
                step = completed_steps[step_id]
                if step.status != StepStatus.SUCCEEDED:
                    raise PlanExecutionError(f"Step '{step_id}' referenced in argument template did not succeed.")

                source_obj = step.output
                if isinstance(source_obj, dict) and field_type == 'data':
                    source_obj = source_obj.get('data', source_obj)

                if key_path:
                    parts = key_path.split('.')
                    curr = source_obj
                    for part in parts:
                        if isinstance(curr, dict) and part in curr:
                            curr = curr[part]
                        else:
                            raise PlanExecutionError(f"Field '{key_path}' not found in step '{step_id}' output.")
                    return curr
                return source_obj

            # Partial string substitution
            def sub_match(m: re.Match) -> str:
                step_id, field_type, key_path = m.groups()
                if step_id not in completed_steps or completed_steps[step_id].status != StepStatus.SUCCEEDED:
                    return m.group(0)
                source_obj = completed_steps[step_id].output
                if isinstance(source_obj, dict) and field_type == 'data':
                    source_obj = source_obj.get('data', source_obj)
                if key_path and isinstance(source_obj, dict):
                    return str(source_obj.get(key_path, ''))
                return str(source_obj)

            return pattern.sub(sub_match, val)

        if isinstance(val, dict):
            return {k: _replace_val(v) for k, v in val.items()}
        if isinstance(val, list):
            return [_replace_val(item) for item in val]
        return val

    return _replace_val(resolved)


class SafeToolExecutionLayer:
    """Dispatches tool calls through strict validation, schema checking,
    permission gates, timeout limits, and audit redaction.
    """

    def __init__(self, registry: Any = None) -> None:
        self.registry = registry

    def _get_registry(self) -> Any:
        if self.registry is not None:
            return self.registry
        from core.action_loader import discover_actions
        return discover_actions()

    def validate_arguments(self, tool_name: str, arguments: dict[str, Any]) -> tuple[bool, str | None]:
        """Validates tool arguments against the tool's registered parameters schema."""
        reg = self._get_registry()
        rec = getattr(reg, '_actions', {}).get(tool_name)
        if not rec or not rec.parameters:
            return True, None

        params_schema = rec.parameters
        required = params_schema.get('required', [])
        properties = params_schema.get('properties', {})

        for req in required:
            if req not in arguments:
                return False, f"Missing required parameter: '{req}'."

        for k, v in arguments.items():
            if k in properties:
                expected_type = properties[k].get('type', '').upper()
                if expected_type in {'STRING', 'TEXT'} and not isinstance(v, str):
                    return False, f"Parameter '{k}' expected string, got {type(v).__name__}."
                if expected_type in {'INTEGER', 'INT'} and not isinstance(v, int):
                    return False, f"Parameter '{k}' expected integer, got {type(v).__name__}."
                if expected_type in {'BOOLEAN', 'BOOL'} and not isinstance(v, bool):
                    return False, f"Parameter '{k}' expected boolean, got {type(v).__name__}."
                if expected_type in {'OBJECT', 'DICT'} and not isinstance(v, dict):
                    return False, f"Parameter '{k}' expected dictionary, got {type(v).__name__}."
                if expected_type in {'ARRAY', 'LIST'} and not isinstance(v, list):
                    return False, f"Parameter '{k}' expected list, got {type(v).__name__}."

        return True, None

    def execute_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        timeout: float = 15.0,
        is_consequential: bool = False,
    ) -> ToolResult:
        """Executes a single registered tool safely with bounded timeout and security check."""
        reg = self._get_registry()

        # 1. Registration check
        if not reg.has(tool_name):
            return ToolResult(
                status='failed',
                summary=f"Tool '{tool_name}' is not registered.",
                retryable=False,
            )

        # 2. Argument schema check
        valid_args, arg_err = self.validate_arguments(tool_name, arguments)
        if not valid_args:
            return ToolResult(
                status='failed',
                summary=f"Invalid arguments for tool '{tool_name}': {arg_err}",
                retryable=False,
            )

        # 3. Security and Permission Check
        try:
            require_owner()
        except PermissionError as pe:
            return ToolResult(
                status='failed',
                summary=f"Permission denied: {pe}",
                retryable=False,
            )

        # 4. Enforce timeout using thread worker
        def _invoke() -> Any:
            return reg.run(tool_name, arguments)

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(_invoke)
            try:
                raw_result = future.result(timeout=timeout)
                normalized = normalize(raw_result)
                # Audit log the execution safely
                audit.write({
                    'action': 'agent.tool_exec',
                    'tool': tool_name,
                    'arguments': audit.redact(arguments),
                    'status': normalized.status,
                    'summary': normalized.summary,
                })
                return normalized
            except concurrent.futures.TimeoutError:
                # Consequential action timeouts are uncertain: we must NEVER retry them
                uncertain = is_consequential
                summary = (
                    f"Tool '{tool_name}' timed out after {timeout} seconds. "
                    + ("The outcome is uncertain, so it will not be retried." if uncertain else "")
                )
                return ToolResult(
                    status='failed',
                    summary=summary.strip(),
                    data={'timed_out': True, 'uncertain': uncertain},
                    retryable=not uncertain,
                )
            except Exception as e:
                return ToolResult(
                    status='failed',
                    summary=f"Tool execution failed with {type(e).__name__}: {e}",
                    retryable=False,
                )


class AgentEngine:
    """Master agent planning, execution, approval, and self-recovery coordinator."""

    def __init__(
        self,
        registry: Any = None,
        task_runtime: TaskRuntime | None = None,
        max_concurrency: int = 2,
        default_step_timeout: float = 15.0,
        default_plan_timeout: float = 60.0,
    ) -> None:
        self.tool_layer = SafeToolExecutionLayer(registry)
        self.task_runtime = task_runtime or get_runtime()
        self.max_concurrency = max_concurrency
        self.default_step_timeout = default_step_timeout
        self.default_plan_timeout = default_plan_timeout
        self._active_plans: dict[str, Plan] = {}
        self._cancellation_events: dict[str, threading.Event] = {}
        self._lock = threading.RLock()

    def create_plan(
        self,
        goal: str,
        steps: list[PlanStep | dict[str, Any]],
        plan_id: str | None = None,
        overall_timeout: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Plan:
        """Creates and validates a new goal-oriented execution plan."""
        pid = plan_id or f"plan_{uuid.uuid4().hex[:12]}"
        step_objs: list[PlanStep] = []
        for s in steps:
            if isinstance(s, PlanStep):
                step_objs.append(s)
            elif isinstance(s, dict):
                step_objs.append(PlanStep.from_dict(s))
            else:
                raise PlanValidationError(f"Invalid step format: {type(s).__name__}")

        plan = Plan(
            plan_id=pid,
            goal=goal,
            steps=step_objs,
            overall_timeout=overall_timeout or self.default_plan_timeout,
            metadata=metadata or {},
        )

        validate_plan(plan)

        with self._lock:
            self._active_plans[pid] = plan
            self._cancellation_events[pid] = threading.Event()

        # Record in durable TaskRuntime
        try:
            task = self.task_runtime.create(goal=goal)
            self.task_runtime.transition(task.id, 'planning', plan=plan.to_dict())
            plan.metadata['runtime_task_id'] = task.id
        except Exception:
            pass

        bus.publish('agent.plan_created', plan=plan.to_dict())
        return plan

    def get_plan(self, plan_id: str) -> Plan | None:
        with self._lock:
            if plan_id in self._active_plans:
                return self._active_plans[plan_id]
        # Attempt recovery from durable TaskRuntime
        for task in self.task_runtime.list(limit=100):
            if task.plan and task.plan.get('plan_id') == plan_id:
                recovered = Plan.from_dict(task.plan)
                with self._lock:
                    self._active_plans[plan_id] = recovered
                return recovered
        return None

    def cancel_plan(self, plan_id: str, reason: str = "Cancelled by user") -> Plan:
        """Cancels an active plan and all non-completed steps cleanly."""
        with self._lock:
            plan = self.get_plan(plan_id)
            if not plan:
                raise KeyError(f"Plan '{plan_id}' not found.")

            event = self._cancellation_events.get(plan_id)
            if event:
                event.set()

            for step in plan.steps:
                if step.status in {StepStatus.PENDING, StepStatus.RUNNING, StepStatus.WAITING_FOR_APPROVAL}:
                    step.status = StepStatus.CANCELLED
                    step.error = reason
                    step.completed_at = time.time()

            plan.status = 'CANCELLED'
            plan.error = reason
            plan.updated_at = time.time()

            self._persist_plan(plan)

        bus.publish('agent.plan_cancelled', plan_id=plan_id, reason=reason)
        return plan

    def approve_step(self, plan_id: str, step_id: str) -> Plan:
        """Owner approval gate: confirms a step held in WAITING_FOR_APPROVAL and executes it."""
        with self._lock:
            plan = self.get_plan(plan_id)
            if not plan:
                raise KeyError(f"Plan '{plan_id}' not found.")

            target_step = next((s for s in plan.steps if s.id == step_id), None)
            if not target_step:
                raise KeyError(f"Step '{step_id}' not found in plan '{plan_id}'.")

            if target_step.status != StepStatus.WAITING_FOR_APPROVAL:
                raise ValueError(f"Step '{step_id}' is not waiting for approval (current: {target_step.status}).")

            target_step.status = StepStatus.PENDING
            target_step.requires_approval = False
            target_step.approved = True

        bus.publish('agent.step_approved', plan_id=plan_id, step_id=step_id)
        # Continue execution
        return self.execute_plan(plan)

    def reject_step(self, plan_id: str, step_id: str, reason: str = "Rejected by user") -> Plan:
        """Owner decline gate: rejects a step without a system error, skipping dependents."""
        with self._lock:
            plan = self.get_plan(plan_id)
            if not plan:
                raise KeyError(f"Plan '{plan_id}' not found.")

            target_step = next((s for s in plan.steps if s.id == step_id), None)
            if not target_step:
                raise KeyError(f"Step '{step_id}' not found in plan '{plan_id}'.")

            target_step.status = StepStatus.CANCELLED
            target_step.error = reason
            target_step.completed_at = time.time()

            # Skip all dependent steps
            self._skip_dependents(plan, target_step.id, f"Prerequisite step '{target_step.id}' was rejected.")
            self._persist_plan(plan)

        bus.publish('agent.step_rejected', plan_id=plan_id, step_id=step_id, reason=reason)
        return plan

    def _skip_dependents(self, plan: Plan, failed_step_id: str, reason: str) -> None:
        """Recursively marks dependent steps as SKIPPED when an upstream step fails or is rejected."""
        to_skip = {failed_step_id}
        changed = True
        while changed:
            changed = False
            for step in plan.steps:
                if step.status == StepStatus.PENDING and step.id not in to_skip:
                    if any(dep in to_skip for dep in step.depends_on):
                        to_skip.add(step.id)
                        step.status = StepStatus.SKIPPED
                        step.error = reason
                        step.completed_at = time.time()
                        changed = True

    def _persist_plan(self, plan: Plan) -> None:
        """Syncs plan and step states to TaskRuntime SQLite database."""
        runtime_id = plan.metadata.get('runtime_task_id')
        if not runtime_id:
            return
        state_map = {
            'PENDING': 'planning',
            'RUNNING': 'executing',
            'WAITING_FOR_APPROVAL': 'waiting_confirmation',
            'SUCCEEDED': 'completed',
            'FAILED': 'failed',
            'CANCELLED': 'cancelled',
        }
        target_state = state_map.get(plan.status, 'executing')
        try:
            self.task_runtime.transition(runtime_id, target_state, plan=plan.to_dict(), error=plan.error)
        except Exception:
            pass

    def execute_plan(self, plan: Plan, auto_approve_low_risk: bool = True) -> Plan:
        """Executes plan steps respecting dependency ordering, approval gates,
        bounded retries, timeouts, and safe recovery.
        """
        validate_plan(plan)
        plan_id = plan.plan_id

        cancel_event = self._cancellation_events.get(plan_id)
        if not cancel_event:
            cancel_event = threading.Event()
            self._cancellation_events[plan_id] = cancel_event

        plan.status = 'RUNNING'
        plan.updated_at = time.time()
        start_time = time.time()

        while True:
            # Check overall plan timeout or cancellation
            if cancel_event.is_set():
                plan.status = 'CANCELLED'
                plan.error = "Plan execution cancelled."
                break

            if (time.time() - start_time) > plan.overall_timeout:
                plan.status = 'FAILED'
                plan.error = f"Overall plan timed out after {plan.overall_timeout} seconds."
                for s in plan.steps:
                    if s.status == StepStatus.PENDING:
                        s.status = StepStatus.CANCELLED
                        s.error = "Plan timed out before this step could start."
                break

            # Find ready steps (all dependencies in SUCCEEDED)
            completed_map = {s.id: s for s in plan.steps if s.status == StepStatus.SUCCEEDED}
            ready_steps = [
                s for s in plan.steps
                if s.status == StepStatus.PENDING
                and all(dep in completed_map for dep in s.depends_on)
            ]

            if not ready_steps:
                # Check if we are waiting for user approval on any step
                waiting_steps = [s for s in plan.steps if s.status == StepStatus.WAITING_FOR_APPROVAL]
                if waiting_steps:
                    plan.status = 'WAITING_FOR_APPROVAL'
                    self._persist_plan(plan)
                    return plan

                # Check if all steps are in a terminal state
                all_terminal = all(s.status in TERMINAL_STEP_STATUSES for s in plan.steps)
                if all_terminal:
                    any_failed = any(s.status == StepStatus.FAILED for s in plan.steps)
                    any_cancelled = any(s.status == StepStatus.CANCELLED for s in plan.steps)
                    if any_failed:
                        plan.status = 'FAILED'
                        plan.error = next(s.error for s in plan.steps if s.status == StepStatus.FAILED and s.error)
                    elif any_cancelled:
                        plan.status = 'CANCELLED'
                        plan.error = "Plan had cancelled steps."
                    else:
                        plan.status = 'SUCCEEDED'
                break

            # Process ready steps
            for step in ready_steps[:self.max_concurrency]:
                if cancel_event.is_set():
                    break

                # Approval Gate for consequential operations
                if (step.requires_approval or step.consequential) and not step.approved:
                    step.status = StepStatus.WAITING_FOR_APPROVAL
                    plan.status = 'WAITING_FOR_APPROVAL'
                    self._persist_plan(plan)
                    bus.publish('agent.approval_required', plan_id=plan_id, step=step.to_dict())
                    return plan

                # Execute step with retry loop
                self._execute_single_step(step, completed_map, cancel_event)

                if step.status == StepStatus.FAILED:
                    # Halt dependent steps
                    self._skip_dependents(plan, step.id, f"Prerequisite step '{step.id}' failed: {step.error}")

                self._persist_plan(plan)

        plan.updated_at = time.time()
        self._persist_plan(plan)
        bus.publish('agent.plan_finished', plan=plan.to_dict())
        return plan

    def _execute_single_step(
        self,
        step: PlanStep,
        completed_map: dict[str, PlanStep],
        cancel_event: threading.Event,
    ) -> None:
        """Executes a single step with argument interpolation, bounded retries, and backoff."""
        step.status = StepStatus.RUNNING
        step.started_at = time.time()

        # 1. Parameter interpolation
        try:
            resolved_args = interpolate_arguments(step.arguments, completed_map)
        except Exception as e:
            step.status = StepStatus.FAILED
            step.error = f"Failed to interpolate step arguments: {e}"
            step.completed_at = time.time()
            return

        # 2. Bounded Retry Loop
        attempt = 0
        max_attempts = max(1, step.max_retries + 1)

        while attempt < max_attempts:
            if cancel_event.is_set():
                step.status = StepStatus.CANCELLED
                step.error = "Cancelled during execution."
                step.completed_at = time.time()
                return

            attempt += 1
            step.attempts = attempt

            result = self.tool_layer.execute_tool(
                tool_name=step.tool,
                arguments=resolved_args,
                timeout=step.timeout,
                is_consequential=step.consequential,
            )

            if result.status == 'success':
                step.status = StepStatus.SUCCEEDED
                step.output = result.data or result.summary
                step.error = None
                step.completed_at = time.time()
                return

            # Check if failure is uncertain (e.g. consequential action timed out)
            if result.data.get('uncertain'):
                step.uncertain = True
                step.retryable = False

            step.retryable = result.retryable and not step.consequential and not step.uncertain
            step.error = result.summary

            if step.retryable and attempt < max_attempts:
                # Exponential backoff: 0.1s, 0.2s, 0.4s
                backoff_delay = 0.1 * (2 ** (attempt - 1))
                time.sleep(backoff_delay)
            else:
                break

        step.status = StepStatus.FAILED
        step.completed_at = time.time()

    def recover_interrupted_tasks(self) -> list[Plan]:
        """Recovers paused or in-flight tasks after process restart.
        Guarantees that uncertain or in-flight consequential operations are NEVER re-executed blindly.
        """
        recovered_plans: list[Plan] = []
        for task in self.task_runtime.list(limit=200):
            if task.plan and task.state in {'planning', 'executing', 'waiting_confirmation', 'paused'}:
                try:
                    plan = Plan.from_dict(task.plan)
                    # Mark any in-flight step as uncertain/paused
                    for s in plan.steps:
                        if s.status == StepStatus.RUNNING:
                            s.status = StepStatus.FAILED
                            s.uncertain = True
                            s.error = "Application restarted while step was in-flight; outcome uncertain. Not auto-replayed."
                    plan.status = 'PAUSED'
                    plan.error = "Interrupted by process restart. Inspect steps before resuming."
                    self._persist_plan(plan)
                    recovered_plans.append(plan)
                except Exception:
                    pass
        return recovered_plans
