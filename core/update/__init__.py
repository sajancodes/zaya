"""Desktop update module for Zaya."""
from .desktop_updater import (
    DesktopUpdater,
    DesktopUpdateManifest,
    UpdateStatus,
    verify_authenticode_signature,
    desktop_updater,
)
from .update_ui import UpdateDialog

__all__ = [
    "desktop_updater",
    "DesktopUpdater",
    "DesktopUpdateManifest",
    "UpdateStatus",
    "UpdateDialog",
    "verify_authenticode_signature",
]
