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


from ctypes import wintypes


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [('wVk', wintypes.WORD), ('wScan', wintypes.WORD),
                ('dwFlags', wintypes.DWORD), ('time', wintypes.DWORD), ('dwExtraInfo', ctypes.c_size_t)]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [('dx', wintypes.LONG), ('dy', wintypes.LONG), ('mouseData', wintypes.DWORD),
                ('dwFlags', wintypes.DWORD), ('time', wintypes.DWORD), ('dwExtraInfo', ctypes.c_size_t)]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [('uMsg', wintypes.DWORD), ('wParamL', wintypes.WORD), ('wParamH', wintypes.WORD)]


class _INPUT_UNION(ctypes.Union):
    _fields_ = [('ki', KEYBDINPUT), ('mi', MOUSEINPUT), ('hi', HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ('data',)
    _fields_ = [('type', wintypes.DWORD), ('data', _INPUT_UNION)]


VK_CODES.update({'delete': 0x2E, 'left': 0x25, 'up': 0x26, 'right': 0x27,
                 'down': 0x28, 'home': 0x24, 'end': 0x23, 'pageup': 0x21, 'pagedown': 0x22})
VK_CODES.update({f'f{i}': 0x6F + i for i in range(1, 25)})


def _send_input(vk=0, scan=0, flags=0) -> bool:
    if sys.platform != 'win32':
        return False
    event = INPUT(type=1, ki=KEYBDINPUT(vk, scan, flags, 0, 0))
    send = ctypes.windll.user32.SendInput
    send.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
    send.restype = wintypes.UINT
    return send(1, ctypes.byref(event), ctypes.sizeof(INPUT)) == 1


def _press_key_code(vk: int) -> bool:
    return _send_input(vk=vk)


def _release_key_code(vk: int) -> bool:
    return _send_input(vk=vk, flags=KEYEVENTF_KEYUP)


def send_hotkey(hotkey_str: str) -> bool:
    parts = [p.strip().lower() for p in hotkey_str.split('+')]
    keys = []
    for part in parts:
        vk = VK_CODES.get(part)
        if vk is None and len(part) == 1 and part.isascii() and part.isalnum():
            vk = ord(part.upper())
        if vk is None:
            return False
        keys.append(vk)
    pressed = []
    ok = True
    try:
        for vk in keys:
            if not _press_key_code(vk):
                ok = False
                break
            pressed.append(vk)
    except (OSError, AttributeError):
        ok = False
    finally:
        for vk in reversed(pressed):
            try:
                ok = _release_key_code(vk) and ok
            except (OSError, AttributeError):
                ok = False
    return bool(keys) and ok


def inject_text(text: str, delay_ms: int = 10) -> bool:
    if sys.platform != 'win32':
        return False
    try:
        raw = text.encode('utf-16-le', errors='surrogatepass')
        for offset in range(0, len(raw), 2):
            unit = int.from_bytes(raw[offset:offset + 2], 'little')
            down = _send_input(scan=unit, flags=KEYEVENTF_UNICODE)
            up = _send_input(scan=unit, flags=KEYEVENTF_UNICODE | KEYEVENTF_KEYUP)
            if not (down and up):
                return False
            if delay_ms > 0:
                time.sleep(min(delay_ms, 1000) / 1000)
        return True
    except (OSError, AttributeError, UnicodeError):
        return False


def ghost_keyboard(parameters: dict, **_kwargs) -> ToolResult:
    """Injects text or hotkeys into the active application."""
    require_owner()
    text = str(parameters.get("text") or "")
    hotkey = str(parameters.get("hotkey") or "").strip()
    delay_ms = max(0, min(1000, int(parameters.get("delay_ms", 10))))

    if hotkey:
        ok = send_hotkey(hotkey)
        if ok:
            return ToolResult("success", f"Injected hotkey: {hotkey}", data={"hotkey": hotkey}, side_effect=True)
        return ToolResult("failed", f"Could not parse hotkey: {hotkey}")

    if text:
        ok = inject_text(text, delay_ms=delay_ms)
        if ok:
            return ToolResult("success", f"Typed {len(text)} characters into active window.", data={"length": len(text)}, side_effect=True)
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
