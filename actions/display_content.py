"""Zaya's native display tool for showing, updating, appending, and clearing visual content.
Created and developed by Sajan Rai for Zaya.
"""
from __future__ import annotations

from core.display_service import get_display_service
from core.execution_policy import require_owner
from core.tool_result import ToolResult


def display_content(parameters: dict, player=None, **_kwargs) -> ToolResult:
    """First-class tool for controlling Zaya's visual display panel/window."""
    require_owner()
    service = get_display_service(player)
    action = str(parameters.get("action", "show")).lower().strip()
    title = parameters.get("title")
    content = parameters.get("content")
    fmt = parameters.get("format", "text")

    if action == "show":
        return service.show_text(title=title or "DISPLAY", content=content, format=fmt)
    elif action == "update":
        return service.update_text(content=content, title=title, format=fmt)
    elif action == "append":
        return service.append_text(content=content)
    elif action == "clear":
        return service.clear()
    elif action == "close":
        return service.close()
    elif action == "status":
        return service.status()
    else:
        return ToolResult(
            status="failed",
            summary=f"Unknown display action: {action}",
            data={"displayed": False, "action": action},
        )


TOOL = {
    "name": "display_content",
    "description": (
        "Use this tool whenever the owner asks to show, display, put, write, render, list, or present textual information "
        "on Zaya's display, screen, result window, content panel, or visual panel.\n"
        "Displays the requested information directly inside Zaya's UI.\n"
        "Use it for: lists, comparisons, research, code, explanations, status information, branch differences, reports, "
        "search results, and textual data.\n"
        "Supports actions: 'show' (render content), 'update' (replace displayed content), 'append' (add text to current display), "
        "'clear' (empty the display), 'close' (hide the display panel/window), and 'status' (inspect active display state).\n"
        "Do NOT create an Excel, Word, PDF, text file, or other document merely because the owner asked to display information. "
        "A file should only be created when the owner explicitly asks to save, export, create, download, write to disk, "
        "make a spreadsheet, or make a document."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["show", "update", "append", "clear", "close", "status"],
                "description": "Action to perform: 'show' to display text/list/code, 'update' to replace, 'append' to add to existing, 'clear' to empty text, 'close' to dismiss/hide panel, 'status' to check state.",
            },
            "title": {
                "type": "STRING",
                "description": "Header title for the displayed content (e.g. 'Branch Comparison: main vs iris', 'Research Results', 'Summary List').",
            },
            "content": {
                "type": "STRING",
                "description": "The textual content, list, markdown, code, or comparison to display.",
            },
            "format": {
                "type": "STRING",
                "enum": ["text", "markdown", "code", "list"],
                "description": "Format to render: 'text', 'markdown', 'code', or 'list'. Default is 'text'.",
            },
        },
        "required": ["action"],
    },
    "handler": display_content,
}
