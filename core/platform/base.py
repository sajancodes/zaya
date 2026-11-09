"""Abstract Base Adapter for Cross-Platform Desktop OS Operations.
Created and developed by Sajan Rai for Zaya.

Defines unified polymorphic interfaces for notifications, process trees, screen capture,
window inspection, and desktop interaction across Windows, macOS, and Linux (X11 & Wayland).
"""
from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class WindowInfo:
    id: str
    title: str
    process_name: str
    pid: Optional[int] = None
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0
    is_visible: bool = True


@dataclass
class PowerStatus:
    battery_percent: Optional[int] = None
    power_plugged: Optional[bool] = None
    power_plan: str = "Unknown"


class PlatformAdapter(abc.ABC):
    """Abstract interface isolating OS-specific desktop interactions."""

    @property
    @abc.abstractmethod
    def platform_name(self) -> str:
        """Return canonical platform name: 'windows', 'macos', 'linux'."""
        pass

    @abc.abstractmethod
    def show_notification(self, title: str, message: str) -> bool:
        """Display an OS-native desktop notification popup."""
        pass

    @abc.abstractmethod
    def list_windows(self) -> List[WindowInfo]:
        """List active desktop top-level windows."""
        pass

    @abc.abstractmethod
    def capture_screen(self, region: Optional[List[int]] = None) -> Optional[bytes]:
        """Capture display region [x1, y1, x2, y2] or full desktop as PNG bytes."""
        pass

    @abc.abstractmethod
    def terminate_process_tree(self, pid: int, timeout_sec: float = 3.0) -> bool:
        """Safely terminate a parent process and all child descendants."""
        pass

    @abc.abstractmethod
    def get_power_status(self) -> PowerStatus:
        """Inspect battery percentage and AC power connectivity."""
        pass

    def is_wayland(self) -> bool:
        """True if running in a Linux Wayland session."""
        return False
