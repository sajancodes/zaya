"""Tests for Cross-Platform Desktop OS Adapters.
Created and developed by Sajan Rai for Zaya.
"""
from __future__ import annotations

import sys
from unittest.mock import patch, MagicMock

import pytest

from core.platform.base import PlatformAdapter, PowerStatus, WindowInfo
from core.platform.factory import get_platform_adapter
from core.platform.windows import WindowsAdapter
from core.platform.macos import MacOSAdapter
from core.platform.linux import LinuxAdapter


class TestPlatformAdapters:
    def test_factory_returns_correct_adapter_for_host(self):
        adapter = get_platform_adapter()
        assert isinstance(adapter, PlatformAdapter)
        if sys.platform == "win32":
            assert adapter.platform_name == "windows"
            assert isinstance(adapter, WindowsAdapter)
        elif sys.platform == "darwin":
            assert adapter.platform_name == "macos"
            assert isinstance(adapter, MacOSAdapter)
        else:
            assert adapter.platform_name == "linux"
            assert isinstance(adapter, LinuxAdapter)

    def test_windows_adapter_power_status(self):
        win = WindowsAdapter()
        status = win.get_power_status()
        assert isinstance(status, PowerStatus)

    def test_windows_adapter_screen_capture(self):
        win = WindowsAdapter()
        # Full or tiny region
        png = win.capture_screen(region=[0, 0, 100, 100])
        # On headless it might return None, on Windows with display it returns bytes
        if png is not None:
            assert isinstance(png, bytes)
            assert png.startswith(b"\x89PNG")

    def test_macos_adapter_notification_command(self):
        mac = MacOSAdapter()
        assert mac.platform_name == "macos"
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            ok = mac.show_notification("Zaya", "Test notice")
            assert ok is True
            assert "osascript" in mock_run.call_args[0][0]

    def test_linux_adapter_wayland_detection(self):
        linux = LinuxAdapter()
        assert linux.platform_name == "linux"

        with patch.dict("os.environ", {"XDG_SESSION_TYPE": "wayland"}):
            assert linux.is_wayland() is True
            # Window listing should gracefully return empty on Wayland due to sandbox
            assert linux.list_windows() == []

        with patch.dict("os.environ", {"XDG_SESSION_TYPE": "x11", "WAYLAND_DISPLAY": ""}):
            assert linux.is_wayland() is False

    def test_linux_adapter_notification(self):
        linux = LinuxAdapter()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            ok = linux.show_notification("Title", "Message")
            assert ok is True
            assert "notify-send" in mock_run.call_args[0][0]
