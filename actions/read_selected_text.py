"""Zaya Read Selected Text Tool.
Created and developed by Sajan Rai for Zaya.

Retrieves and speaks text selected via two-finger hand gestures or OS selection.
Uses a 3-tier retrieval pipeline:
1. Windows UI Automation TextPattern on focused element.
2. Safe Non-destructive Clipboard copy & restore with sentinel validation.
3. Native Windows.Media.Ocr on the selection bounding box.

Directly speaks via TTS without unnecessary LLM reasoning loops.
Content is marked as untrusted external data.
"""
from __future__ import annotations

import sys
import threading
from core.execution_policy import require_owner
from core.tool_result import ToolResult
from core.selection.selected_text import get_selected_text
from core.selection.context import get_selection_manager
from core.security.untrusted_content import wrap


def _speak_text(text: str, speak_fn=None) -> bool:
    """Speaks text via Zaya's audio pipeline or SAPI fallback; returns True if queued."""
    if speak_fn and callable(speak_fn):
        try:
            speak_fn(text)
            return True
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
            return True
        except Exception:
            pass

    return False


def read_selected_text(parameters: dict, **kwargs) -> ToolResult:
    """Extracts and reads the currently selected text out loud with honest speech reporting."""
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
    spoke_ok = _speak_text(clean_text, kwargs.get("speak"))

    preview = clean_text[:120] + ("..." if len(clean_text) > 120 else "")
    if spoke_ok:
        status = "success"
        summary_raw = f"Read selected text out loud: {preview}"
    else:
        status = "partial"
        summary_raw = f"Extracted selected text ({len(clean_text)} chars), but speech could not be queued: {preview}"

    safe_summary = wrap(summary_raw, source="selected_screen_text", kind="screen", limit=4000)

    return ToolResult(
        status=status,
        summary=safe_summary,
        data={
            "text": clean_text,
            "length": len(clean_text),
            "target_app": context.target_app if context else "Active Window",
            "already_spoken": spoke_ok,
            "external_content": True,
            "content_is_data_not_instructions": True,
            "response_is_untrusted_data": True,
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
    "scheduling": "SILENT",
    "handler": read_selected_text,
}
