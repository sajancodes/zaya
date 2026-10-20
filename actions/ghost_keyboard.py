"""Phantom Ghost Keyboard: Inline typing injection overlay & keystroke synthesizer.
Created and developed by Sajan Rai for Zaya.

Simulates physical typing or keystrokes into any active Windows application or editor with high precision.
"""
from __future__ import annotations

import ctypes
import sys
import time
from typing import Optional

from core.execution_policy import require_owner
from core.tool_result import ToolResult

# Win32 Virtual Key Constants
VK_CODES = {
    "ctrl": 0x11,
    "control": 0x11,
    "alt": 0x12,
    "shift": 0x10,
    "space": 0x20,
    "enter": 0x0D,
    "tab": 0x09,
    "esc": 0x1B,
    "escape": 0x1B,
    "backspace": 0x08,
    "win": 0x5B,
    "windows": 0x5B,
    "c": 0x43,
    "v": 0x56,
    "x": 0x58,
    "i": 0x49,
    "a": 0x41,
}

KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004


def _press_key_code(vk: int) -> None:
    if sys.platform == "win32":
        try:
            ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
        except Exception:
            pass


def _release_key_code(vk: int) -> None:
    if sys.platform == "win32":
        try:
            ctypes.windll.user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
        except Exception:
            pass


def send_hotkey(hotkey_str: str) -> bool:
    """Simulates a hotkey combination like 'ctrl+alt+space' or 'ctrl+shift+i'."""
    parts = [p.strip().lower() for p in hotkey_str.split("+")]
    vk_list = []
    for p in parts:
        vk = VK_CODES.get(p)
        if vk is None and len(p) == 1:
            vk = ord(p.upper())
        if vk:
            vk_list.append(vk)

    if not vk_list:
        return False

    # Press down in order
    for vk in vk_list:
        _press_key_code(vk)
        time.sleep(0.01)

    # Release in reverse order
    for vk in reversed(vk_list):
        _release_key_code(vk)
        time.sleep(0.01)

    return True


def inject_text(text: str, delay_ms: int = 10) -> bool:
    """Types unicode characters into the active window using Win32 keybd_event."""
    if sys.platform != "win32":
        return False

    try:
        user32 = ctypes.windll.user32
        for ch in text:
            code = ord(ch)
            user32.keybd_event(0, code, KEYEVENTF_UNICODE, 0)
            user32.keybd_event(0, code, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, 0)
            if delay_ms > 0:
                time.sleep(delay_ms / 1000.0)
        return True
    except Exception:
        return False


def ghost_keyboard(parameters: dict, **_kwargs) -> ToolResult:
    """Injects text or hotkeys into the active application."""
    require_owner()
    text = str(parameters.get("text") or "")
    hotkey = str(parameters.get("hotkey") or "").strip()
    delay_ms = int(parameters.get("delay_ms") or 10)

    if hotkey:
        ok = send_hotkey(hotkey)
        if ok:
            return ToolResult("success", f"Injected hotkey: {hotkey}", data={"hotkey": hotkey})
        return ToolResult("failed", f"Could not parse hotkey: {hotkey}")

    if text:
        ok = inject_text(text, delay_ms=delay_ms)
        if ok:
            return ToolResult("success", f"Typed {len(text)} characters into active window.", data={"length": len(text)})
        return ToolResult("failed", "Ghost typing injection failed on this OS platform.")

    return ToolResult("failed", "No text or hotkey provided.")


TOOL = {
    "name": "ghost_keyboard",
    "description": "Ghost Keyboard: Inlines text or simulates keyboard hotkeys (like Ctrl+Alt+Space, Ctrl+V, Ctrl+Shift+I) directly into active applications and editors.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "text": {
                "type": "STRING",
                "description": "The exact string to type into the active window."
            },
            "hotkey": {
                "type": "STRING",
                "description": "Hotkey to press, e.g. 'ctrl+alt+space', 'ctrl+v', 'ctrl+shift+i'."
            },
            "delay_ms": {
                "type": "INTEGER",
                "description": "Delay between keystrokes in milliseconds (default: 10ms)."
            }
        }
    },
    "handler": ghost_keyboard
}
