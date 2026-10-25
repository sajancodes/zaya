"""Display service providing a unified interface over Zaya's UI display.
Created and developed by Sajan Rai for Zaya.
"""
from __future__ import annotations

import logging
import time
from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional

from core.tool_result import ToolResult

logger = logging.getLogger(__name__)

SAFE_DISPLAY_LIMIT = 64_000


@dataclass
class DisplayState:
    is_open: bool = False
    title: str = ""
    content_length: int = 0
    total_length: int = 0
    format: str = "text"
    last_action: str = ""
    last_updated: float = 0.0
    truncated: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class DisplayService:
    """Service wrapping Zaya's content window/display panel."""

    def __init__(self, ui=None):
        self._ui = ui
        self._state = DisplayState()
        self._cached_content = ""

    def set_ui(self, ui) -> None:
        self._ui = ui

    @property
    def ui(self):
        return self._ui

    def record_external_show(self, title: str, text: str, format: str = "text") -> None:
        """Tracks display state when show_content is called directly from other parts of Zaya."""
        self._state.is_open = True
        self._state.title = str(title or "")
        self._state.content_length = len(text or "")
        self._state.total_length = len(text or "")
        self._state.format = format or "text"
        self._state.last_action = "show"
        self._state.last_updated = time.time()
        self._state.truncated = False
        self._cached_content = text or ""

    def show_text(self, title: str, content: str, format: str = "text") -> ToolResult:
        """Display text, list, code, or markdown content on Zaya's display."""
        if self._ui is None:
            return ToolResult(
                status="failed",
                summary="The Zaya display is unavailable.",
                data={"displayed": False, "action": "show", "reason": "No UI instance registered"},
            )

        if content is None:
            return ToolResult(
                status="failed",
                summary="No content was provided to display.",
                data={"displayed": False, "action": "show", "reason": "Empty content"},
            )

        content_str = str(content)
        total_len = len(content_str)
        is_truncated = False
        display_text = content_str

        if total_len > SAFE_DISPLAY_LIMIT:
            is_truncated = True
            display_text = (
                content_str[:SAFE_DISPLAY_LIMIT]
                + f"\n\n...[Content truncated for display — {SAFE_DISPLAY_LIMIT} of {total_len} characters shown. Use file export if full output is needed]..."
            )

        # Safe formatting adjustment
        format_type = (format or "text").lower().strip()
        if format_type == "code" and not display_text.strip().startswith("```"):
            display_text = f"```\n{display_text}\n```"

        title_str = str(title or "DISPLAY")
        try:
            if hasattr(self._ui, "show_content"):
                try:
                    self._ui.show_content(title_str, display_text, format=format_type)
                except TypeError:
                    # In case of mock or legacy signature accepting 2 args
                    self._ui.show_content(title_str, display_text)
            else:
                return ToolResult(
                    status="failed",
                    summary="The Zaya display is unavailable.",
                    data={"displayed": False, "action": "show", "reason": "UI missing show_content"},
                )
        except Exception as e:
            logger.exception("Failed to show content on display: %s", e)
            return ToolResult(
                status="failed",
                summary=f"Display failed: {e}",
                data={"displayed": False, "action": "show", "error": str(e)},
            )

        self._cached_content = display_text
        self._state.is_open = True
        self._state.title = title_str
        self._state.content_length = len(display_text)
        self._state.total_length = total_len
        self._state.format = format_type
        self._state.last_action = "show"
        self._state.last_updated = time.time()
        self._state.truncated = is_truncated

        summary = (
            f"Displayed {title_str} on Zaya's display ({len(display_text)} characters)."
            if not is_truncated
            else f"Displayed {title_str} on Zaya's display (truncated {SAFE_DISPLAY_LIMIT} of {total_len} chars)."
        )

        return ToolResult(
            status="success",
            summary=summary,
            data={
                "displayed": True,
                "action": "show",
                "title": title_str,
                "format": format_type,
                "content_length": len(display_text),
                "total_length": total_len,
                "truncated": is_truncated,
            },
            evidence=[{"displayed": True, "title": title_str}],
            side_effect=True,
        )

    def update_text(self, content: str, title: Optional[str] = None, format: Optional[str] = None) -> ToolResult:
        """Update existing content on Zaya's display."""
        active_title = title if title is not None else (self._state.title or "DISPLAY")
        active_format = format if format is not None else self._state.format
        result = self.show_text(active_title, content, format=active_format)
        if result.status == "success":
            self._state.last_action = "update"
            result.data["action"] = "update"
            result.summary = f"Updated content for {active_title} on Zaya's display."
        return result

    def append_text(self, content: str) -> ToolResult:
        """Append text to the existing display."""
        if self._ui is None:
            return ToolResult(
                status="failed",
                summary="The Zaya display is unavailable.",
                data={"displayed": False, "action": "append", "reason": "No UI instance registered"},
            )

        if content is None:
            return ToolResult(
                status="failed",
                summary="No content was provided to append.",
                data={"displayed": False, "action": "append", "reason": "Empty content"},
            )

        combined = (self._cached_content + '\n' + str(content)).strip()
        result = self.show_text(self._state.title or 'DISPLAY', combined, format=self._state.format)
        if result.status == 'success':
            self._state.last_action = 'append'
            result.data['action'] = 'append'
            result.summary = 'Appended content to Zaya display.' + (' The display limit was reached.' if result.data.get('truncated') else '')
        return result

    def clear(self) -> ToolResult:
        """Clear text from Zaya's display without closing the panel."""
        if self._ui is None:
            return ToolResult(
                status="failed",
                summary="The Zaya display is unavailable.",
                data={"displayed": False, "action": "clear", "reason": "No UI instance registered"},
            )

        try:
            if hasattr(self._ui, "clear_content"):
                self._ui.clear_content()
            elif hasattr(self._ui, "show_content"):
                self._ui.show_content("DISPLAY CLEARED", "")
        except Exception as e:
            logger.exception("Failed to clear display: %s", e)
            return ToolResult(
                status="failed",
                summary=f"Display clear failed: {e}",
                data={"displayed": False, "action": "clear", "error": str(e)},
            )

        self._cached_content = ""
        self._state.title = ""
        self._state.content_length = 0
        self._state.total_length = 0
        self._state.last_action = "clear"
        self._state.last_updated = time.time()

        return ToolResult(
            status="success",
            summary="Cleared Zaya's display.",
            data={"displayed": False, "action": "clear"},
            evidence=[{"action": "clear"}],
            side_effect=True,
        )

    def close(self) -> ToolResult:
        """Close/hide Zaya's display panel/window."""
        if self._ui is None:
            return ToolResult(
                status="failed",
                summary="The Zaya display is unavailable.",
                data={"displayed": False, "action": "close", "reason": "No UI instance registered"},
            )

        try:
            if hasattr(self._ui, "close_content"):
                self._ui.close_content()
            else:
                return ToolResult('failed', 'The display has no thread-safe close operation.', {'displayed': False})
        except Exception as e:
            logger.exception("Failed to close display: %s", e)
            return ToolResult(
                status="failed",
                summary=f"Display close failed: {e}",
                data={"displayed": False, "action": "close", "error": str(e)},
            )

        self._state.is_open = False
        self._state.last_action = "close"
        self._state.last_updated = time.time()

        return ToolResult(
            status="success",
            summary="Closed Zaya's display.",
            data={"displayed": False, "action": "close", "is_open": False},
            evidence=[{"action": "close"}],
            side_effect=True,
        )

    def status(self) -> ToolResult:
        """Return the current active status of Zaya's display."""
        # Check actual visibility if UI supports it
        if self._ui is not None and hasattr(self._ui, "is_content_visible"):
            try:
                self._state.is_open = bool(self._ui.is_content_visible())
            except Exception:
                pass

        state_dict = self.get_state()
        return ToolResult(
            status="success",
            summary=f"Zaya display is {'open' if self._state.is_open else 'closed'}.",
            data=state_dict,
            evidence=[{"is_open": self._state.is_open, "title": self._state.title}],
        )

    def get_state(self) -> Dict[str, Any]:
        return self._state.to_dict()

    def is_visible(self) -> bool:
        if self._ui is not None and hasattr(self._ui, "is_content_visible"):
            try:
                return bool(self._ui.is_content_visible())
            except Exception:
                pass
        return self._state.is_open


_global_display_service: Optional[DisplayService] = None


def get_display_service(ui=None) -> DisplayService:
    global _global_display_service
    if _global_display_service is None:
        _global_display_service = DisplayService(ui)
    elif ui is not None:
        _global_display_service.set_ui(ui)
    return _global_display_service
