"""Ambient Workspace Vision & Error Peeler Action for Zaya.
Created and developed by Sajan Rai.

Diagnoses compiler errors, runtime exceptions, and stack traces across Python, TypeScript,
Kotlin, Rust, and Go with automated fix suggestions and project awareness correlation.
"""
from __future__ import annotations

from typing import Any

from core.ambient_vision import get_error_peeler
from core.execution_policy import require_owner
from core.tool_result import ToolResult


def ambient_vision(parameters: dict[str, Any], **_kwargs) -> ToolResult:
    """Analyze compiler errors or terminal output for actionable diagnostics."""
    require_owner()
    action = str(parameters.get("action", "peel_error")).lower().strip()
    peeler = get_error_peeler()

    if action in {"peel_error", "diagnose"}:
        text = str(parameters.get("text", "")).strip()
        if not text:
            # Fallback to clipboard if available
            try:
                import pyperclip
                text = pyperclip.paste().strip()
            except Exception:
                text = ""

        if not text:
            return ToolResult(
                "failed",
                "Parameter 'text' was not provided and clipboard contains no text.",
                {},
            )

        project_name = str(parameters.get("project", "")).strip()
        diag = peeler.diagnose(text, project_name=project_name)

        evidence = [
            {
                "source": "ambient_vision",
                "language": f.get("language"),
                "error_type": f.get("error_type"),
                "file": f.get("file_path"),
            }
            for f in diag.get("findings", [])
        ]

        status = "success" if diag.get("has_errors") else "partial"
        return ToolResult(
            status=status,
            summary=diag.get("summary", ""),
            data=diag,
            evidence=evidence,
        )

    return ToolResult("failed", f"Unknown action '{action}'. Valid action is 'peel_error'.", {})


TOOL = {
    "name": "ambient_vision",
    "description": (
        "Diagnose terminal compiler errors, build failures, and exceptions across Python, "
        "TypeScript, Kotlin, Rust, and Go. Correlates errors with active project context "
        "and produces root cause analysis and immediate fix recommendations."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["peel_error", "diagnose"],
                "description": "Action to perform: 'peel_error' (default).",
            },
            "text": {
                "type": "STRING",
                "description": "Raw compiler output, terminal log, or stack trace to diagnose (falls back to clipboard if omitted).",
            },
            "project": {
                "type": "STRING",
                "description": "Optional target project name to correlate diagnostics with.",
            },
        },
        "required": [],
    },
    "handler": ambient_vision,
}
