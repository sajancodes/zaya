"""Habit Learning and Automated Routine Synthesis Engine for Zaya.
Created and developed by Sajan Rai for Zaya.

Passively tracks sequences of user commands and project actions, identifies recurring
behavioral patterns, and synthesizes proactive multi-step executable routines.
"""
from __future__ import annotations

import collections
import json
import logging
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.execution_policy import require_owner
from core.runtime_paths import mutable_path

logger = logging.getLogger(__name__)

STORE_PATH = mutable_path(Path(__file__).resolve().parent.parent / "memory" / "habits.json")


@dataclass
class ActionEvent:
    tool_name: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    project: str = ""
    timestamp: float = field(default_factory=time.time)


@dataclass
class RoutineStep:
    tool_name: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    description: str = ""


@dataclass
class Routine:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:10])
    name: str = ""
    description: str = ""
    trigger_context: str = ""        # e.g. "project:Zaya", "time:morning", "event:startup"
    steps: List[RoutineStep] = field(default_factory=list)
    confidence: float = 0.85
    execution_count: int = 0
    auto_trigger: bool = False
    created_at: float = field(default_factory=time.time)
    last_executed: Optional[float] = None


class HabitEngine:
    """Detects recurring action workflows and compiles automated routines."""

    def __init__(self, store_path: Optional[Path] = None) -> None:
        self._path = store_path or STORE_PATH
        self._lock = threading.RLock()
        self._recent_events: collections.deque = collections.deque(maxlen=100)
        self._routines: Dict[str, Routine] = {}
        self._pattern_counts: Dict[str, int] = collections.defaultdict(int)
        self._min_occurrences: int = 3
        self._load()

    def _load(self) -> None:
        try:
            if self._path.exists():
                data = json.loads(self._path.read_text(encoding="utf-8"))
                for r_data in data.get("routines", []):
                    steps = [RoutineStep(**s) for s in r_data.pop("steps", [])]
                    self._routines[r_data["id"]] = Routine(**r_data, steps=steps)
        except Exception as e:
            logger.debug("[HabitEngine] Load error: %s", e)

    def _save(self) -> None:
        with self._lock:
            try:
                self._path.parent.mkdir(parents=True, exist_ok=True)
                payload = {
                    "routines": [
                        {**asdict(r), "steps": [asdict(s) for s in r.steps]}
                        for r in self._routines.values()
                    ]
                }
                temp = self._path.with_suffix(".tmp")
                temp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
                temp.replace(self._path)
            except Exception as e:
                logger.debug("[HabitEngine] Save error: %s", e)

    # ── Event Logging & Sequence Detection ──────────────────────────────────

    def record_action(self, tool_name: str, parameters: Dict[str, Any], project: str = "") -> Optional[Routine]:
        """Record an executed action and inspect recent history for patterns."""
        with self._lock:
            event = ActionEvent(tool_name=tool_name, parameters=parameters, project=project)
            self._recent_events.append(event)
            return self._analyze_recent_patterns(project)

    def _analyze_recent_patterns(self, project: str) -> Optional[Routine]:
        """Analyze recent event tuples for repeating n-grams (length 2 to 3)."""
        if len(self._recent_events) < 2:
            return None

        # Look at the last 2 and 3 tool combinations
        events_list = list(self._recent_events)
        for n in (2, 3):
            if len(events_list) >= n:
                window = events_list[-n:]
                # Must share the same project context or general desktop
                tools_seq = tuple(e.tool_name for e in window)
                # Ignore trivial repetitive single commands (e.g. volume repeated)
                if len(set(tools_seq)) < 2:
                    continue

                pattern_key = f"{project}|{'->'.join(tools_seq)}"
                self._pattern_counts[pattern_key] += 1

                if self._pattern_counts[pattern_key] >= self._min_occurrences:
                    # Check if routine already exists
                    routine_name = f"Auto: {' + '.join(tools_seq)}"
                    if not any(r.name == routine_name for r in self._routines.values()):
                        steps = [
                            RoutineStep(
                                tool_name=e.tool_name,
                                parameters=copy_safe_params(e.parameters),
                                description=f"Execute {e.tool_name}",
                            )
                            for e in window
                        ]
                        routine = Routine(
                            name=routine_name,
                            description=f"Automated workflow for {' -> '.join(tools_seq)} in {project or 'workspace'}",
                            trigger_context=f"project:{project}" if project else "general",
                            steps=steps,
                            confidence=0.88,
                        )
                        self._routines[routine.id] = routine
                        self._save()
                        logger.info("[HabitEngine] Synthesized new routine: %s", routine.name)
                        return routine
        return None

    # ── Routine Execution & Management ──────────────────────────────────────

    def list_routines(self) -> List[dict]:
        with self._lock:
            return [asdict(r) for r in self._routines.values()]

    def get_routine(self, routine_id: str) -> Optional[Routine]:
        with self._lock:
            return self._routines.get(routine_id)

    def create_custom_routine(
        self,
        name: str,
        steps: List[Dict[str, Any]],
        trigger_context: str = "manual",
        description: str = "",
    ) -> Routine:
        """Manually define a named multi-step routine."""
        require_owner()
        with self._lock:
            r_steps = [RoutineStep(**s) for s in steps]
            routine = Routine(
                name=name.strip(),
                description=description.strip() or f"User custom routine: {name}",
                trigger_context=trigger_context.strip(),
                steps=r_steps,
                confidence=1.0,
            )
            self._routines[routine.id] = routine
            self._save()
            return routine

    def delete_routine(self, routine_id: str) -> bool:
        require_owner()
        with self._lock:
            if routine_id in self._routines:
                del self._routines[routine_id]
                self._save()
                return True
            return False

    def check_context_triggers(self, current_project: str = "") -> List[Routine]:
        """Check if any synthesized routine matches the active context."""
        with self._lock:
            matches = []
            for r in self._routines.values():
                if current_project and r.trigger_context == f"project:{current_project}":
                    matches.append(r)
            return matches

    def mark_executed(self, routine_id: str) -> None:
        with self._lock:
            r = self._routines.get(routine_id)
            if r:
                r.execution_count += 1
                r.last_executed = time.time()
                self._save()


def copy_safe_params(p: Dict[str, Any]) -> Dict[str, Any]:
    """Strip temporary or session-specific keys from stored parameters."""
    safe = {}
    for k, v in p.items():
        if k not in {"session_id", "timestamp", "runtime_id"}:
            safe[k] = v
    return safe


# ── Global Singleton ─────────────────────────────────────────────────────────

_engine: Optional[HabitEngine] = None
_engine_lock = threading.Lock()


def get_habit_engine() -> HabitEngine:
    global _engine
    with _engine_lock:
        if _engine is None:
            _engine = HabitEngine()
        return _engine
