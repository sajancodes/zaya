"""Self-Reflective Metacognition & Tool Reliability Tracker for Zaya.
Created and developed by Sajan Rai.

Maintains self-reflective metrics on tool reliability, latency profiles, consecutive failures,
and circuit-breaker degradation to dynamically adapt execution strategies.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.runtime_paths import mutable_path

logger = logging.getLogger(__name__)

_METRICS_PATH = mutable_path(Path(__file__).resolve().parent.parent / "memory" / "tool_reliability.json")


@dataclass
class ToolMetrics:
    name: str
    invocations: int = 0
    successes: int = 0
    failures: int = 0
    consecutive_failures: int = 0
    total_duration_ms: float = 0.0
    latencies_ms: list[float] = field(default_factory=list)
    last_invoked: float = 0.0
    last_error: str = ""
    status: str = "healthy"  # healthy, degraded, tripped
    tripped_until: float = 0.0

    @property
    def success_rate(self) -> float:
        if self.invocations == 0:
            return 1.0
        return self.successes / float(self.invocations)

    @property
    def avg_latency_ms(self) -> float:
        if self.invocations == 0:
            return 0.0
        return self.total_duration_ms / float(self.invocations)


class MetacognitiveEngine:
    """Self-monitoring metacognitive tracker and circuit breaker."""

    CIRCUIT_BREAKER_CONSECUTIVE_LIMIT = 3
    COOLDOWN_PERIOD_SECONDS = 60.0
    MAX_LATENCY_HISTORY = 50

    def __init__(self, storage_path: Optional[Path] = None) -> None:
        self.storage_path = storage_path or _METRICS_PATH
        self._lock = threading.RLock()
        self._tools: dict[str, ToolMetrics] = {}
        self._load()

    def _load(self) -> None:
        with self._lock:
            if self.storage_path.exists():
                try:
                    data = json.loads(self.storage_path.read_text(encoding="utf-8"))
                    for name, raw in data.items():
                        self._tools[name] = ToolMetrics(
                            name=name,
                            invocations=raw.get("invocations", 0),
                            successes=raw.get("successes", 0),
                            failures=raw.get("failures", 0),
                            consecutive_failures=raw.get("consecutive_failures", 0),
                            total_duration_ms=raw.get("total_duration_ms", 0.0),
                            latencies_ms=raw.get("latencies_ms", []),
                            last_invoked=raw.get("last_invoked", 0.0),
                            last_error=raw.get("last_error", ""),
                            status=raw.get("status", "healthy"),
                            tripped_until=raw.get("tripped_until", 0.0),
                        )
                except Exception as exc:
                    logger.warning("Failed to load tool reliability data: %s", exc)

    def _save(self) -> None:
        with self._lock:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {}
            for name, m in self._tools.items():
                payload[name] = {
                    "name": m.name,
                    "invocations": m.invocations,
                    "successes": m.successes,
                    "failures": m.failures,
                    "consecutive_failures": m.consecutive_failures,
                    "total_duration_ms": round(m.total_duration_ms, 2),
                    "latencies_ms": m.latencies_ms[-self.MAX_LATENCY_HISTORY:],
                    "last_invoked": m.last_invoked,
                    "last_error": m.last_error,
                    "status": m.status,
                    "tripped_until": m.tripped_until,
                }
            self.storage_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def record_execution(
        self,
        tool_name: str,
        duration_ms: float,
        success: bool,
        error_message: str = "",
    ) -> ToolMetrics:
        """Record a completed tool invocation and evaluate health state."""
        clean_name = tool_name.strip().lower()
        now = time.time()

        with self._lock:
            if clean_name not in self._tools:
                self._tools[clean_name] = ToolMetrics(name=clean_name)

            m = self._tools[clean_name]
            m.invocations += 1
            m.total_duration_ms += max(0.0, duration_ms)
            m.last_invoked = now
            m.latencies_ms.append(round(duration_ms, 2))
            if len(m.latencies_ms) > self.MAX_LATENCY_HISTORY:
                m.latencies_ms.pop(0)

            if success:
                m.successes += 1
                m.consecutive_failures = 0
                if m.status in ("degraded", "tripped"):
                    m.status = "healthy"
                    m.tripped_until = 0.0
            else:
                m.failures += 1
                m.consecutive_failures += 1
                m.last_error = error_message

                if m.consecutive_failures >= self.CIRCUIT_BREAKER_CONSECUTIVE_LIMIT:
                    m.status = "tripped"
                    m.tripped_until = now + self.COOLDOWN_PERIOD_SECONDS
                    logger.warning("Tool '%s' circuit breaker tripped for %ds.", clean_name, self.COOLDOWN_PERIOD_SECONDS)
                elif m.consecutive_failures >= 2:
                    m.status = "degraded"

            self._save()
            return m

    def check_tool_health(self, tool_name: str) -> dict[str, Any]:
        """Check if a tool is healthy or currently tripped/degraded."""
        clean_name = tool_name.strip().lower()
        now = time.time()

        with self._lock:
            m = self._tools.get(clean_name)
            if not m:
                return {"name": clean_name, "status": "healthy", "can_execute": True}

            # Check if tripped cooldown has expired
            if m.status == "tripped" and now >= m.tripped_until:
                m.status = "degraded"  # Half-open state for retry
                m.consecutive_failures = 1
                self._save()

            can_execute = m.status != "tripped"
            return {
                "name": clean_name,
                "status": m.status,
                "can_execute": can_execute,
                "success_rate": round(m.success_rate, 3),
                "avg_latency_ms": round(m.avg_latency_ms, 2),
                "consecutive_failures": m.consecutive_failures,
                "last_error": m.last_error,
                "tripped_until": m.tripped_until,
            }

    def generate_diagnostic_report(self) -> dict[str, Any]:
        """Generate high-level self-reflective metacognition report."""
        with self._lock:
            total_tools = len(self._tools)
            healthy = sum(1 for m in self._tools.values() if m.status == "healthy")
            degraded = sum(1 for m in self._tools.values() if m.status == "degraded")
            tripped = sum(1 for m in self._tools.values() if m.status == "tripped")
            total_invocations = sum(m.invocations for m in self._tools.values())
            overall_successes = sum(m.successes for m in self._tools.values())
            overall_rate = (overall_successes / float(total_invocations)) if total_invocations > 0 else 1.0

            tools_summary = [
                {
                    "name": m.name,
                    "status": m.status,
                    "invocations": m.invocations,
                    "success_rate": round(m.success_rate, 3),
                    "avg_latency_ms": round(m.avg_latency_ms, 2),
                    "last_error": m.last_error,
                }
                for m in sorted(self._tools.values(), key=lambda x: x.invocations, reverse=True)
            ]

            summary_text = (
                f"Metacognitive health: {healthy}/{total_tools} tools healthy "
                f"({degraded} degraded, {tripped} tripped). Overall success rate: {overall_rate * 100:.1f}% "
                f"across {total_invocations} recorded invocations."
            )

            return {
                "summary": summary_text,
                "total_tools": total_tools,
                "healthy_count": healthy,
                "degraded_count": degraded,
                "tripped_count": tripped,
                "overall_success_rate": round(overall_rate, 3),
                "total_invocations": total_invocations,
                "tools": tools_summary,
            }

    def reset_tool(self, tool_name: str) -> bool:
        """Reset circuit breaker and metrics for a specific tool."""
        clean_name = tool_name.strip().lower()
        with self._lock:
            if clean_name in self._tools:
                self._tools[clean_name].status = "healthy"
                self._tools[clean_name].consecutive_failures = 0
                self._tools[clean_name].tripped_until = 0.0
                self._save()
                return True
            return False


_metacog: Optional[MetacognitiveEngine] = None
_metacog_lock = threading.Lock()


def get_metacognitive_engine() -> MetacognitiveEngine:
    global _metacog
    with _metacog_lock:
        if _metacog is None:
            _metacog = MetacognitiveEngine()
        return _metacog
