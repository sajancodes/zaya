"""Conversational Dialog Coordinator Action for Zaya.
Created and developed by Sajan Rai.

Coordinates conversational state transitions, contextual pronoun resolution,
slot filling, and nested side-query resumption.
"""
from __future__ import annotations

from typing import Any

from core.dialog_coordinator import get_dialog_coordinator
from core.execution_policy import require_owner
from core.tool_result import ToolResult


def dialog_action(parameters: dict[str, Any], **_kwargs) -> ToolResult:
    """Process utterances or manage dialog state machine."""
    require_owner()
    action = str(parameters.get("action", "status")).lower().strip()
    coord = get_dialog_coordinator()

    if action == "status":
        ctx = coord.get_context()
        summary = f"Dialog state: {ctx.state}. Active entity: {ctx.active_entity or 'None'}."
        return ToolResult("success", summary, ctx.__dict__)

    elif action == "process":
        text = str(parameters.get("text", "")).strip()
        if not text:
            return ToolResult("failed", "Parameter 'text' is required for processing.", {})

        res = coord.process_turn(text)
        summary = f"Resolved text: '{res.resolved_text}' [State: {res.state}, Intent: {res.intent}]."
        evidence = [{"source": "dialog_coordinator", "state": res.state, "intent": res.intent}]
        return ToolResult("success", summary, res.__dict__, evidence=evidence)

    elif action == "confirm_prompt":
        action_name = str(parameters.get("pending_action", "operation"))
        prompt = str(parameters.get("prompt", "Are you sure?"))
        coord.request_confirmation(action_name=action_name, parameters=parameters.get("params", {}), prompt=prompt)
        return ToolResult("success", f"Awaiting confirmation for '{action_name}'.", coord.get_context().__dict__)

    elif action == "reset":
        coord.reset()
        return ToolResult("success", "Dialog context reset to IDLE.", coord.get_context().__dict__)

    return ToolResult("failed", f"Unknown action '{action}'. Valid actions are 'status', 'process', 'confirm_prompt', 'reset'.", {})


TOOL = {
    "name": "dialog_coordinator",
    "description": (
        "Process utterances through the multi-turn dialog state machine. "
        "Performs contextual pronoun resolution ('it', 'that'), slot-filling transitions, "
        "and mixed-initiative confirmation states."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["status", "process", "confirm_prompt", "reset"],
                "description": "Dialog coordinator action: 'status' (default), 'process', 'confirm_prompt', 'reset'.",
            },
            "text": {
                "type": "STRING",
                "description": "Utterance text to resolve through context state machine (for 'process').",
            },
            "pending_action": {
                "type": "STRING",
                "description": "Action name to require confirmation for (for 'confirm_prompt').",
            },
            "prompt": {
                "type": "STRING",
                "description": "Confirmation question prompt presented to user.",
            },
            "params": {
                "type": "OBJECT",
                "description": "Pending parameters associated with confirmation request.",
            },
        },
        "required": [],
    },
    "handler": dialog_action,
}
