"""Continuous passive screen intelligence and error watcher.

Monitors active desktop foreground windows and terminals in the background.
Detects compiler errors, tracebacks, and exceptions with zero heavy compute
so Zaya possesses immediate situational awareness when the owner speaks.
"""
from __future__ import annotations

import asyncio
import ctypes
import re
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

try:
    import psutil
    _PSUTIL = True
except ImportError:
    _PSUTIL = False


@dataclass
class ScreenContext:
    app_name: str = ""
    window_title: str = ""
    detected_error: str = ""
    error_type: str = ""
    timestamp: float = field(default_factory=time.time)
    has_error: bool = False

    def is_recent(self, max_age_seconds: float = 60.0) -> bool:
        return (time.time() - self.timestamp) <= max_age_seconds


_CRASH_PATTERNS = [
    (re.compile(r"Traceback \(most recent call last\):.*?(?:\n[A-Za-z0-9_.]+(?:Error|Exception):.*)", re.DOTALL), "python_traceback"),
    (re.compile(r"(?:SyntaxError|TypeError|ValueError|KeyError|AttributeError|NameError|IndexError|ImportError):.*"), "python_exception"),
    (re.compile(r"FAILED\s+[\w/\\]+\.py::\w+"), "pytest_failure"),
    (re.compile(r"(?:Uncaught|UnhandledPromiseRejection|ReferenceError|TypeError):\s+.*"), "js_error"),
    (re.compile(r"error\[E\d+\]:.*"), "rust_error"),
    (re.compile(r"fatal error:.*"), "compiler_fatal"),
    (re.compile(r"(?:HTTP\s+)?(?:500|404|502|503)\s+(?:Internal Server Error|Not Found|Bad Gateway)"), "http_error"),
]


class PassiveScreenWatcher:
    def __init__(self, check_interval: float = 2.5):
        self.check_interval = check_interval
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._current_context: Optional[ScreenContext] = None
        self._last_window_text = ""

    def get_foreground_info(self) -> tuple[str, str, int]:
        """Returns (process_name, window_title, pid)."""
        if sys.platform != "win32":
            return "", "", 0

        try:
            u32 = ctypes.windll.user32
            hwnd = u32.GetForegroundWindow()
            if not hwnd:
                return "", "", 0

            buf = ctypes.create_unicode_buffer(512)
            u32.GetWindowTextW(hwnd, buf, 512)
            title = buf.value.strip()

            pid = ctypes.c_ulong()
            u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            proc_id = pid.value

            proc_name = ""
            if _PSUTIL and proc_id:
                try:
                    proc_name = psutil.Process(proc_id).name().lower()
                except Exception:
                    pass

            return proc_name, title, proc_id
        except Exception:
            return "", "", 0

    def inspect_text_for_crashes(self, text: str) -> tuple[str, str]:
        """Checks text for error/traceback signatures. Returns (snippet, error_type)."""
        if not text:
            return "", ""

        for pattern, err_type in _CRASH_PATTERNS:
            match = pattern.search(text)
            if match:
                snippet = match.group(0).strip()
                # Bound snippet size
                if len(snippet) > 800:
                    snippet = snippet[:800] + "... [truncated]"
                return snippet, err_type
        return "", ""

    def update_context(self, text_sample: str = "") -> ScreenContext:
        """Polls current foreground window and updates context."""
        proc_name, title, pid = self.get_foreground_info()

        # Check window title for obvious failure markers (e.g. 'FAILED tests', 'Error in...')
        title_snippet, title_err = self.inspect_text_for_crashes(title)

        snippet, err_type = self.inspect_text_for_crashes(text_sample)
        if not snippet and title_snippet:
            snippet, err_type = title_snippet, title_err

        has_err = bool(snippet)
        ctx = ScreenContext(
            app_name=proc_name,
            window_title=title,
            detected_error=snippet,
            error_type=err_type,
            timestamp=time.time(),
            has_error=has_err,
        )
        if has_err or (self._current_context is None) or (self._current_context.window_title != title):
            self._current_context = ctx
        return ctx

    def get_screen_context_prompt(self) -> str:
        """Generates dynamic prompt injection if there is recent active context or detected errors."""
        ctx = self._current_context
        if not ctx or not ctx.is_recent(90.0):
            return ""

        parts = ["[ACTIVE SCREEN CONTEXT]"]
        if ctx.window_title:
            parts.append(f"Foreground Window: {ctx.window_title} ({ctx.app_name or 'active'})")
        if ctx.has_error and ctx.detected_error:
            parts.append(f"Notice: An active error/traceback ({ctx.error_type}) was detected on the owner's screen:\n{ctx.detected_error}")
            parts.append("If the owner asks what happened, why it failed, or to fix the error, assist immediately with this context.")

        return "\n".join(parts)

    async def _watch_loop(self):
        while self._running:
            try:
                proc, title, pid = self.get_foreground_info()
                # Fast title check
                if title and title != self._last_window_text:
                    self._last_window_text = title
                    self.update_context()
            except Exception:
                pass
            await asyncio.sleep(self.check_interval)

    def start(self, loop: Optional[asyncio.AbstractEventLoop] = None):
        """Starts passive watcher loop."""
        if self._running:
            return
        self._running = True
        current_loop = loop or asyncio.get_event_loop()
        self._task = current_loop.create_task(self._watch_loop())

    def stop(self):
        """Stops passive watcher loop."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            self._task = None


# Global singleton instance
passive_screen_watcher = PassiveScreenWatcher()
