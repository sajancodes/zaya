"""Live session tool registry, declarations, and schema compaction.

Provides tool declarations with schema compaction to minimize serialized schema characters
and latency on the Gemini Live API without losing structural parameter information.
"""
from __future__ import annotations

import copy
import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

INLINE_TOOL_DECLARATIONS = [
    {
        "name": "system_status",
        "description": "Returns real-time system metrics: CPU, RAM, GPU, CPU temperature, uptime, and process count.",
        "parameters": {"type": "OBJECT", "properties": {}},
    },
    {
        "name": "screen_process",
        "description": "Captures screen or webcam image for analysis when user asks what is on screen or to view camera.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "angle": {"type": "STRING", "description": "'screen' to capture display, 'camera' for webcam. Default: 'screen'"},
                "text": {"type": "STRING", "description": "The question or instruction about the captured image"},
            },
            "required": ["text"],
        },
    },
    {
        "name": "close_camera",
        "description": "Closes the live camera view shown on screen when requested.",
        "parameters": {"type": "OBJECT", "properties": {}, "required": []},
    },
    {
        "name": "manage_monitor",
        "description": "Add, remove, or list background monitoring topics checked daily for updates.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "add | remove | list"},
                "topic": {"type": "STRING", "description": "Topic to monitor or stop monitoring"},
            },
            "required": ["action"],
        },
    },
    {
        "name": "restart_zaya",
        "description": "Restart the Zaya assistant when the owner asks to restart Zaya, you, or the assistant. Closes the current app before launching its replacement. Does not restart Windows.",
        "parameters": {"type": "OBJECT", "properties": {}},
    },
    {
        "name": "shutdown_jarvis",
        "description": "Shuts down the assistant completely when user asks to end conversation, close, or stop.",
        "parameters": {"type": "OBJECT", "properties": {}},
    },
    {
        "name": "save_memory",
        "description": "Save an important personal fact about the user silently to long-term memory.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "category": {
                    "type": "STRING",
                    "description": "identity | preferences | projects | relationships | wishes | notes",
                },
                "key": {"type": "STRING", "description": "Short snake_case key (e.g. favorite_food, sister_name)"},
                "value": {"type": "STRING", "description": "Concise value in English"},
            },
            "required": ["category", "key", "value"],
        },
    },
    {
        "name": "recall_memory",
        "description": "Look up facts stored about user in long-term memory not shown in core prompt index.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {"type": "STRING", "description": "Keyword to search for, or empty to list all facts"},
            },
            "required": [],
        },
    },
    {
        "name": "undo",
        "description": "Reverse the last change made to the computer (file moved/written, volume/wifi setting).",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "undo (default) | list"},
            },
            "required": [],
        },
    },
]


def _compact_text(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def compact_tool_schema(decl: dict[str, Any], max_desc_len: int = 200, max_param_len: int = 140) -> dict[str, Any]:
    """Compact verbose prose and redundant examples in tool schemas while preserving names and types."""
    d = copy.deepcopy(decl)
    if "description" in d:
        desc = _compact_text(str(d["description"]))
        # Whitespace is redundant; behavioral constraints are not. Keep complete
        # sentences and all selection/evidence rules instead of slicing prose.
        d["description"] = desc

    params = d.get("parameters")
    if isinstance(params, dict):
        props = params.get("properties")
        if isinstance(props, dict):
            for p_name, p_val in props.items():
                if isinstance(p_val, dict) and "description" in p_val:
                    p_desc = _compact_text(str(p_val["description"]))
                    p_val["description"] = p_desc

    return d


def compact_tool_declarations(declarations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Apply schema compaction across a list of tool declarations."""
    return [compact_tool_schema(d) for d in declarations]
