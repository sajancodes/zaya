"""Continuous Screen Monitor using Gemini Robotics ER-2 Streaming Preview.
Created and developed by Sajan Rai for Zaya.

Employs "models/gemini-robotics-er-2-streaming-preview" (with automated reasoning fallbacks)
for continuous, high-temporal, spatial screen understanding, visual state transitions,
progress tracking, and affordance-grounded error detection.
"""
from __future__ import annotations

import base64
import collections
import io
import json
import logging
import re
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from core.execution_policy import require_owner

logger = logging.getLogger(__name__)

# Primary Robotics Embodied Reasoning Model
ROBOTICS_MODEL = "models/gemini-robotics-er-2-streaming-preview"
FALLBACK_LADDER = [
    ROBOTICS_MODEL,
    "models/gemini-3.8-live",
    "gemini-2.5-flash",
]

DEFAULT_INTERVAL_SEC = 3.0
MIN_INTERVAL_SEC = 1.0
MAX_INTERVAL_SEC = 3600.0
DEFAULT_MAX_DURATION_SEC = 14400  # 4 hours
MAX_OBSERVATIONS = 100


@dataclass
class RoboticsObservation:
    """Detailed visual observation produced by the Robotics ER-2 model."""
    timestamp: float = field(default_factory=time.time)
    active_app: str = ""
    summary: str = ""
    state_transition: str = ""
    needs_attention: bool = False
    attention_reason: str = ""
    actionable_elements: List[Dict[str, Any]] = field(default_factory=list)
    action_suggestion: str = ""
    frame_delta_ratio: float = 0.0
    model_used: str = ROBOTICS_MODEL
    raw_response: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "active_app": self.active_app,
            "summary": self.summary,
            "state_transition": self.state_transition,
            "needs_attention": self.needs_attention,
            "attention_reason": self.attention_reason,
            "actionable_elements": self.actionable_elements,
            "action_suggestion": self.action_suggestion,
            "frame_delta_ratio": round(self.frame_delta_ratio, 3),
            "model_used": self.model_used,
        }


def _compute_frame_delta(img1_bytes: Optional[bytes], img2_bytes: Optional[bytes]) -> float:
    """Fast sampling comparison to detect visual changes between consecutive frames."""
    if not img1_bytes or not img2_bytes:
        return 1.0  # Full change
    if img1_bytes == img2_bytes:
        return 0.0

    # Subsample bytes across 128 check points
    step1 = max(1, len(img1_bytes) // 128)
    step2 = max(1, len(img2_bytes) // 128)
    sample1 = img1_bytes[::step1][:128]
    sample2 = img2_bytes[::step2][:128]

    mismatches = sum(1 for b1, b2 in zip(sample1, sample2) if abs(b1 - b2) > 8)
    return float(mismatches) / max(1, min(len(sample1), len(sample2)))


class RoboticsScreenMonitorEngine:
    """Continuous screen monitor driven by Gemini Robotics ER-2 visual streaming."""

    def __init__(
        self,
        model_id: str = ROBOTICS_MODEL,
        interval_sec: float = DEFAULT_INTERVAL_SEC,
        capture_fn: Optional[Callable[[], Optional[bytes]]] = None,
        notify_fn: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.model_id = model_id
        self.interval_sec = max(MIN_INTERVAL_SEC, float(interval_sec))
        self._capture_fn = capture_fn or self._default_capture
        self._notify_fn = notify_fn or (lambda msg: logger.info("[RoboticsMonitor Alert] %s", msg))

        self._lock = threading.RLock()
        self._active: bool = False
        self._task_objective: str = "Continuously monitor screen for critical changes, task completion, or errors."
        self._max_duration_sec: int = DEFAULT_MAX_DURATION_SEC
        self._started_at: float = 0.0
        self._stopped_at: Optional[float] = None
        self._session_id: str = ""
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        self._last_frame_bytes: Optional[bytes] = None
        self._last_analysis_time: float = 0.0
        self._alerts_count: int = 0
        self._history: collections.deque[RoboticsObservation] = collections.deque(maxlen=MAX_OBSERVATIONS)

    # ── Screen Capture ────────────────────────────────────────────────────────

    def _default_capture(self) -> Optional[bytes]:
        """Capture screen bytes with multi-backend fallbacks."""
        # 1. Try ScreenPeeler / mss
        try:
            from actions.screen_peeler import capture_screen_region
            png = capture_screen_region()
            if png and len(png) >= 16:
                return png
        except Exception:
            pass

        # 2. Try PIL ImageGrab
        try:
            from PIL import ImageGrab
            img = ImageGrab.grab()
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            return buf.getvalue()
        except Exception:
            pass

        return None

    # ── Frame Analysis via Robotics ER-2 ──────────────────────────────────────

    def analyze_frame(
        self,
        png_bytes: bytes,
        task: str = "",
        previous_summary: str = "",
        frame_delta: float = 1.0,
    ) -> RoboticsObservation:
        """Query Gemini Robotics ER-2 streaming model to perform spatial visual analysis."""
        objective = task.strip() or self._task_objective

        prompt = (
            f"You are the Gemini Robotics Embodied Reasoning (ER-2) Continuous Screen Monitor.\n"
            f"Analyze this screen frame with spatial precision and temporal awareness.\n\n"
            f"TASK OBJECTIVE: {objective}\n"
            f"PREVIOUS CONTEXT: {previous_summary or 'Initial baseline observation.'}\n\n"
            f"Perform the following evaluations:\n"
            f"1. active_app: Identify the primary foreground application.\n"
            f"2. summary: High-level summary of what is visible on screen right now.\n"
            f"3. state_transition: What visual event or progress occurred since the last check?\n"
            f"4. needs_attention: Set to true IF there is a build error, fatal exception, prompt waiting for user input, completion of long job, crash dialog, or anomalous warning.\n"
            f"5. attention_reason: Explain why immediate user or assistant action is needed (or empty string if normal).\n"
            f"6. actionable_elements: List interactive buttons or inputs with labels and normalized coordinates [ymin, xmin, ymax, xmax] between 0 and 1000.\n"
            f"7. action_suggestion: Concrete recommended command or user action.\n\n"
            f"Respond with ONLY a raw JSON object formatted as:\n"
            f"{{\n"
            f'  "active_app": "<string>",\n'
            f'  "summary": "<string>",\n'
            f'  "state_transition": "<string>",\n'
            f'  "needs_attention": false,\n'
            f'  "attention_reason": "",\n'
            f'  "actionable_elements": [],\n'
            f'  "action_suggestion": ""\n'
            f"}}"
        )

        model_used = self.model_id
        raw_text = ""

        try:
            try:
                from google.genai import types as gtypes
                img_part = gtypes.Part.from_bytes(data=png_bytes, mime_type="image/png")
            except ImportError:
                img_part = {
                    "inline_data": {
                        "mime_type": "image/png",
                        "data": base64.b64encode(png_bytes).decode("ascii"),
                    }
                }

            from core import gemini

            # Call with SMART vision model ladder (fallback from live/robotics tier)
            tiers_to_try = [gemini.SMART, gemini.FAST]
            if self.model_id not in (gemini.SMART, gemini.FAST):
                tiers_to_try.insert(0, self.model_id)

            resp = None
            for tier in tiers_to_try:
                try:
                    resp = gemini.call(
                        [img_part, prompt],
                        tier=tier,
                        timeout_ms=25_000,
                    )
                    if resp and resp.text:
                        model_used = str(tier)
                        raw_text = resp.text.strip()
                        break
                except Exception as call_err:
                    logger.debug("[RoboticsMonitor] Tier %s failed: %s", tier, call_err)
                    continue
        except Exception as e:
            logger.warning("[RoboticsMonitor] Frame analysis failed: %s", e)

        # Parse JSON from response
        parsed: Dict[str, Any] = {}
        if raw_text:
            cleaned = raw_text
            if "```json" in cleaned:
                cleaned = cleaned.split("```json", 1)[1].split("```", 1)[0].strip()
            elif "```" in cleaned:
                cleaned = cleaned.split("```", 1)[1].split("```", 1)[0].strip()
            elif "{" in cleaned and "}" in cleaned:
                cleaned = cleaned[cleaned.find("{"): cleaned.rfind("}") + 1]

            try:
                parsed = json.loads(cleaned)
            except Exception as e:
                logger.debug("[RoboticsMonitor] JSON parse error: %s", e)

        # Fallback to OCR heuristic if API was offline or returned empty
        if not parsed:
            parsed = self._fallback_ocr_analysis(png_bytes, objective)
            model_used = "heuristic-ocr-fallback"

        obs = RoboticsObservation(
            timestamp=time.time(),
            active_app=parsed.get("active_app", "Unknown App"),
            summary=parsed.get("summary", "Screen observed, no significant anomaly."),
            state_transition=parsed.get("state_transition", "Steady state."),
            needs_attention=bool(parsed.get("needs_attention", False)),
            attention_reason=parsed.get("attention_reason", ""),
            actionable_elements=parsed.get("actionable_elements", []),
            action_suggestion=parsed.get("action_suggestion", ""),
            frame_delta_ratio=frame_delta,
            model_used=model_used,
            raw_response=raw_text[:500],
        )

        with self._lock:
            self._history.append(obs)
            if obs.needs_attention:
                self._alerts_count += 1

        return obs

    def _fallback_ocr_analysis(self, png_bytes: bytes, objective: str) -> Dict[str, Any]:
        """Local OCR heuristic fallback when network model is unreachable."""
        try:
            from actions.screen_peeler import _ocr_via_powershell
            text = _ocr_via_powershell(png_bytes)
        except Exception:
            text = ""

        lower = text.lower()
        needs_attention = False
        reasons = []

        for kw in ["error", "failed", "fatal", "exception", "panic", "crash"]:
            if kw in lower:
                needs_attention = True
                reasons.append(f"Detected keyword '{kw}'")

        for kw in ["press any key", "y/n", "continue?", "confirm"]:
            if kw in lower:
                needs_attention = True
                reasons.append(f"Waiting for prompt '{kw}'")

        return {
            "active_app": "Desktop Workspace",
            "summary": f"Local OCR extracted {len(text)} chars from screen.",
            "state_transition": "Screen observed via fallback pipeline.",
            "needs_attention": needs_attention,
            "attention_reason": ", ".join(reasons) if reasons else "",
            "actionable_elements": [],
            "action_suggestion": "Inspect active terminal or window." if needs_attention else "",
        }

    # ── Continuous Monitoring Loop ──────────────────────────────────────────

    def start(
        self,
        task_objective: str = "",
        interval_sec: float = DEFAULT_INTERVAL_SEC,
        max_duration_sec: int = DEFAULT_MAX_DURATION_SEC,
    ) -> Dict[str, Any]:
        """Start the continuous background screen monitoring loop."""
        require_owner()

        with self._lock:
            if self._active:
                return {
                    "status": "already_running",
                    "session_id": self._session_id,
                    "task": self._task_objective,
                    "model": self.model_id,
                    "interval_sec": self.interval_sec,
                }

            self._active = True
            self._task_objective = task_objective.strip() or self._task_objective
            self.interval_sec = max(MIN_INTERVAL_SEC, min(MAX_INTERVAL_SEC, float(interval_sec)))
            self._max_duration_sec = max(10, int(max_duration_sec))
            self._started_at = time.time()
            self._stopped_at = None
            self._session_id = uuid.uuid4().hex[:10]
            self._stop_event.clear()
            self._alerts_count = 0

            self._thread = threading.Thread(
                target=self._monitor_loop,
                name="zaya-robotics-screen-monitor",
                daemon=True,
            )
            self._thread.start()

        logger.info(
            "[RoboticsMonitor] Started continuous surveillance using '%s' every %.1fs",
            self.model_id,
            self.interval_sec,
        )

        return {
            "status": "started",
            "session_id": self._session_id,
            "model": self.model_id,
            "interval_sec": self.interval_sec,
            "task": self._task_objective,
        }

    def stop(self) -> Dict[str, Any]:
        """Stop the continuous background screen monitor."""
        require_owner()

        with self._lock:
            if not self._active:
                return {"status": "not_active"}

            self._active = False
            self._stopped_at = time.time()
            self._stop_event.set()

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)

        return {
            "status": "stopped",
            "session_id": self._session_id,
            "elapsed_sec": round((self._stopped_at or time.time()) - self._started_at, 1),
            "alerts_raised": self._alerts_count,
            "total_observations": len(self._history),
        }

    def status(self) -> Dict[str, Any]:
        """Get live monitoring status and latest observation."""
        with self._lock:
            elapsed = 0.0
            if self._active:
                elapsed = time.time() - self._started_at
            elif self._stopped_at:
                elapsed = self._stopped_at - self._started_at

            latest = self._history[-1].to_dict() if self._history else None

            return {
                "active": self._active,
                "session_id": self._session_id,
                "model": self.model_id,
                "interval_sec": self.interval_sec,
                "elapsed_sec": round(elapsed, 1),
                "task": self._task_objective,
                "alerts_raised": self._alerts_count,
                "total_observations": len(self._history),
                "latest_observation": latest,
            }

    def set_interval(self, interval_sec: float) -> float:
        """Dynamically adjust sampling interval."""
        require_owner()
        with self._lock:
            self.interval_sec = max(MIN_INTERVAL_SEC, min(MAX_INTERVAL_SEC, float(interval_sec)))
            return self.interval_sec

    def observe_now(self, task: str = "") -> RoboticsObservation:
        """Capture and analyze a single frame immediately."""
        png = self._capture_fn()
        if not png:
            return RoboticsObservation(
                summary="Screen capture returned no bytes.",
                needs_attention=False,
                model_used=self.model_id,
            )
        prev_summary = self._history[-1].summary if self._history else ""
        return self.analyze_frame(png, task=task, previous_summary=prev_summary, frame_delta=1.0)

    def get_recent_observations(self, limit: int = 10) -> List[Dict[str, Any]]:
        with self._lock:
            return [obs.to_dict() for obs in list(self._history)[-limit:]]

    # ── Background Thread Loop ──────────────────────────────────────────────

    def _monitor_loop(self) -> None:
        logger.info("[RoboticsMonitor] Loop active.")
        prev_frame: Optional[bytes] = None
        prev_summary: str = ""

        try:
            while not self._stop_event.is_set():
                now = time.time()
                # Check maximum duration timeout
                if (now - self._started_at) >= self._max_duration_sec:
                    logger.info("[RoboticsMonitor] Reached max duration (%ds). Stopping.", self._max_duration_sec)
                    self._notify_fn(f"Robotics screen monitor reached scheduled time limit.")
                    break

                # 1. Capture screen
                frame = self._capture_fn()
                if frame:
                    # 2. Compute visual delta
                    delta = _compute_frame_delta(prev_frame, frame)
                    time_since_last_analysis = now - self._last_analysis_time

                    # Trigger analysis if visual content changed (> 2% diff) or heartbeat timeout (>= 25s)
                    if delta > 0.02 or time_since_last_analysis >= 25.0:
                        obs = self.analyze_frame(
                            frame,
                            task=self._task_objective,
                            previous_summary=prev_summary,
                            frame_delta=delta,
                        )
                        prev_summary = obs.summary
                        prev_frame = frame
                        self._last_analysis_time = now

                        # Trigger alerts if attention needed
                        if obs.needs_attention:
                            msg = f"Screen Alert: {obs.attention_reason or obs.summary}"
                            self._notify_fn(msg)

                # Sleep responsive increments
                deadline = time.monotonic() + self.interval_sec
                while not self._stop_event.is_set() and time.monotonic() < deadline:
                    time.sleep(0.05)

        except Exception as e:
            logger.error("[RoboticsMonitor] Loop encountered exception: %s", e)
        finally:
            with self._lock:
                self._active = False
                self._stopped_at = time.time()
            logger.info("[RoboticsMonitor] Loop terminated.")


# ── Global Singleton ─────────────────────────────────────────────────────────

_robotics_monitor: Optional[RoboticsScreenMonitorEngine] = None
_rm_lock = threading.Lock()


def get_robotics_screen_monitor() -> RoboticsScreenMonitorEngine:
    global _robotics_monitor
    with _rm_lock:
        if _robotics_monitor is None:
            _robotics_monitor = RoboticsScreenMonitorEngine()
        return _robotics_monitor
