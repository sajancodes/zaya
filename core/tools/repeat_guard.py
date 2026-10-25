"""Reuse a proven tool result instead of executing the same action twice.

The guard is intentionally narrow: it only suppresses an *identical* tool call
inside the same owner scope. Interactive operations that are meaningful to
repeat (a scroll step, a held key, a volume nudge) are declared repeatable and
always pass through.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any, Mapping

from core.tool_result import ToolResult


# Tools whose exact repetition is part of normal use. Everything else defaults
# to once per owner scope: a model repeating itself must not launch, send,
# delete or install twice.
_REPEATABLE_TOOLS = {
    "computer_control",
    "computer_settings",
    "media_controller",
    "video_player",
    "scroll",
    "terminal_exec",
}

_REPEATABLE_ACTIONS = {
    "scroll", "press_key", "type_text", "write_on_screen", "type", "write",
    "volume", "volume_up", "volume_down", "mute", "unmute", "next", "previous",
    "play", "pause", "seek", "move", "drag", "click", "double_click", "right_click",
}


def _action_of(arguments: Mapping[str, Any] | None) -> str:
    if not isinstance(arguments, Mapping):
        return ""
    return str(arguments.get("action") or arguments.get("command") or "").strip().lower()


def repetition_policy(tool: str, arguments: Mapping[str, Any] | None = None) -> str:
    """Return ``"repeatable"`` or ``"once"`` for this exact operation."""
    name = str(tool or "").strip().lower()
    action = _action_of(arguments)
    if name in {"computer_control", "computer_settings"} and action in _REPEATABLE_ACTIONS:
        return "repeatable"
    if name in {"media_controller", "video_player"}:
        return "repeatable"
    if name in {"scroll", "press_key", "type_text"}:
        return "repeatable"
    if name in _REPEATABLE_TOOLS and action in _REPEATABLE_ACTIONS:
        return "repeatable"
    return "once"


@dataclass
class _Entry:
    result: ToolResult
    created_at: float


class RepeatGuard:
    """Bounded, thread-safe memory of successful non-repeatable calls."""

    def __init__(self, ttl_sec: float = 900.0, max_entries: int = 2048, clock=time.monotonic):
        self.ttl_sec = max(1.0, float(ttl_sec))
        self.max_entries = max(16, int(max_entries))
        self.clock = clock
        self._lock = threading.RLock()
        self._entries: dict[str, _Entry] = {}

    def _prune(self) -> None:
        now = self.clock()
        expired = [key for key, entry in self._entries.items() if now - entry.created_at > self.ttl_sec]
        for key in expired:
            self._entries.pop(key, None)
        if len(self._entries) > self.max_entries:
            oldest = sorted(self._entries.items(), key=lambda item: item[1].created_at)
            for key, _ in oldest[: len(self._entries) - self.max_entries]:
                self._entries.pop(key, None)

    def reuse(self, request_key: str, tool: str, arguments: Mapping[str, Any] | None = None) -> ToolResult | None:
        if not request_key or repetition_policy(tool, arguments) == "repeatable":
            return None
        with self._lock:
            self._prune()
            entry = self._entries.get(request_key)
            return entry.result if entry is not None else None

    def remember(self, request_key: str, tool: str, result: ToolResult,
                 arguments: Mapping[str, Any] | None = None) -> None:
        if (not request_key or result.status != "success"
                or repetition_policy(tool, arguments) == "repeatable"):
            return
        with self._lock:
            self._prune()
            self._entries[request_key] = _Entry(result, self.clock())
