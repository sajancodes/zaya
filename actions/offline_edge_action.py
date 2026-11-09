"""Offline Edge Router Action for Zaya.
Created and developed by Sajan Rai for Zaya.
"""
from __future__ import annotations

from core.offline_edge_engine import get_offline_edge_engine
from core.tool_result import ToolResult


def offline_edge_action(parameters: dict, **_kwargs) -> ToolResult:
    """Test or route an utterance through the offline edge engine."""
    utterance = parameters.get("utterance", "").strip()
    if not utterance:
        return ToolResult("failed", "Provide an utterance to evaluate.")

    engine = get_offline_edge_engine()
    handled, res, latency_ms = engine.execute_locally(utterance)

    if handled and res:
        return ToolResult(
            res.status,
            f"[Offline Edge: {latency_ms:.1f}ms] {res.summary}",
            data={"handled_locally": True, "latency_ms": round(latency_ms, 2), "inner_data": res.data},
        )

    return ToolResult(
        "partial",
        f"Utterance '{utterance}' requires cloud LLM reasoning (not a deterministic local command).",
        data={"handled_locally": False, "latency_ms": round(latency_ms, 2)},
    )


TOOL = {
    "name": "offline_edge_action",
    "description": "Zero-latency offline desktop router: evaluates whether an utterance can execute entirely locally in <5ms.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "utterance": {"type": "STRING", "description": "User voice or text command to evaluate locally."},
        },
        "required": ["utterance"],
    },
    "handler": offline_edge_action,
}
