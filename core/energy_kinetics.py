"""Predictive Energy Kinetics & Battery Optimization Sentinel.
Created and developed by Sajan Rai for Zaya.

Monitors battery drain kinetics, drain velocity (%/hr), AC power transition events,
and recommends intelligent power profile switching to prevent unexpected shutdowns.
"""
from __future__ import annotations

import collections
import logging
import platform
import re
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_OS = platform.system()


@dataclass
class BatterySnapshot:
    timestamp: float
    percent: float
    power_plugged: Optional[bool]
    secs_left: Optional[int]


@dataclass
class PowerTelemetry:
    percent: float
    power_plugged: Optional[bool]
    secs_left: Optional[int]
    drain_rate_pct_per_hr: float
    estimated_runtime_hours: Optional[float]
    recommended_profile: str
    active_scheme: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "percent": round(self.percent, 1),
            "power_plugged": self.power_plugged,
            "secs_left": self.secs_left,
            "drain_rate_pct_per_hr": round(self.drain_rate_pct_per_hr, 2),
            "estimated_runtime_hours": (
                round(self.estimated_runtime_hours, 2)
                if self.estimated_runtime_hours is not None
                else None
            ),
            "recommended_profile": self.recommended_profile,
            "active_scheme": self.active_scheme,
        }


class EnergyKineticsSentinel:
    """Monitors power drain kinetics and recommends profile optimizations."""

    def __init__(self, history_len: int = 60) -> None:
        self._history: collections.deque[BatterySnapshot] = collections.deque(maxlen=history_len)
        self._lock = threading.RLock()
        self._last_alert_time: Dict[str, float] = {}
        self.alert_cooldown_sec = 600.0  # 10 minutes between duplicate alerts

    def record_snapshot(
        self,
        percent: float,
        power_plugged: Optional[bool],
        secs_left: Optional[int] = None,
    ) -> None:
        """Record an explicit battery snapshot."""
        with self._lock:
            self._history.append(
                BatterySnapshot(
                    timestamp=time.time(),
                    percent=max(0.0, min(100.0, percent)),
                    power_plugged=power_plugged,
                    secs_left=secs_left,
                )
            )

    def query_live_battery(self) -> Tuple[float, Optional[bool], Optional[int]]:
        """Query platform battery using psutil or mock fallback."""
        try:
            import psutil
            bat = psutil.sensors_battery()
            if bat is not None:
                return float(bat.percent), bat.power_plugged, bat.secsleft
        except Exception:
            pass

        # Windows powercfg query fallback
        if _OS == "Windows":
            try:
                out = subprocess.check_output(
                    ["powershell", "-NoProfile", "-Command", "Get-CimInstance Win32_Battery | Select-Object EstimatedChargeRemaining, BatteryStatus"],
                    text=True,
                    timeout=3,
                )
                m = re.search(r"(\d+)", out)
                if m:
                    return float(m.group(1)), None, None
            except Exception:
                pass

        return 100.0, True, None

    def calculate_drain_rate(self) -> float:
        """Calculate average battery drain rate (% per hour). Positive means draining."""
        with self._lock:
            if len(self._history) < 2:
                return 0.0

            oldest = self._history[0]
            newest = self._history[-1]

            duration_hours = (newest.timestamp - oldest.timestamp) / 3600.0
            if duration_hours <= 0.001:  # < 3.6 seconds
                return 0.0

            # Only calculate drain if unplugged
            if newest.power_plugged is True:
                return 0.0

            delta_pct = oldest.percent - newest.percent
            return max(0.0, delta_pct / duration_hours)

    def evaluate_telemetry(self) -> PowerTelemetry:
        """Evaluate full battery kinetics and recommend power profiles."""
        pct, plugged, secs = self.query_live_battery()
        self.record_snapshot(pct, plugged, secs)

        drain_rate = self.calculate_drain_rate()

        runtime_hours = None
        if secs and secs > 0:
            runtime_hours = secs / 3600.0
        elif drain_rate > 0.5:
            runtime_hours = pct / drain_rate

        # Recommendation logic
        if plugged:
            rec = "performance"
        elif pct <= 20.0 or (drain_rate > 25.0 and pct < 50.0):
            rec = "battery_saver"
        else:
            rec = "balanced"

        from actions.computer_settings import get_power_mode
        active_scheme = get_power_mode()

        telemetry = PowerTelemetry(
            percent=pct,
            power_plugged=plugged,
            secs_left=secs,
            drain_rate_pct_per_hr=drain_rate,
            estimated_runtime_hours=runtime_hours,
            recommended_profile=rec,
            active_scheme=active_scheme,
        )

        self._check_proactive_alerts(telemetry)
        return telemetry

    def _check_proactive_alerts(self, tel: PowerTelemetry) -> None:
        now = time.time()
        # Low Battery Alert
        if not tel.power_plugged and tel.percent <= 15.0:
            last = self._last_alert_time.get("low_battery", 0.0)
            if (now - last) >= self.alert_cooldown_sec:
                self._last_alert_time["low_battery"] = now
                self._dispatch_event("power.low_battery", tel)

        # Rapid Drain Alert (>35% / hr)
        if not tel.power_plugged and tel.drain_rate_pct_per_hr >= 35.0:
            last = self._last_alert_time.get("rapid_drain", 0.0)
            if (now - last) >= self.alert_cooldown_sec:
                self._last_alert_time["rapid_drain"] = now
                self._dispatch_event("power.rapid_drain", tel)

    def _dispatch_event(self, event_name: str, tel: PowerTelemetry) -> None:
        try:
            from core.event_bus import bus
            bus.publish(event_name, telemetry=tel.to_dict())
        except Exception:
            pass


# ── Global Singleton ─────────────────────────────────────────────────────────

_sentinel: Optional[EnergyKineticsSentinel] = None


def get_energy_kinetics_sentinel() -> EnergyKineticsSentinel:
    global _sentinel
    if _sentinel is None:
        _sentinel = EnergyKineticsSentinel()
    return _sentinel
