"""Hybrid Offline Edge Engine and Zero-Latency Local Command Dispatcher for Zaya.
Created and developed by Sajan Rai for Zaya.

Parses deterministic OS and computer control intents locally, executing local tools
in <5ms with zero cloud network latency or API round-trip dependency.
"""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from core.tool_result import ToolResult

logger = logging.getLogger(__name__)


@dataclass
class LocalMatch:
    tool_name: str
    parameters: Dict[str, Any]
    intent_label: str
    confidence: float = 1.0


class OfflineEdgeEngine:
    """Classifies and executes deterministic desktop commands offline with zero network latency."""

    def __init__(self) -> None:
        self._rules: List[Tuple[re.Pattern, str, Callable[[re.Match], Dict[str, Any]]]] = []
        self._register_default_grammars()

    def _register_default_grammars(self) -> None:
        # 1. Volume & Audio Control
        self.register(
            r"^(?:please\s+)?(?:mute|silence)(?:\s+(?:the\s+)?volume|\s+(?:the\s+)?sound|\s+(?:the\s+)?audio)?$",
            "volume_control",
            lambda m: {"action": "mute"},
        )
        self.register(
            r"^(?:please\s+)?unmute(?:\s+(?:the\s+)?volume|\s+(?:the\s+)?sound)?$",
            "volume_control",
            lambda m: {"action": "unmute"},
        )
        self.register(
            r"^(?:please\s+)?set\s+(?:the\s+)?volume\s+(?:to\s+)?(\d{1,3})(?:%|\s*percent)?$",
            "volume_control",
            lambda m: {"action": "set", "level": int(m.group(1))},
        )

        # 2. Spatial Window Layouts
        self.register(
            r"^(?:please\s+)?(?:arrange|layout|set)\s+(?:windows\s+)?(?:in\s+)?(split|split_code|dev|dual|quad|focus)(?:\s+layout|\s+mode)?$",
            "spatial_layout",
            lambda m: {"action": "preset", "preset": "split_code" if m.group(1) in {"split", "dev"} else m.group(1)},
        )

        # 3. System Status & Telemetry
        self.register(
            r"^(?:what\s+is\s+my\s+|check\s+|show\s+)?(?:system\s+status|cpu\s+usage|memory\s+usage|ram\s+usage|pc\s+health)$",
            "system_status",
            lambda m: {"action": "check"},
        )
        self.register(
            r"^(?:what\s+is\s+my\s+|check\s+)?battery(?:\s+status|\s+level|\s+percentage)?$",
            "capability_registry",
            lambda m: {"action": "status"},
        )

        # 4. Screen Capture
        self.register(
            r"^(?:please\s+)?(?:take\s+(?:a\s+)?screenshot|capture\s+(?:the\s+)?screen|grab\s+screen)$",
            "screen_peeler",
            lambda m: {"source": "full_monitor"},
        )

        # 5. Monitor Mode Control
        self.register(
            r"^(?:please\s+)?(?:stop|cancel|halt)\s+(?:the\s+)?monitor(?:\s+mode)?$",
            "monitor_mode",
            lambda m: {"action": "stop"},
        )
        self.register(
            r"^(?:what\s+is\s+the\s+)?monitor(?:\s+mode)?\s+status$",
            "monitor_mode",
            lambda m: {"action": "status"},
        )

    def register(self, pattern: str, tool_name: str, param_extractor: Callable[[re.Match], Dict[str, Any]]) -> None:
        """Register a new offline regex intent."""
        compiled = re.compile(pattern, re.IGNORECASE)
        self._rules.append((compiled, tool_name, param_extractor))

    def match(self, utterance: str) -> Optional[LocalMatch]:
        """Match an utterance against local deterministic grammars."""
        clean = utterance.strip()
        for regex, tool, extractor in self._rules:
            m = regex.search(clean)
            if m:
                try:
                    params = extractor(m)
                    return LocalMatch(tool_name=tool, parameters=params, intent_label=tool)
                except Exception:
                    continue
        return None

    def execute_locally(self, utterance: str) -> Tuple[bool, Optional[ToolResult], float]:
        """Execute matching utterance directly via local action loader.

        Returns (handled_locally, tool_result, latency_ms).
        """
        t0 = time.monotonic()
        match = self.match(utterance)
        if not match:
            return False, None, (time.monotonic() - t0) * 1000.0

        from core.action_loader import execute_tool
        try:
            result = execute_tool(match.tool_name, match.parameters)
            latency_ms = (time.monotonic() - t0) * 1000.0
            logger.info("[OfflineEdgeEngine] Executed '%s' offline in %.2fms", match.tool_name, latency_ms)
            return True, result, latency_ms
        except Exception as e:
            latency_ms = (time.monotonic() - t0) * 1000.0
            return True, ToolResult("failed", f"Offline execution error: {e}"), latency_ms


# ── Global Singleton ─────────────────────────────────────────────────────────

_edge: Optional[OfflineEdgeEngine] = None


def get_offline_edge_engine() -> OfflineEdgeEngine:
    global _edge
    if _edge is None:
        _edge = OfflineEdgeEngine()
    return _edge
