"""Track active workspace context (foreground window, process, project, and session activity).

Publishes 'workspace.changed' on the runtime EventBus whenever the active
window/process changes. Updates contextual SessionActivity for authorized external
surfaces (e.g. WhatsApp status).
"""
from __future__ import annotations

import logging
import os
import platform
import re
import threading
import time
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)

# Known developer/editor process names to project folder or file detection
_IDE_PROCESSES = {
    "code.exe": "vscode",
    "code": "vscode",
    "devenv.exe": "visual_studio",
    "idea64.exe": "intellij",
    "pycharm64.exe": "pycharm",
    "webstorm64.exe": "webstorm",
    "sublime_text.exe": "sublime",
    "notepad++.exe": "notepad++",
    "cursor.exe": "cursor",
    "windsurf.exe": "windsurf",
}

_BROWSER_PROCESSES = {
    "chrome.exe": "chrome",
    "msedge.exe": "edge",
    "firefox.exe": "firefox",
    "brave.exe": "brave",
    "opera.exe": "opera",
}


def clean_title(title: str) -> str:
    """Sanitize window title removing excess whitespace and trailing brand markers."""
    t = str(title or "").strip()
    if not t:
        return ""
    # Strip common editor/browser suffix patterns
    # The Edge branch used to hold a literal U+200B zero-width space in the
    # source. It is invisible, survives copy/paste unpredictably and makes the
    # pattern unreadable; the escape says exactly the same thing. like " - Visual Studio Code", " - Sublime Text"
    t = re.sub(r"\s+[-—]\s+(Visual Studio Code|Google Chrome|Microsoft\u200b? Edge|Mozilla Firefox|Brave|Sublime Text|Notepad\+\+)$", "", t, flags=re.IGNORECASE)
    return t.strip()


def extract_project_name(title: str, process_name: str) -> str:
    """Extract a clean project/workspace name from window title and process."""
    proc = (process_name or "").lower().strip()
    clean = clean_title(title)
    if not clean:
        return ""

    if proc in _IDE_PROCESSES:
        # VS Code style: "file_or_folder - workspace - Visual Studio Code" or "[Extension] - folder"
        parts = [p.strip() for p in clean.split(" - ") if p.strip()]
        if len(parts) >= 2:
            return parts[-1]
        if parts:
            return parts[0]

    return ""


class WorkspaceTracker:
    """Monitors the active window/process and manages workspace context."""

    def __init__(
        self,
        clock: Callable[[], float] = time.monotonic,
        poll_interval: float = 1.0,
        bus: Any | None = None,
    ) -> None:
        self._clock = clock
        self._poll_interval = poll_interval
        self._bus = bus
        self._lock = threading.RLock()
        self._current_context: dict[str, Any] = {
            "window_title": "",
            "process_name": "",
            "pid": 0,
            "project_name": "",
            "changed_at": 0.0,
        }
        self._running = False
        self._thread: threading.Thread | None = None

    def _get_bus(self):
        if self._bus is not None:
            return self._bus
        try:
            from core.event_bus import bus
            return bus
        except ImportError:
            return None

    def get_foreground_info(self) -> dict[str, Any]:
        """Query OS for the currently focused foreground window and process."""
        title = ""
        process_name = ""
        pid = 0

        if platform.system() == "Windows":
            try:
                import ctypes
                from ctypes import wintypes
                user32 = ctypes.windll.user32
                hwnd = user32.GetForegroundWindow()
                if hwnd:
                    length = user32.GetWindowTextLengthW(hwnd)
                    if length > 0:
                        buff = ctypes.create_unicode_buffer(length + 1)
                        user32.GetWindowTextW(hwnd, buff, length + 1)
                        title = buff.value.strip()

                    dw_pid = wintypes.DWORD()
                    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(dw_pid))
                    pid = dw_pid.value
                    if pid > 0:
                        try:
                            import psutil
                            proc = psutil.Process(pid)
                            process_name = proc.name()
                        except Exception:
                            process_name = ""
            except Exception as e:
                logger.debug("Error inspecting Windows foreground window: %s", e)
        else:
            # Fallback for Linux / MacOS if needed
            title = ""
            process_name = ""
            pid = 0

        project = extract_project_name(title, process_name)
        return {
            "window_title": title,
            "process_name": process_name,
            "pid": pid,
            "project_name": project,
        }

    def update(self) -> dict[str, Any]:
        """Poll foreground state and publish event if changed."""
        info = self.get_foreground_info()
        now = self._clock()
        changed = False

        with self._lock:
            if (info["window_title"] != self._current_context["window_title"]
                    or info["process_name"] != self._current_context["process_name"]
                    or info["pid"] != self._current_context["pid"]):
                changed = True
                self._current_context = {
                    **info,
                    "changed_at": now,
                }
                snapshot = dict(self._current_context)

        if changed:
            bus = self._get_bus()
            if bus:
                try:
                    bus.publish("workspace.changed", **snapshot)
                except Exception as e:
                    logger.debug("Failed to publish workspace.changed: %s", e)

            # Optionally sync with session_activity for owner context if in an IDE
            if info["project_name"]:
                try:
                    from core.session_activity import activity
                    # Contextual session activity allows max 220 chars without paths
                    summary = f"Sajan is working on {info['project_name'][:60]}."
                    activity.set("project", summary, seconds=1800)
                except Exception:
                    pass

        with self._lock:
            return dict(self._current_context)

    def snapshot(self) -> dict[str, Any]:
        """Return the current workspace context snapshot."""
        with self._lock:
            ctx = dict(self._current_context)
            if ctx["changed_at"]:
                ctx["age_seconds"] = round(max(0.0, self._clock() - ctx["changed_at"]))
            else:
                ctx["age_seconds"] = 0
            return ctx

    def start_polling(self) -> None:
        """Start background polling thread."""
        with self._lock:
            if self._running:
                return
            self._running = True
            self._thread = threading.Thread(target=self._poll_loop, daemon=True, name="workspace-tracker")
            self._thread.start()

    def stop_polling(self) -> None:
        """Stop background polling thread."""
        with self._lock:
            self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

    def _poll_loop(self) -> None:
        while True:
            with self._lock:
                if not self._running:
                    break
            try:
                self.update()
            except Exception as e:
                logger.debug("WorkspaceTracker poll error: %s", e)
            time.sleep(self._poll_interval)


tracker = WorkspaceTracker()
