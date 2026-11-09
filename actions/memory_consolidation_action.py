"""Memory Consolidation Action — Autonomous Dream Cycle Engine.
Created and developed by Sajan Rai for Zaya.
"""
from __future__ import annotations

import json
from typing import Any, Dict

from core.memory_consolidation import get_memory_consolidation_engine


def handle_memory_consolidation(
    action: str = "consolidate",
    dry_run: bool = False,
) -> str:
    """Execute or inspect memory consolidation and dream cycle passes."""
    engine = get_memory_consolidation_engine()

    if action == "consolidate":
        report = engine.consolidate(dry_run=dry_run)
        return json.dumps({
            "status": "success",
            "report": report.to_dict(),
        })

    elif action == "last_report":
        report = engine.get_last_report()
        if not report:
            return json.dumps({"status": "success", "message": "No consolidation passes executed yet."})
        return json.dumps({"status": "success", "report": report.to_dict()})

    return f"Unknown memory consolidation action: '{action}'."


TOOL = {
    "name": "memory_consolidation",
    "description": (
        "Run an autonomous memory consolidation dream pass. "
        "Prunes ephemeral noise, resolves historical contradictions, and synthesizes durable macro-insights."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["consolidate", "last_report"],
                "description": "Consolidation action.",
            },
            "dry_run": {
                "type": "BOOLEAN",
                "description": "If true, simulates the consolidation pass without modifying memory storage.",
            },
        },
        "required": ["action"],
    },
    "handler": handle_memory_consolidation,
}
