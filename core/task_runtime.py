"""Durable task state and bounded, evidence-based execution bookkeeping."""
from __future__ import annotations
import json
import sqlite3
import threading
import time
import uuid
from dataclasses import MISSING, asdict, dataclass, field, fields
from pathlib import Path
from core.runtime_paths import mutable_path
from core import audit
from core.event_bus import bus
from core.tool_result import ToolResult

STATES = {'created', 'inspecting', 'planning', 'executing', 'verifying',
          'waiting_confirmation', 'waiting_external', 'completed', 'failed', 'cancelled', 'paused'}
TERMINAL = {'completed', 'failed', 'cancelled'}


@dataclass
class Task:
    id: str
    goal: str
    source: str = 'local_ui'
    trust_level: str = 'local_owner'
    state: str = 'created'
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    active_step: str | None = None
    attempts: int = 0
    max_attempts: int = 3
    evidence: list[dict] = field(default_factory=list)
    side_effects: list[dict] = field(default_factory=list)
    error: str | None = None
    parent_id: str | None = None
    plan: dict | None = None


class TaskRuntime:
    def __init__(self, path: Path | str = ':memory:') -> None:
        if str(path) != ':memory:':
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self.db = sqlite3.connect(str(path), check_same_thread=False)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA busy_timeout=5000')
        self.db.execute('PRAGMA synchronous=NORMAL')
        self.db.execute('PRAGMA wal_autocheckpoint=1000')
        self.db.execute('CREATE TABLE IF NOT EXISTS runtime_tasks (id TEXT PRIMARY KEY, payload TEXT NOT NULL)')
        self.db.execute('CREATE TABLE IF NOT EXISTS tool_results (request_id TEXT PRIMARY KEY, payload TEXT NOT NULL)')
        self.db.execute('CREATE TABLE IF NOT EXISTS tool_request_claims (request_id TEXT PRIMARY KEY, created_at REAL NOT NULL)')
        # A process restart cannot prove an in-flight side effect failed. Do not replay it.
        rows = self.db.execute('SELECT id,payload FROM runtime_tasks').fetchall()
        for task in (self._load_task(*row) for row in rows):
            if task.state not in TERMINAL:
                self.transition(task.id, 'paused', error='Application restarted; inspect evidence before resuming.')

    def create(self, goal: str, **kwargs) -> Task:
        task = Task(id=uuid.uuid4().hex, goal=goal, **kwargs)
        self._save(task, 'task.created')
        return task

    def _save(self, task: Task, event: str | None = 'task.updated') -> Task:
        task.updated_at = time.time()
        payload = audit.redact(asdict(task))
        with self._lock, self.db:
            self.db.execute('INSERT OR REPLACE INTO runtime_tasks VALUES (?,?)', (task.id, json.dumps(payload)))
        if event is not None:
            bus.publish(event, task=payload)
        return task

    def get(self, task_id: str) -> Task:
        with self._lock:
            row = self.db.execute('SELECT id, payload FROM runtime_tasks WHERE id=?', (task_id,)).fetchone()
        if not row:
            raise KeyError(task_id)
        return self._load_task(*row)

    @staticmethod
    def _load_task(task_id: str, raw: str) -> Task:
        """Old rows remain readable without trusting renamed or future fields."""
        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            data = {}
        if not isinstance(data, dict):
            data = {}
        values = {}
        for item in fields(Task):
            if item.name in data:
                values[item.name] = data[item.name]
            elif item.default is not MISSING:
                values[item.name] = item.default
            elif item.default_factory is not MISSING:
                values[item.name] = item.default_factory()
        values['id'] = task_id  # The database key, never an embedded stale ID.
        values.setdefault('goal', 'Recovered task')
        for name in ('evidence', 'side_effects'):
            if not isinstance(values[name], list):
                values[name] = []
        if not isinstance(values['state'], str) or values['state'] not in STATES:
            values['state'] = 'paused'
        return Task(**values)

    def list(self, limit: int = 200) -> list[Task]:
        with self._lock:
            rows = self.db.execute('SELECT id, payload FROM runtime_tasks ORDER BY rowid DESC LIMIT ?', (min(limit, 1000),)).fetchall()
        return [self._load_task(*row) for row in rows]

    def transition(self, task_id: str, state: str, **updates) -> Task:
        with self._lock:
            task = self.get(task_id)
            if state not in STATES or (task.state in TERMINAL and state != task.state):
                raise ValueError(f'Invalid task transition: {task.state} -> {state}')
            for key, value in updates.items():
                if key not in {'active_step', 'error', 'evidence', 'side_effects', 'plan'}:
                    raise ValueError(f'Unsupported task field: {key}')
                setattr(task, key, value)
            task.state = state
            return self._save(task, f'task.{state}' if state in TERMINAL else 'task.updated')

    def attempt(self, task_id: str, step: str) -> Task:
        with self._lock:
            task = self.get(task_id)
            if task.state in TERMINAL or task.attempts >= task.max_attempts or task.side_effects:
                raise ValueError('Retry budget exhausted, terminal task, or successful side effect already recorded.')
            task.attempts += 1
            task.state, task.active_step = 'executing', step
            return self._save(task)

    def finish(self, task_id: str, result: ToolResult) -> Task:
        with self._lock:
            task = self.get(task_id)
            task.evidence.extend(result.evidence)
            if result.side_effect and result.status == 'success':
                task.side_effects.append({'step': task.active_step, 'summary': result.summary})
            if task.state in TERMINAL:
                # Keep evidence of a late side effect without undoing cancellation.
                return self._save(task, event=None)
            state = {'success': 'completed', 'failed': 'failed', 'partial': 'waiting_external',
                     'cancelled': 'cancelled', 'waiting_confirmation': 'waiting_confirmation',
                     'ambiguous': 'waiting_confirmation', 'started': 'waiting_external'}.get(result.status, 'failed')
            return self.transition(task_id, state, evidence=task.evidence, side_effects=task.side_effects,
                                   error=result.summary if state == 'failed' else None)

    def cached(self, request_id: str) -> ToolResult | None:
        with self._lock:
            row = self.db.execute('SELECT payload FROM tool_results WHERE request_id=?', (request_id,)).fetchone()
        if not row:
            return None
        try:
            payload = json.loads(row[0])
            if (not isinstance(payload, dict) or not isinstance(payload.get('summary'), str)
                    or not isinstance(payload.get('data', {}), dict)
                    or not isinstance(payload.get('evidence', []), list)):
                raise ValueError('Invalid cached result')
            return ToolResult(**payload)
        except (ValueError, TypeError):
            # A recorded request must not execute again just because its stored
            # result is unreadable: the original action may already have run.
            return ToolResult('failed', 'The recorded result is unreadable. This request was not repeated.',
                              {'cached_result_invalid': True}, retryable=False)

    def remember(self, request_id: str, result: ToolResult) -> None:
        with self._lock, self.db:
            self.db.execute('INSERT OR IGNORE INTO tool_results VALUES (?,?)',
                            (request_id, json.dumps(audit.redact(result.to_dict()), default=str)))

    def claim_request(self, request_id: str) -> bool:
        """Durably reserve an invocation before any side effect can start."""
        with self._lock, self.db:
            cursor = self.db.execute('INSERT OR IGNORE INTO tool_request_claims VALUES (?,?)',
                                     (request_id, time.time()))
            return cursor.rowcount == 1

    def release_request(self, request_id: str) -> None:
        """Release only requests whose completed result proves no side effect."""
        with self._lock, self.db:
            self.db.execute('DELETE FROM tool_request_claims WHERE request_id=?', (request_id,))

    def close(self) -> None:
        with self._lock:
            try:
                self.db.execute('PRAGMA wal_checkpoint(PASSIVE)')
            except Exception:
                pass
            self.db.close()


_runtime: TaskRuntime | None = None
_runtime_lock = threading.Lock()


def get_runtime() -> TaskRuntime:
    global _runtime
    with _runtime_lock:
        if _runtime is None:
            _runtime = TaskRuntime(mutable_path(Path(__file__).resolve().parent.parent / 'memory' / 'zaya_runtime.db'))
    return _runtime
