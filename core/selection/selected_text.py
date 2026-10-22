"""Three-tier selected text extraction:
1. Windows UI Automation (UIA) TextPattern on focused element.
2. Safe Non-destructive Clipboard Copy & Restore with sentinel validation.
3. Screen OCR of the selected bounding box via native Windows.Media.Ocr.
"""
from __future__ import annotations

import sys
import time
import uuid
from typing import List, Optional, Tuple

from .context import SelectionContext, get_selection_manager


def _snapshot_windows_clipboard() -> List[Tuple[int, bytes]]:
    """Captures all currently available clipboard formats and their raw bytes on Windows."""
    if sys.platform != "win32":
        return []
    formats: List[Tuple[int, bytes]] = []
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        user32.GetClipboardData.restype = wintypes.HANDLE
        user32.GetClipboardData.argtypes = [wintypes.UINT]
        kernel32.GlobalLock.restype = ctypes.c_void_p
        kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
        kernel32.GlobalUnlock.restype = wintypes.BOOL
        kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
        kernel32.GlobalSize.restype = ctypes.c_size_t
        kernel32.GlobalSize.argtypes = [wintypes.HGLOBAL]

        if not user32.OpenClipboard(None):
            return []
        try:
            fmt = user32.EnumClipboardFormats(0)
            while fmt != 0:
                h_data = user32.GetClipboardData(fmt)
                if h_data:
                    size = kernel32.GlobalSize(h_data)
                    # Limit capture to 10MB per format to avoid freezing on massive dumps
                    if 0 < size < 10 * 1024 * 1024:
                        ptr = kernel32.GlobalLock(h_data)
                        if ptr:
                            try:
                                data = ctypes.string_at(ptr, size)
                                formats.append((fmt, data))
                            finally:
                                kernel32.GlobalUnlock(h_data)
                fmt = user32.EnumClipboardFormats(fmt)
        finally:
            user32.CloseClipboard()
    except Exception:
        pass
    return formats


def _restore_windows_clipboard(formats: List[Tuple[int, bytes]]) -> bool:
    """Restores full captured clipboard formats on Windows."""
    if sys.platform != "win32" or not formats:
        return False
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        user32.SetClipboardData.restype = wintypes.HANDLE
        user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
        kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
        kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
        kernel32.GlobalLock.restype = ctypes.c_void_p
        kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
        kernel32.GlobalUnlock.restype = wintypes.BOOL
        kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]

        if not user32.OpenClipboard(None):
            return False
        try:
            user32.EmptyClipboard()
            for fmt, data in formats:
                # 0x0042 = GHND (GMEM_MOVEABLE | GMEM_ZEROINIT)
                h_mem = kernel32.GlobalAlloc(0x0042, len(data))
                if h_mem:
                    ptr = kernel32.GlobalLock(h_mem)
                    if ptr:
                        ctypes.memmove(ptr, data, len(data))
                        kernel32.GlobalUnlock(h_mem)
                        user32.SetClipboardData(fmt, h_mem)
            return True
        finally:
            user32.CloseClipboard()
    except Exception:
        return False


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
    """Safe Non-destructive clipboard copy with sentinel verification & full format restoration."""
    if sys.platform != "win32":
        return ""
    try:
        import pyperclip
        from actions.ghost_keyboard import send_hotkey

        # 1. Full snapshot of original clipboard
        snapshot = _snapshot_windows_clipboard()
        original_text = ""
        try:
            original_text = pyperclip.paste()
        except Exception:
            pass

        # 2. Inject unique sentinel so we can strictly detect whether Ctrl+C produced new content
        sentinel = f"__ZAYA_CLIP_SENTINEL_{uuid.uuid4().hex}__"
        try:
            pyperclip.copy(sentinel)
        except Exception:
            pass

        # 3. Simulate Ctrl+C in active foreground window
        send_hotkey("ctrl+c")

        # 4. Poll up to 180ms for the clipboard content to update
        copied = ""
        deadline = time.monotonic() + 0.18
        while time.monotonic() < deadline:
            time.sleep(0.02)
            try:
                curr = pyperclip.paste()
                if curr != sentinel:
                    copied = curr
                    break
            except Exception:
                pass

        # 5. Restore the original clipboard faithfully
        restored = False
        if snapshot:
            restored = _restore_windows_clipboard(snapshot)
        if not restored and original_text:
            try:
                pyperclip.copy(original_text)
            except Exception:
                pass

        # 6. If clipboard remained sentinel, copy failed (no selectable text in target)
        if not copied or copied == sentinel:
            return ""

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


def get_selected_text(
    context: Optional[SelectionContext] = None,
    allow_stale: bool = False,
) -> str:
    """Extracts text using UIA -> Clipboard (Sentinel-guarded) -> OCR fallback chain."""
    if context is None:
        context = get_selection_manager().get_selection(allow_stale=allow_stale)

    if context and context.cached_text:
        return context.cached_text

    # Tier 1: Windows UI Automation from focused element
    text = _extract_via_uia()
    if text:
        if context:
            context.cached_text = text
        return text

    # Tier 2: Non-destructive Clipboard with sentinel verification
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
