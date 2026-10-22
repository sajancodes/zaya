"""Three-tier selected text extraction:
1. Windows UI Automation (UIA) TextPattern on focused element.
2. Non-destructive Clipboard Copy & Restore (Ctrl+C, read, restore original).
3. Screen OCR of the selected bounding box via native Windows.Media.Ocr.
"""
from __future__ import annotations

import sys
import time
from typing import Optional

from .context import SelectionContext, get_selection_manager


def _extract_via_uia() -> str:
    """Attempts to retrieve selected text from the focused UI element using UI Automation."""
    if sys.platform != "win32":
        return ""
    try:
        import comtypes.client
        uia_mod = comtypes.client.GetModule("UIAutomationCore.dll")
        uia = comtypes.client.CreateObject(uia_mod.CUIAutomation)
        focused = uia.GetFocusedElement()
        if not focused:
            return ""
        # 10014 = UIA_TextPatternId
        raw_pattern = focused.GetCurrentPattern(10014)
        if not raw_pattern:
            return ""
        text_pattern = raw_pattern.QueryInterface(uia_mod.IUIAutomationTextPattern)
        selection = text_pattern.GetSelection()
        if not selection or selection.Length == 0:
            return ""
        text_range = selection.GetElement(0)
        # -1 = retrieve entire range text
        text = text_range.GetText(-1)
        if text and text.strip():
            return text.strip()
    except Exception:
        pass
    return ""


def _extract_via_clipboard() -> str:
    """Non-destructive clipboard copy: saves clipboard, sends Ctrl+C, reads, restores original."""
    if sys.platform != "win32":
        return ""
    try:
        import pyperclip
        from actions.ghost_keyboard import send_hotkey

        saved_clipboard = ""
        try:
            saved_clipboard = pyperclip.paste()
        except Exception:
            saved_clipboard = ""

        # Send Ctrl+C into foreground target
        send_hotkey("ctrl+c")
        time.sleep(0.08)

        copied = ""
        try:
            copied = pyperclip.paste()
        except Exception:
            copied = ""

        # Immediately restore original clipboard content
        try:
            pyperclip.copy(saved_clipboard)
        except Exception:
            pass

        if copied and copied.strip() and copied != saved_clipboard:
            return copied.strip()
        # Even if copied == saved_clipboard, if text was selected and identical, it might still be valid
        if copied and copied.strip():
            return copied.strip()
    except Exception:
        pass
    return ""


def _extract_via_ocr(context: Optional[SelectionContext] = None) -> str:
    """OCR fallback over the selection bounding box."""
    if not context or context.width < 10 or context.height < 10:
        return ""
    try:
        from actions.screen_peeler import extract_text_from_region
        min_x, min_y, max_x, max_y = context.rect
        text = extract_text_from_region([min_x, min_y, max_x, max_y])
        if text and text.strip():
            return text.strip()
    except Exception:
        pass
    return ""


def get_selected_text(context: Optional[SelectionContext] = None) -> str:
    """Extracts text using UIA -> Clipboard -> OCR fallback chain."""
    if context is None:
        context = get_selection_manager().get_selection()

    if context and context.cached_text:
        return context.cached_text

    # Tier 1: Windows UI Automation
    text = _extract_via_uia()
    if text:
        if context:
            context.cached_text = text
        return text

    # Tier 2: Non-destructive Clipboard
    text = _extract_via_clipboard()
    if text:
        if context:
            context.cached_text = text
        return text

    # Tier 3: OCR of bounding box
    if context:
        text = _extract_via_ocr(context)
        if text:
            context.cached_text = text
            return text

    return ""
