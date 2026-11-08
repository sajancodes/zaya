"""Autonomous Background Sentinel.

Continuously monitors dev servers, battery/hardware health, and workspace integrity.
Surfaces proactive vocal and UI alerts before things break, closing the gap
to 90% Zaya autonomous situational awareness.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import socket
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core.runtime_paths import mutable_path

try:
    import psutil
    _PSUTIL = True
except ImportError:
    _PSUTIL = False

logger = logging.getLogger(__name__)

WATCHED_DEV_PORTS = (3000, 3001, 5000, 5173, 8000, 8080, 8081, 4200)
DEFAULT_STORE_PATH = mutable_path(Path(__file__).resolve().parent.parent / "memory" / "sentinel_alerts.json")

TEXT_EXTENSIONS: set[str] = {
    ".py", ".xml", ".kt", ".java", ".json", ".ts", ".tsx",
    ".js", ".jsx", ".html", ".css", ".md", ".txt", ".toml",
    ".yaml", ".yml", ".gradle",
}

EXCLUDED_DIRS: set[str] = {
    ".git", ".venv", "venv", "node_modules", "__pycache__",
    "dist", "build", ".gradle", ".idea", ".vscode",
}


@dataclass
class SentinelAlert:
    id: str
    category: str
    summary: str
    details: dict[str, Any] = field(default_factory=dict)
    severity: str = "medium"
    timestamp: float = field(default_factory=time.time)
    delivered_at: float | None = None

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
    def __init__(self, check_interval: float = 4.0, store_path: Path | None = None):
        self.check_interval = check_interval
        self._store_path = Path(store_path) if store_path else DEFAULT_STORE_PATH
        self._lock = threading.RLock()
        self._running = False
        self._task: asyncio.Task | None = None
        self._alerts: deque[SentinelAlert] = deque(maxlen=64)

        # Persistent delivery state
        self._delivered: dict[str, float] = self._load_delivered()

        # Port state tracking
        self._open_ports: set[int] = set()
        self._port_cooldowns: dict[int, float] = {}

        # Battery tracking
        self._last_battery_alert = 0.0

        # Workspace tracking
        self._last_git_check = 0.0

    def _load_delivered(self) -> dict[str, float]:
        with self._lock:
            if not self._store_path.exists():
                return {}
            try:
                data = json.loads(self._store_path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    delivered = data.get("delivered", data)
                    if isinstance(delivered, dict):
                        return {str(k): float(v) for k, v in delivered.items() if isinstance(v, (int, float))}
            except Exception as e:
                logger.debug("Failed to read sentinel delivery store: %s", e)
            return {}

    def _save_delivered(self) -> None:
        with self._lock:
            try:
                self._store_path.parent.mkdir(parents=True, exist_ok=True)
                temp = self._store_path.with_suffix(".tmp")
                payload = {
                    "version": 1,
                    "delivered": self._delivered,
                }
                temp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
                temp.replace(self._store_path)
            except Exception as e:
                logger.debug("Failed to write sentinel delivery store: %s", e)

    def _upsert_alert(self, alert: SentinelAlert) -> SentinelAlert:
        with self._lock:
            for existing in self._alerts:
                if existing.id == alert.id:
                    existing.timestamp = alert.timestamp
                    existing.details = alert.details
                    existing.summary = alert.summary
                    existing.severity = alert.severity
                    return existing

            if alert.id in self._delivered:
                alert.delivered_at = self._delivered[alert.id]

            self._alerts.append(alert)
            return alert

    def check_ports(self) -> list[SentinelAlert]:
        """Checks watched localhost ports for unexpected drops."""
        new_alerts: list[SentinelAlert] = []
        now = time.time()
        currently_open: set[int] = set()

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
            if (now - self._port_cooldowns.get(port, 0)) > 60.0:
                self._port_cooldowns[port] = now
                summary = f"Dev server on port {port} has terminated unexpectedly."
                try:
                    from core.passive_screen_watcher import passive_screen_watcher
                    ctx = passive_screen_watcher._current_context
                    if ctx and ctx.is_recent(30.0) and ctx.has_error:
                        summary += f" Recent error: {ctx.detected_error[:120]}"
                except Exception:
                    pass

                alert = SentinelAlert(
                    id=f"port:{port}:{int(now)}",
                    category="server",
                    summary=summary,
                    details={"port": port, "state": "dropped"},
                    severity="high",
                    timestamp=now,
                )
                upserted = self._upsert_alert(alert)
                new_alerts.append(upserted)

        self._open_ports = currently_open
        return new_alerts

    def check_battery(self) -> SentinelAlert | None:
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
                    id=f"battery:{int(battery.percent)}:{int(now)}",
                    category="battery",
                    summary=f"Battery is at {int(battery.percent)}%. Please connect your charger, sir.",
                    details={"percent": battery.percent},
                    severity="high",
                    timestamp=now,
                )
                return self._upsert_alert(alert)
        except Exception:
            pass
        return None

    def check_git_conflicts(
        self,
        workspace_root: Path | None = None,
        force: bool = False,
        max_files: int = 500,
        max_file_size: int = 1_000_000,
    ) -> list[SentinelAlert]:
        """Checks for merge conflict markers across workspace files."""
        now = time.time()
        if not force and (now - self._last_git_check) < 30.0:
            return []
        self._last_git_check = now

        root = (workspace_root or Path.cwd()).resolve()
        detected_alerts: list[SentinelAlert] = []
        files_scanned = 0

        try:
            for dirpath, dirnames, filenames in os.walk(root):
                # Filter out excluded directories in-place
                dirnames[:] = [
                    d for d in dirnames
                    if d not in EXCLUDED_DIRS and not d.startswith(".venv")
                ]

                for fname in filenames:
                    if files_scanned >= max_files:
                        break
                    file_path = Path(dirpath) / fname
                    if file_path.suffix not in TEXT_EXTENSIONS:
                        continue

                    try:
                        stat = file_path.stat()
                        if stat.st_size > max_file_size:
                            continue
                        files_scanned += 1
                        content_bytes = file_path.read_bytes()
                        if b"<<<<<<< HEAD" in content_bytes and b">>>>>>>" in content_bytes:
                            content_hash = hashlib.sha256(content_bytes).hexdigest()[:16]
                            alert_id = f"conflict:{file_path.resolve()}:{content_hash}"
                            alert = SentinelAlert(
                                id=alert_id,
                                category="git",
                                summary=f"Merge conflict markers detected in {file_path.name}, sir.",
                                details={"file": str(file_path.resolve())},
                                severity="high",
                                timestamp=now,
                            )
                            upserted = self._upsert_alert(alert)
                            detected_alerts.append(upserted)
                    except Exception:
                        continue
                if files_scanned >= max_files:
                    break
        except Exception as e:
            logger.debug("check_git_conflicts scan failed: %s", e)

        return detected_alerts

    def next_alert(self) -> dict[str, Any] | None:
        """Returns the oldest unconsumed alert."""
        with self._lock:
            for alert in self._alerts:
                if alert.id in self._delivered:
                    alert.delivered_at = self._delivered[alert.id]
                    continue
                if alert.delivered_at is None:
                    return alert.to_dict()
            return None

    def delivered(self, alert_item: dict[str, Any]) -> None:
        """Marks an alert as delivered persistently across process restarts."""
        alert_id = alert_item.get("id")
        if not alert_id:
            return
        with self._lock:
            now = time.time()
            self._delivered[str(alert_id)] = now
            for alert in self._alerts:
                if alert.id == alert_id:
                    alert.delivered_at = now
            self._save_delivered()

    async def _loop_worker(self):
        while self._running:
            try:
                self.check_ports()
                self.check_battery()
                self.check_git_conflicts()
            except Exception:
                pass
            await asyncio.sleep(self.check_interval)

    def start(self, loop: asyncio.AbstractEventLoop | None = None):
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
_sentinel: BackgroundSentinel | None = None


def get_sentinel() -> BackgroundSentinel:
    global _sentinel
    if _sentinel is None:
        _sentinel = BackgroundSentinel()
    return _sentinel
