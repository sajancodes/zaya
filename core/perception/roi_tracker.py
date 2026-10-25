import ctypes
import os
from ctypes import wintypes


def foreground():
    """Small Win32 metadata query; never reads another application's document."""
    if os.name != 'nt':
        return '', '', (), False
    user = ctypes.windll.user32
    user.GetForegroundWindow.restype = wintypes.HWND
    user.GetWindowTextW.argtypes = (wintypes.HWND,wintypes.LPWSTR,ctypes.c_int)
    user.GetClassNameW.argtypes = (wintypes.HWND,wintypes.LPWSTR,ctypes.c_int)
    user.GetWindowRect.argtypes = (wintypes.HWND,ctypes.POINTER(wintypes.RECT))
    hwnd = user.GetForegroundWindow()
    title, kind = ctypes.create_unicode_buffer(512), ctypes.create_unicode_buffer(128)
    user.GetWindowTextW(hwnd, title, 512)
    user.GetClassNameW(hwnd, kind, 128)
    rect = wintypes.RECT()
    user.GetWindowRect(hwnd, ctypes.byref(rect))
    pid=wintypes.DWORD()
    user.GetWindowThreadProcessId.argtypes=(wintypes.HWND,ctypes.POINTER(wintypes.DWORD))
    user.GetWindowThreadProcessId(hwnd,ctypes.byref(pid))
    app=kind.value
    try:
        import psutil
        app=psutil.Process(pid.value).name()
    except Exception:
        pass
    return app, title.value, (rect.left, rect.top, rect.right, rect.bottom), kind.value == '#32770'


def cursor_region(radius=160):
    if os.name != 'nt':
        return ()
    point = wintypes.POINT()
    if not ctypes.windll.user32.GetCursorPos(ctypes.byref(point)):
        return ()
    return (point.x - radius, point.y - radius, point.x + radius, point.y + radius)


def resolve_region(source, state=None):
    if source == 'cursor':
        return list(cursor_region()) or None
    if source == 'active_window':
        return list(foreground()[2]) or None
    if source == 'tracked_roi' and state and (state.tracked_region or state.changed_regions):
        x, y, w, h = state.tracked_region or state.changed_regions[0]
        return [x, y, x + w, y + h]
    if source == 'full_monitor':
        return None
    raise ValueError('No region is available for this source.')
