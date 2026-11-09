"""Cross-platform desktop OS abstraction package for Zaya."""
from core.platform.base import PlatformAdapter, PowerStatus, WindowInfo
from core.platform.factory import get_platform_adapter

__all__ = ["PlatformAdapter", "PowerStatus", "WindowInfo", "get_platform_adapter"]
