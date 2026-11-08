"""Unified Project Awareness Service.

Reconciles active workspace windows, registered projects, task runtime state,
background sentinel alerts, and persistent project state to maintain an
authoritative understanding of the active project and its provenance.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core.runtime_paths import mutable_path

logger = logging.getLogger(__name__)

DEFAULT_PERSISTED_PATH = mutable_path(Path(__file__).resolve().parent.parent / "memory" / "project_state.json")


@dataclass
class Observation:
    source: str          # "workspace", "task_runtime", "project_index", "sentinel", "conversation", "persisted"
    kind: str            # "project", "task", "process", "workspace", "alert", "history"
    project: str         # project name or ""
    timestamp: float
    confidence: float    # 0.0-1.0
    stale: bool = False
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "kind": self.kind,
            "project": self.project,
            "timestamp": self.timestamp,
            "confidence": self.confidence,
            "stale": self.stale,
            "details": self.details,
        }


class ProjectAwarenessService:
    def __init__(self, persisted_path: Path | None = None):
        self._persisted_path = Path(persisted_path) if persisted_path else DEFAULT_PERSISTED_PATH
        self._lock = threading.RLock()
        self._active_project: str = ""
        self._last_known_project: str = ""
        self._manual_project: str = ""
        self._manual_confidence: float = 1.0
        self._manual_timestamp: float = 0.0
        self._last_rehydrated: float = 0.0
        self._rehydrate_from_disk()

    def _rehydrate_from_disk(self) -> None:
        with self._lock:
            if not self._persisted_path.exists():
                return
            try:
                data = json.loads(self._persisted_path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    self._active_project = str(data.get("active_project") or "").strip()
                    self._last_known_project = str(data.get("last_known_project") or "").strip()
                    if not self._last_known_project and self._active_project:
                        self._last_known_project = self._active_project
                    self._last_rehydrated = time.time()
            except Exception as e:
                logger.debug("Failed to read project_state.json: %s", e)

    def _save_to_disk(self) -> None:
        with self._lock:
            try:
                self._persisted_path.parent.mkdir(parents=True, exist_ok=True)
                temp = self._persisted_path.with_suffix(".tmp")
                payload = {
                    "version": 1,
                    "active_project": self._active_project,
                    "last_known_project": self._last_known_project,
                    "updated_at": time.time(),
                }
                temp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
                temp.replace(self._persisted_path)
            except Exception as e:
                logger.debug("Failed to save project_state.json: %s", e)

    def set_active_project(self, name: str, source: str = "manual", confidence: float = 0.8) -> None:
        """Sets the active project explicitly."""
        clean_name = str(name or "").strip()
        with self._lock:
            if clean_name:
                self._manual_project = clean_name
                self._manual_confidence = min(1.0, max(0.0, float(confidence)))
                self._manual_timestamp = time.time()
                self._active_project = clean_name
                self._last_known_project = clean_name
                self._save_to_disk()

    def clear_active_project(self) -> None:
        """Clears the active project and resets manual override."""
        with self._lock:
            self._manual_project = ""
            self._manual_timestamp = 0.0
            self._active_project = ""
            self._last_known_project = ""
            self._save_to_disk()

    def rehydrate(self) -> dict[str, Any]:
        """Rehydrates project state on startup or after provider reset."""
        with self._lock:
            self._rehydrate_from_disk()
            return self.snapshot()

    def active_project(self) -> str:
        """Returns the currently active project name according to observation reconciliation."""
        snap = self.snapshot()
        return snap.get("active_project", "")

    def snapshot(self) -> dict[str, Any]:
        """Gathers observations across all subsystems and reconciles current project state."""
        now = time.time()
        observations: list[Observation] = []
        history_observations: list[Observation] = []

        with self._lock:
            # 1. Manual override (if set)
            if self._manual_project:
                age = now - self._manual_timestamp
                is_stale = age > 3600.0
                conf = self._manual_confidence * (0.8 if is_stale else 1.0)
                observations.append(Observation(
                    source="manual",
                    kind="project",
                    project=self._manual_project,
                    timestamp=self._manual_timestamp,
                    confidence=conf,
                    stale=is_stale,
                    details={"manual": True, "age_seconds": round(age)},
                ))

            # 2. Workspace context (IDE / foreground window)
            workspace_data: dict[str, Any] = {}
            try:
                from core.workspace_context import tracker
                workspace_data = tracker.snapshot()
                ws_project = str(workspace_data.get("project_name") or "").strip()
                ws_process = str(workspace_data.get("process_name") or "").strip()
                ws_title = str(workspace_data.get("window_title") or "").strip()
                ws_changed = float(workspace_data.get("changed_at") or 0.0)
                ws_age = workspace_data.get("age_seconds", 0)

                if ws_project:
                    # Active IDE window with identified project
                    observations.append(Observation(
                        source="workspace",
                        kind="workspace",
                        project=ws_project,
                        timestamp=ws_changed or now,
                        confidence=0.95,
                        stale=False,
                        details={
                            "window_title": ws_title,
                            "process_name": ws_process,
                            "pid": workspace_data.get("pid", 0),
                            "age_seconds": ws_age,
                        },
                    ))
                    # Automatically track as active and last known project
                    self._active_project = ws_project
                    self._last_known_project = ws_project
                    self._save_to_disk()
            except Exception as e:
                logger.debug("Failed to query workspace tracker: %s", e)

            # 3. Persisted project state from disk (if workspace has no active IDE)
            if self._active_project:
                # If we have a persisted active project but workspace has no active IDE project
                ws_project = str(workspace_data.get("project_name") or "").strip()
                if not ws_project or ws_project != self._active_project:
                    observations.append(Observation(
                        source="persisted",
                        kind="project",
                        project=self._active_project,
                        timestamp=self._last_rehydrated or now,
                        confidence=0.75,
                        stale=True,
                        details={"persisted": True, "last_known": self._last_known_project},
                    ))

            # 4. Registered projects from project_index
            registered_projects: list[dict] = []
            try:
                from memory.project_index import INDEX_PATH
                if INDEX_PATH.exists():
                    records = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
                    if isinstance(records, dict):
                        # Sort by last_seen descending
                        sorted_records = sorted(
                            records.values(),
                            key=lambda r: float(r.get("last_seen", 0.0)),
                            reverse=True,
                        )
                        for rec in sorted_records:
                            p_name = str(rec.get("name") or "").strip()
                            p_path = str(rec.get("path") or "").strip()
                            last_seen = float(rec.get("last_seen", 0.0))
                            if p_name:
                                registered_projects.append({"name": p_name, "path": p_path, "last_seen": last_seen})
                                observations.append(Observation(
                                    source="project_index",
                                    kind="project",
                                    project=p_name,
                                    timestamp=last_seen or now,
                                    confidence=0.8,
                                    stale=False,
                                    details={"path": p_path, "aliases": rec.get("aliases", [])},
                                ))
            except Exception as e:
                logger.debug("Failed to query project index: %s", e)

            # 5. Task runtime (active, recent, or failed tasks)
            active_task: dict[str, Any] | None = None
            running_process: dict[str, Any] | None = None
            try:
                from core.task_runtime import TERMINAL, get_runtime
                runtime = get_runtime()
                tasks = runtime.list(limit=20)
                for t in tasks:
                    t_dict = {
                        "id": t.id,
                        "goal": t.goal,
                        "state": t.state,
                        "active_step": t.active_step,
                        "updated_at": t.updated_at,
                    }
                    if t.state not in TERMINAL and active_task is None:
                        active_task = t_dict
                        observations.append(Observation(
                            source="task_runtime",
                            kind="task",
                            project="",
                            timestamp=t.updated_at,
                            confidence=0.9,
                            stale=False,
                            details=t_dict,
                        ))
            except Exception as e:
                logger.debug("Failed to query task runtime: %s", e)

            # 5b. Coding jobs (active or running coding process)
            try:
                from core.coding_jobs import get_jobs
                c_jobs = get_jobs()
                c_exec = c_jobs.execution_status()
                if c_exec.get("process_running") or c_exec.get("worker_running"):
                    active_job = c_jobs.active() or c_jobs.latest()
                    running_process = {
                        "type": "opencode",
                        "pid": c_exec.get("pid"),
                        "worker_running": c_exec.get("worker_running"),
                        "process_running": c_exec.get("process_running"),
                        "project": active_job.project if active_job else "",
                        "phase": active_job.phase if active_job else "",
                        "progress": active_job.progress if active_job else "",
                    }
                    if active_job and active_job.project:
                        job_p_name = Path(active_job.project).name
                        observations.append(Observation(
                            source="coding_job",
                            kind="process",
                            project=job_p_name,
                            timestamp=active_job.updated_at,
                            confidence=0.98,
                            stale=False,
                            details=running_process,
                        ))
            except Exception as e:
                logger.debug("Failed to query coding jobs: %s", e)

            # 6. Background Sentinel alerts
            sentinel_alerts: list[dict[str, Any]] = []
            try:
                from core.background_sentinel import get_sentinel
                sentinel = get_sentinel()
                with sentinel._lock:
                    for alert in sentinel._alerts:
                        a_dict = alert.to_dict()
                        sentinel_alerts.append(a_dict)
                        # Extract any project or file context from alert
                        alert_file = alert.details.get("file", "")
                        observations.append(Observation(
                            source="sentinel",
                            kind="alert",
                            project="",
                            timestamp=alert.timestamp,
                            confidence=0.85,
                            stale=alert.delivered_at is not None,
                            details={"alert_id": alert.id, "summary": alert.summary, "file": alert_file},
                        ))
            except Exception as e:
                logger.debug("Failed to query background sentinel: %s", e)

            # 7. Conversation archive (strictly historical context)
            try:
                from memory.conversation_store import ConversationStore
                conv = ConversationStore()
                recent_msgs = conv.recent(limit=5)
                for msg in recent_msgs:
                    history_obs = Observation(
                        source="conversation",
                        kind="history",
                        project="",
                        timestamp=float(msg.get("created", 0.0)),
                        confidence=0.3,
                        stale=True,
                        details={"role": msg.get("role"), "text": msg.get("text", "")[:120]},
                    )
                    history_observations.append(history_obs)
            except Exception as e:
                logger.debug("Failed to query conversation store: %s", e)

            # Reconcile authoritative active project
            # Rules:
            # 1. Conversation rows NEVER set active project.
            # 2. Never treat an empty task list as "no project active".
            # 3. Project remains active when no coding process runs.
            # 4. Resolve in order of highest confidence among non-stale/fresh project observations,
            #    falling back to registered projects or persisted state.
            resolved_active = ""
            project_candidates: list[Observation] = [
                obs for obs in observations
                if obs.project and obs.kind in ("project", "workspace", "process")
            ]

            if project_candidates:
                # Sort by: (not stale) desc, confidence desc, timestamp desc
                project_candidates.sort(
                    key=lambda o: (not o.stale, o.confidence, o.timestamp),
                    reverse=True,
                )
                resolved_active = project_candidates[0].project

            if not resolved_active:
                if self._active_project:
                    resolved_active = self._active_project
                elif self._last_known_project:
                    resolved_active = self._last_known_project
                elif registered_projects:
                    resolved_active = registered_projects[0]["name"]

            if resolved_active and resolved_active != self._active_project:
                self._active_project = resolved_active
                self._last_known_project = resolved_active
                self._save_to_disk()

            # Compile sources list with provenance
            sources_summary = [
                {
                    "source": obs.source,
                    "kind": obs.kind,
                    "project": obs.project,
                    "timestamp": obs.timestamp,
                    "confidence": obs.confidence,
                    "stale": obs.stale,
                }
                for obs in observations
            ]

            return {
                "active_project": resolved_active,
                "last_known_project": self._last_known_project or resolved_active,
                "active_task": active_task,
                "running_process": running_process,
                "workspace": workspace_data,
                "background_alerts": sentinel_alerts,
                "history": [h.to_dict() for h in history_observations],
                "sources": sources_summary,
            }


# Global singleton instance
_awareness: ProjectAwarenessService | None = None
_awareness_lock = threading.RLock()


def get_project_awareness() -> ProjectAwarenessService:
    global _awareness
    with _awareness_lock:
        if _awareness is None:
            _awareness = ProjectAwarenessService()
        return _awareness
