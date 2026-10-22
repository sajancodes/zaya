"""Zaya Read Selected Text Tool.
Created and developed by Sajan Rai for Zaya.

Retrieves and speaks text selected via two-finger hand gestures or OS selection.
Uses a 3-tier retrieval pipeline:
1. Windows UI Automation TextPattern on focused element.
2. Non-destructive Clipboard copy & restore (Ctrl+C, read, restore original).
3. Native Windows.Media.Ocr on the selection bounding box.

Directly speaks via TTS without unnecessary LLM reasoning loops.
"""
from __future__ import annotations

import sys
import threading
from core.execution_policy import require_owner
from core.tool_result import ToolResult
from core.selection.selected_text import get_selected_text
from core.selection.context import get_selection_manager


def _speak_text(text: str, speak_fn=None):
    """Speaks text immediately via caller callback or native SAPI."""
    if speak_fn and callable(speak_fn):
        try:
            speak_fn(text)
            return
        except Exception:
            pass

    if sys.platform == "win32":
        try:
            import win32com.client

            def _spk():
                try:
                    voice = win32com.client.Dispatch("SAPI.SpVoice")
                    voice.Speak(text)
                except Exception:
                    pass

            threading.Thread(target=_spk, daemon=True).start()
        except Exception:
            pass


def read_selected_text(parameters: dict, **kwargs) -> ToolResult:
    """Extracts and reads the currently selected text out loud."""
    require_owner()

    context = get_selection_manager().get_selection()
    text = get_selected_text(context)

    if not text or not text.strip():
        return ToolResult(
            "failed",
            "No text is currently selected. Use a two-finger gesture or mouse to drag and select text first.",
            data={"text": ""},
        )

    clean_text = text.strip()
    _speak_text(clean_text, kwargs.get("speak"))

    preview = clean_text[:120] + ("..." if len(clean_text) > 120 else "")
    return ToolResult(
        "success",
        f"Reading selected text: {preview}",
        data={
            "text": clean_text,
            "length": len(clean_text),
            "target_app": context.target_app if context else "Active Window",
            "speak": clean_text,
        },
        side_effect=True,
    )


TOOL = {
    "name": "read_selected_text",
    "description": (
        "Reads the currently selected text on screen out loud. "
        "Use when the user says 'Zaya, read this text', 'read the selected text', 'read this', or 'what does this text say?'. "
        "Retrieves text from two-finger hand selection or active window selection via UI Automation, clipboard, or OCR, "
        "and speaks it directly via TTS."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "prompt": {
                "type": "STRING",
                "description": "Optional user request context, e.g. 'read this text'."
            }
        }
    },
    "handler": read_selected_text,
}
