"""Monitor Mode — periodic screen-capture surveillance with AI analysis.
Created and developed by Sajan Rai for Zaya.

When the owner says "monitor X" before stepping away, Zaya captures the screen
every N minutes, analyses the screenshot with vision AI (or OCR fallback), and
takes contextual action when the situation warrants it.
"""
from __future__ import annotations

import base64
import logging
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, List, Optional

from core.execution_policy import require_owner

logger = logging.getLogger(__name__)

# ── Defaults ────────────────────────────────────────────────────────────────────
DEFAULT_INTERVAL_SEC = 300        # 5 minutes
MIN_INTERVAL_SEC = 30             # safety floor
MAX_INTERVAL_SEC = 3600           # 1 hour ceiling
DEFAULT_MAX_DURATION_SEC = 14400  # 4 hours
MAX_OBSERVATIONS = 100


@dataclass
class Observation:
    """A single screen-capture analysis snapshot."""
    timestamp: float = field(default_factory=time.time)
    summary: str = ""
    action_taken: str = ""
    needs_attention: bool = False
    raw_ocr: str = ""


@dataclass
class MonitorSession:
    """Represents an active or completed monitoring session."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    task: str = ""
    interval_sec: int = DEFAULT_INTERVAL_SEC
    max_duration_sec: int = DEFAULT_MAX_DURATION_SEC
    started_at: float = field(default_factory=time.time)
    stopped_at: Optional[float] = None
    active: bool = False
    observations: List[dict] = field(default_factory=list)
    alerts_raised: int = 0

    def elapsed(self) -> float:
        end = self.stopped_at or time.time()
        return end - self.started_at

    def summary(self) -> dict:
        return {
            "id": self.id,
            "task": self.task,
            "active": self.active,
            "interval_sec": self.interval_sec,
            "elapsed_sec": round(self.elapsed()),
            "observation_count": len(self.observations),
            "alerts_raised": self.alerts_raised,
        }


class MonitorModeEngine:
    """Background loop that periodically captures & analyses the screen.

    Parameters
    ----------
    capture_fn : callable
        A function ``() -> Optional[bytes]`` returning PNG screenshot bytes.
    analyse_fn : callable
        A function ``(png_bytes: bytes, task: str) -> dict`` returning analysis
        with keys ``summary``, ``needs_attention``, ``action_suggestion``.
    notify_fn : callable or None
        ``(text: str) -> None`` called when urgent attention is needed.
    """

    def __init__(
        self,
        capture_fn: Optional[Callable[[], Optional[bytes]]] = None,
        analyse_fn: Optional[Callable[[bytes, str], dict]] = None,
        notify_fn: Optional[Callable[[str], None]] = None,
    ) -> None:
        self._capture = capture_fn or _default_capture
        self._analyse = analyse_fn or _default_analyse
        self._notify = notify_fn or (lambda t: logger.info("[MonitorMode] %s", t))
        self._lock = threading.RLock()
        self._session: Optional[MonitorSession] = None
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._history: List[MonitorSession] = []

    # ── Public API ──────────────────────────────────────────────────────────

    def start(
        self,
        task: str,
        interval_sec: int = DEFAULT_INTERVAL_SEC,
        max_duration_sec: int = DEFAULT_MAX_DURATION_SEC,
        *,
        _clamp: bool = True,
    ) -> MonitorSession:
        """Begin a new monitoring session."""
        require_owner()
        if not task.strip():
            raise ValueError("Describe what I should monitor.")

        if _clamp:
            interval_sec = max(MIN_INTERVAL_SEC, min(MAX_INTERVAL_SEC, int(interval_sec)))
            max_duration_sec = max(60, int(max_duration_sec))
        else:
            interval_sec = max(1, min(MAX_INTERVAL_SEC, int(interval_sec)))
            max_duration_sec = max(1, int(max_duration_sec))

        with self._lock:
            if self._session and self._session.active:
                raise RuntimeError(
                    f"Already monitoring: '{self._session.task}'. "
                    "Stop it first or adjust the current session."
                )
            session = MonitorSession(
                task=task.strip(),
                interval_sec=interval_sec,
                max_duration_sec=max_duration_sec,
                active=True,
            )
            self._session = session
            self._stop.clear()

        self._thread = threading.Thread(
            target=self._loop, args=(session,), name="zaya-monitor", daemon=True
        )
        self._thread.start()
        logger.info("[MonitorMode] Started: '%s' every %ds", task, interval_sec)
        return session

    def stop(self) -> Optional[MonitorSession]:
        """Stop the current monitoring session."""
        require_owner()
        with self._lock:
            if not self._session or not self._session.active:
                return self._session
            self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)
        with self._lock:
            return self._session

    def status(self) -> dict:
        """Return current session status and recent observations."""
        with self._lock:
            if not self._session:
                return {"active": False, "message": "No monitoring session."}
            return self._session.summary()

    def adjust_interval(self, interval_sec: int) -> dict:
        """Change the capture interval of the active session."""
        require_owner()
        interval_sec = max(MIN_INTERVAL_SEC, min(MAX_INTERVAL_SEC, int(interval_sec)))
        with self._lock:
            if not self._session or not self._session.active:
                raise RuntimeError("No active monitoring session to adjust.")
            self._session.interval_sec = interval_sec
        return {"interval_sec": interval_sec}

    def recent_observations(self, limit: int = 10) -> List[dict]:
        """Return the most recent observations."""
        with self._lock:
            if not self._session:
                return []
            return list(self._session.observations[-limit:])

    def history(self) -> List[dict]:
        """Return summaries of all past sessions."""
        with self._lock:
            return [s.summary() for s in self._history]

    # ── Internal loop ───────────────────────────────────────────────────────

    def _loop(self, session: MonitorSession) -> None:
        """Main monitoring loop — runs in background thread."""
        try:
            while not self._stop.is_set():
                # Check max duration
                if session.elapsed() >= session.max_duration_sec:
                    logger.info("[MonitorMode] Max duration reached, stopping.")
                    self._notify(
                        f"Monitor session for '{session.task}' reached its "
                        f"time limit ({session.max_duration_sec // 60} min)."
                    )
                    break

                # Capture screen
                try:
                    png = self._capture()
                except Exception as exc:
                    logger.warning("[MonitorMode] Capture failed: %s", exc)
                    png = None

                if png:
                    # Analyse
                    try:
                        result = self._analyse(png, session.task)
                    except Exception as exc:
                        logger.warning("[MonitorMode] Analysis failed: %s", exc)
                        result = {"summary": f"Analysis error: {exc}", "needs_attention": False}

                    obs = Observation(
                        summary=result.get("summary", ""),
                        needs_attention=bool(result.get("needs_attention", False)),
                        action_taken=result.get("action_taken", ""),
                        raw_ocr=result.get("raw_ocr", "")[:2000],
                    )

                    with self._lock:
                        session.observations = (
                            session.observations + [asdict(obs)]
                        )[-MAX_OBSERVATIONS:]

                    if obs.needs_attention:
                        session.alerts_raised += 1
                        self._notify(
                            f"[Monitor Alert] {session.task}: {obs.summary}"
                        )
                        logger.info("[MonitorMode] Alert: %s", obs.summary[:200])
                    else:
                        logger.debug("[MonitorMode] OK: %s", obs.summary[:100])
                else:
                    logger.debug("[MonitorMode] No screenshot captured this cycle.")

                # Sleep in responsive increments
                deadline = time.monotonic() + session.interval_sec
                while not self._stop.is_set() and time.monotonic() < deadline:
                    if session.elapsed() >= session.max_duration_sec:
                        break
                    time.sleep(min(0.1, max(0.01, deadline - time.monotonic())))

        except Exception as exc:
            logger.error("[MonitorMode] Loop error: %s", exc)
        finally:
            with self._lock:
                session.active = False
                session.stopped_at = time.time()
                self._history.append(session)
            logger.info("[MonitorMode] Session ended: '%s'", session.task)


# ── Default implementations ─────────────────────────────────────────────────

def _default_capture() -> Optional[bytes]:
    """Capture the primary screen using mss (already used by ScreenPeeler)."""
    from actions.screen_peeler import capture_screen_region
    return capture_screen_region()


def _default_analyse(png_bytes: bytes, task: str) -> dict:
    """Analyse a screenshot using OCR; AI vision is added when available."""
    from actions.screen_peeler import _ocr_via_powershell

    ocr_text = _ocr_via_powershell(png_bytes)
    if not ocr_text:
        return {
            "summary": "Screen captured but no text could be extracted.",
            "needs_attention": False,
            "raw_ocr": "",
        }

    # Simple heuristic checks for common situations
    lower = ocr_text.lower()
    needs_attention = False
    summary_parts = []

    # Check for error indicators
    error_keywords = ["error", "failed", "exception", "crash", "fatal", "panic"]
    found_errors = [kw for kw in error_keywords if kw in lower]
    if found_errors:
        needs_attention = True
        summary_parts.append(f"Detected error keywords: {', '.join(found_errors)}")

    # Check for completion indicators
    done_keywords = ["completed", "finished", "done", "success", "passed"]
    found_done = [kw for kw in done_keywords if kw in lower]
    if found_done:
        summary_parts.append(f"Completion indicators: {', '.join(found_done)}")

    # Check for prompts/waiting
    if any(kw in lower for kw in ["press any key", "y/n", "continue?", "confirm"]):
        needs_attention = True
        summary_parts.append("Screen appears to be waiting for user input.")

    if not summary_parts:
        summary_parts.append(f"Screen text extracted ({len(ocr_text)} chars), no notable events.")

    return {
        "summary": " | ".join(summary_parts),
        "needs_attention": needs_attention,
        "raw_ocr": ocr_text[:2000],
    }


# ── Singleton ────────────────────────────────────────────────────────────────

_engine: Optional[MonitorModeEngine] = None
_engine_lock = threading.Lock()


def get_monitor_engine() -> MonitorModeEngine:
    global _engine
    with _engine_lock:
        if _engine is None:
            _engine = MonitorModeEngine()
        return _engine
