"""Parallel Sub-Worker Swarm & Multi-Agent Mesh.
Created and developed by Sajan Rai for Zaya.

Enables concurrent, non-blocking sub-worker orchestration for parallelizing
independent research, compilation, analysis, and validation tasks without stalling
the primary assistant conversational loop.
"""
from __future__ import annotations

import concurrent.futures
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class SwarmTask:
    task_id: str
    name: str
    role: str
    status: str  # queued, running, completed, failed, cancelled
    created_at: float
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    result: Any = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def duration_sec(self) -> Optional[float]:
        if self.started_at and self.finished_at:
            return round(self.finished_at - self.started_at, 2)
        elif self.started_at:
            return round(time.monotonic() - self.started_at, 2)
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "name": self.name,
            "role": self.role,
            "status": self.status,
            "created_at": self.created_at,
            "duration_sec": self.duration_sec,
            "result": self.result,
            "error": self.error,
            "metadata": self.metadata,
        }


class SubAgentSwarm:
    """Manages concurrent worker execution and mesh coordination."""

    def __init__(self, max_workers: int = 4) -> None:
        self._max_workers = max(1, min(max_workers, 16))
        self._pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self._max_workers,
            thread_name_prefix="zaya_swarm_worker",
        )
        self._tasks: Dict[str, SwarmTask] = {}
        self._futures: Dict[str, concurrent.futures.Future] = {}
        self._lock = threading.RLock()

    def spawn(
        self,
        name: str,
        role: str,
        fn: Callable[..., Any],
        *args: Any,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> SwarmTask:
        """Spawn a new sub-worker to execute fn concurrently."""
        task_id = f"sw_{uuid.uuid4().hex[:8]}"
        task = SwarmTask(
            task_id=task_id,
            name=name,
            role=role,
            status="queued",
            created_at=time.monotonic(),
            metadata=metadata or {},
        )

        with self._lock:
            self._tasks[task_id] = task

        def _runner():
            task.started_at = time.monotonic()
            task.status = "running"
            try:
                out = fn(*args, **kwargs)
                task.result = out
                task.status = "completed"
            except Exception as e:
                task.error = str(e)
                task.status = "failed"
                logger.warning("[SwarmWorker] Task %s (%s) failed: %s", task_id, name, e)
            finally:
                task.finished_at = time.monotonic()

        future = self._pool.submit(_runner)
        with self._lock:
            self._futures[task_id] = future

        return task

    def get_task(self, task_id: str) -> Optional[SwarmTask]:
        with self._lock:
            return self._tasks.get(task_id)

    def list_tasks(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            tasks = list(self._tasks.values())
        tasks.sort(key=lambda t: t.created_at, reverse=True)
        return [t.to_dict() for t in tasks[:limit]]

    def join(self, task_ids: Optional[List[str]] = None, timeout: float = 30.0) -> Dict[str, Any]:
        """Wait for specified tasks (or all active tasks) to complete."""
        with self._lock:
            if task_ids is None:
                targets = list(self._futures.keys())
            else:
                targets = [tid for tid in task_ids if tid in self._futures]
            futures = [self._futures[tid] for tid in targets]

        done, not_done = concurrent.futures.wait(futures, timeout=timeout)
        return {
            "completed": len(done),
            "pending": len(not_done),
            "tasks": [self._tasks[tid].to_dict() for tid in targets if tid in self._tasks],
        }

    def cancel(self, task_id: str) -> bool:
        with self._lock:
            task = self._tasks.get(task_id)
            future = self._futures.get(task_id)
            if not task or not future:
                return False
            cancelled = future.cancel()
            if cancelled:
                task.status = "cancelled"
                task.finished_at = time.monotonic()
            return cancelled


# ── Global Singleton ─────────────────────────────────────────────────────────

_swarm: Optional[SubAgentSwarm] = None


def get_subagent_swarm() -> SubAgentSwarm:
    global _swarm
    if _swarm is None:
        _swarm = SubAgentSwarm()
    return _swarm
