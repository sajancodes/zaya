"""Toolsmith Action — Dynamic Tool Synthesis & Runtime Plugin Compiler.
Created and developed by Sajan Rai for Zaya.
"""
from __future__ import annotations

import json
from typing import Any, Dict

from core.toolsmith_engine import get_toolsmith_engine


def handle_toolsmith(
    action: str = "list",
    name: str = "",
    code: str = "",
    description: str = "",
    test_args_json: str = "",
) -> str:
    """Manage dynamic tool synthesis and live action compilation."""
    engine = get_toolsmith_engine()

    if action == "list":
        tools = engine.list_tools()
        return json.dumps({"status": "success", "count": len(tools), "tools": tools})

    elif action == "synthesize":
        if not name or not code:
            return "Error: name and code are required to synthesize a new tool."

        test_args = json.loads(test_args_json) if test_args_json else None
        ok, msg, meta = engine.synthesize_tool(
            name=name,
            code=code,
            description=description,
            test_args=test_args,
        )
        if not ok:
            return json.dumps({"status": "failed", "error": msg})

        return json.dumps({
            "status": "success",
            "message": msg,
            "tool": meta.to_dict() if meta else {},
        })

    elif action == "remove":
        if not name:
            return "Error: name is required to remove a synthesized tool."
        ok = engine.remove_tool(name)
        return json.dumps({"status": "success" if ok else "failed", "removed": ok})

    elif action == "inspect":
        if not name:
            return "Error: name is required to inspect a tool."
        meta = engine.get_tool(name)
        if not meta:
            return f"Error: Tool '{name}' not found."
        return json.dumps({"status": "success", "tool": meta.to_dict()})

    return f"Unknown toolsmith action: '{action}'."


TOOL = {
    "name": "toolsmith",
    "description": (
        "Synthesize, compile, and dynamically register new capabilities into Zaya on the fly. "
        "Allows creating custom actions with full schema, AST security audit, and live execution."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["synthesize", "list", "remove", "inspect"],
                "description": "Toolsmith operation.",
            },
            "name": {
                "type": "STRING",
                "description": "Unique alphanumeric identifier for the tool (e.g. 'ip_geolocation_lookup').",
            },
            "code": {
                "type": "STRING",
                "description": "Full Python source code defining 'TOOL = {...}' and the handler function.",
            },
            "description": {
                "type": "STRING",
                "description": "High-level summary of what the synthesized tool does.",
            },
            "test_args_json": {
                "type": "STRING",
                "description": "JSON arguments to pass during the dry-run test.",
            },
        },
        "required": ["action"],
    },
    "handler": handle_toolsmith,
}
