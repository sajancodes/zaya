"""Autonomous Background Sentinel.

Continuously monitors dev servers, battery/hardware health, and workspace integrity.
Surfaces proactive vocal and UI alerts before things break, closing the gap
to 90% Jarvis autonomous situational awareness.
"""
from __future__ import annotations

import asyncio
import socket
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

try:
    import psutil
    _PSUTIL = True
except ImportError:
    _PSUTIL = False


WATCHED_DEV_PORTS = (3000, 3001, 5000, 5173, 8000, 8080, 8081, 4200)


@dataclass
class SentinelAlert:
    id: str
    category: str
    summary: str
    details: dict[str, Any] = field(default_factory=dict)
    severity: str = "medium"
    timestamp: float = field(default_factory=time.time)
    delivered_at: Optional[float] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "category": self.category,
            "summary": self.summary,
            "details": self.details,
            "severity": self.severity,
            "timestamp": self.timestamp,
        }


class BackgroundSentinel:
    def __init__(self, check_interval: float = 4.0):
        self.check_interval = check_interval
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._alerts: deque[SentinelAlert] = deque(maxlen=16)

        # Port state tracking
        self._open_ports: Set[int] = set()
        self._port_cooldowns: Dict[int, float] = {}

        # Battery tracking
        self._last_battery_alert = 0.0

        # Workspace tracking
        self._last_git_check = 0.0

    def check_ports(self) -> List[SentinelAlert]:
        """Checks watched localhost ports for unexpected drops."""
        new_alerts: List[SentinelAlert] = []
        now = time.time()
        currently_open: Set[int] = set()

        for port in WATCHED_DEV_PORTS:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.02)
            try:
                if s.connect_ex(("127.0.0.1", port)) == 0:
                    currently_open.add(port)
            except Exception:
                pass
            finally:
                try:
                    s.close()
                except Exception:
                    pass

        # Detect transition from open -> closed
        dropped = self._open_ports - currently_open
        for port in dropped:
            # Check cooldown
            if (now - self._port_cooldowns.get(port, 0)) > 60.0:
                self._port_cooldowns[port] = now
                summary = f"Dev server on port {port} has terminated unexpectedly."
                # Check passive screen watcher for correlated crashes
                try:
                    from core.passive_screen_watcher import passive_screen_watcher
                    ctx = passive_screen_watcher._current_context
                    if ctx and ctx.is_recent(30.0) and ctx.has_error:
                        summary += f" Recent error: {ctx.detected_error[:120]}"
                except Exception:
                    pass

                alert = SentinelAlert(
                    id=f"port_{port}_{int(now)}",
                    category="server",
                    summary=summary,
                    details={"port": port, "state": "dropped"},
                    severity="high",
                    timestamp=now,
                )
                self._alerts.append(alert)
                new_alerts.append(alert)

        self._open_ports = currently_open
        return new_alerts

    def check_battery(self) -> Optional[SentinelAlert]:
        """Checks for low battery condition while unplugged."""
        if not _PSUTIL:
            return None
        now = time.time()
        if (now - self._last_battery_alert) < 900.0:  # 15 min debounce
            return None

        try:
            battery = psutil.sensors_battery()
            if battery and not battery.power_plugged and battery.percent <= 15:
                self._last_battery_alert = now
                alert = SentinelAlert(
                    id=f"battery_{int(now)}",
                    category="battery",
                    summary=f"Battery is at {int(battery.percent)}%. Please connect your charger, sir.",
                    details={"percent": battery.percent},
                    severity="high",
                    timestamp=now,
                )
                self._alerts.append(alert)
                return alert
        except Exception:
            pass
        return None

    def check_git_conflicts(self, workspace_root: Optional[Path] = None) -> List[SentinelAlert]:
        """Checks for merge conflict markers in workspace files."""
        now = time.time()
        if (now - self._last_git_check) < 30.0:
            return []
        self._last_git_check = now

        root = workspace_root or Path.cwd()
        new_alerts = []

        try:
            for py_file in root.glob("*.py"):
                if py_file.name.startswith("."):
                    continue
                try:
                    text = py_file.read_text(encoding="utf-8", errors="ignore")
                    if "<<<<<<< HEAD" in text and ">>>>>>>" in text:
                        alert = SentinelAlert(
                            id=f"conflict_{py_file.name}_{int(now)}",
                            category="git",
                            summary=f"Merge conflict markers detected in {py_file.name}, sir.",
                            details={"file": str(py_file)},
                            severity="high",
                            timestamp=now,
                        )
                        self._alerts.append(alert)
                        new_alerts.append(alert)
                        break
                except Exception:
                    pass
        except Exception:
            pass

        return new_alerts

    def next_alert(self) -> Optional[dict[str, Any]]:
        """Returns the oldest unconsumed alert."""
        for alert in self._alerts:
            if alert.delivered_at is None:
                return alert.to_dict()
        return None

    def delivered(self, alert_item: dict[str, Any]):
        """Marks an alert as delivered."""
        alert_id = alert_item.get("id")
        for alert in self._alerts:
            if alert.id == alert_id:
                alert.delivered_at = time.time()

    async def _loop_worker(self):
        while self._running:
            try:
                self.check_ports()
                self.check_battery()
                self.check_git_conflicts()
            except Exception:
                pass
            await asyncio.sleep(self.check_interval)

    def start(self, loop: Optional[asyncio.AbstractEventLoop] = None):
        """Starts background monitoring."""
        if self._running:
            return
        self._running = True
        current_loop = loop or asyncio.get_event_loop()
        self._task = current_loop.create_task(self._loop_worker())

    def stop(self):
        """Stops background monitoring."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            self._task = None


# Global singleton instance
_sentinel: Optional[BackgroundSentinel] = None


def get_sentinel() -> BackgroundSentinel:
    global _sentinel
    if _sentinel is None:
        _sentinel = BackgroundSentinel()
    return _sentinel
