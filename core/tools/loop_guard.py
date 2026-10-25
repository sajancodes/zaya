"""Bound a conversational tool loop without crashing the turn."""

from __future__ import annotations

import hashlib
import json
import threading
from collections import deque
from dataclasses import dataclass
from typing import Any, Mapping


class LoopLimitReached(RuntimeError):
    """Raised only when a caller explicitly chooses strict mode."""


@dataclass(frozen=True)
class LoopDecision:
    allowed: bool
    reason: str = ""
    call_number: int = 0
    repeated: int = 0


class LoopGuard:
    """Per-owner-scope call budget and repeated-cycle detector."""

    def __init__(self, max_calls: int = 16, max_same_tool: int = 6, max_repeated_cycles: int = 3):
        self.max_calls = max(1, int(max_calls))
        self.max_same_tool = max(1, int(max_same_tool))
        self.max_repeated_cycles = max(1, int(max_repeated_cycles))
        self._lock = threading.RLock()
        self._scopes: dict[str, dict[str, Any]] = {}
        self._order: deque[str] = deque()
        self._max_scopes = 512

    @staticmethod
    def signature(tool: str, arguments: Mapping[str, Any] | None) -> str:
        try:
            payload = json.dumps(dict(arguments or {}), sort_keys=True, separators=(",", ":"), default=str)
        except (TypeError, ValueError):
            payload = str(arguments)
        return hashlib.sha256(f"{tool}:{payload}".encode("utf-8", "replace")).hexdigest()

    def reset(self, scope: str) -> None:
        with self._lock:
            self._scopes.pop(str(scope or ""), None)

    def check(self, scope: str, tool: str, arguments: Mapping[str, Any] | None = None) -> LoopDecision:
        key = str(scope or "anonymous")
        signature = self.signature(tool, arguments)
        with self._lock:
            state = self._scopes.get(key)
            if state is None:
                state = {"calls": 0, "tools": {}, "signatures": deque(maxlen=32)}
                self._scopes[key] = state
                self._order.append(key)
                while len(self._order) > self._max_scopes:
                    self._scopes.pop(self._order.popleft(), None)
            state["calls"] += 1
            state["tools"][tool] = int(state["tools"].get(tool, 0)) + 1
            state["signatures"].append(signature)
            repeated = sum(1 for item in state["signatures"] if item == signature)
            if state["calls"] > self.max_calls:
                return LoopDecision(False, f"This turn reached its {self.max_calls}-call tool budget. Answer from the evidence already collected.", state["calls"], repeated)
            if state["tools"][tool] > self.max_same_tool:
                return LoopDecision(False, f"Tool '{tool}' was requested more than {self.max_same_tool} times this turn. Use the results already returned.", state["calls"], repeated)
            if repeated > self.max_repeated_cycles:
                return LoopDecision(False, "The same tool call repeated without new information. Use the earlier result instead of calling it again.", state["calls"], repeated)
            return LoopDecision(True, call_number=state["calls"], repeated=repeated)

    def strict_check(self, scope: str, tool: str, arguments: Mapping[str, Any] | None = None) -> None:
        decision = self.check(scope, tool, arguments)
        if not decision.allowed:
            raise LoopLimitReached(decision.reason)
