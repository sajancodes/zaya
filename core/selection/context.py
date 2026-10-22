"""Selection context captures two-finger drag bounding regions and target app metadata."""
from __future__ import annotations

import time
import threading
from dataclasses import dataclass, field
from typing import Optional, Tuple


@dataclass
class SelectionContext:
    start: Tuple[int, int]
    end: Tuple[int, int]
    rect: Tuple[int, int, int, int]  # (min_x, min_y, max_x, max_y)
    timestamp: float = field(default_factory=time.time)
    target_app: str = "Desktop"
    target_title: str = ""
    target_pid: int = 0
    cached_text: str = ""

    def is_valid(self, ttl_seconds: float = 300.0) -> bool:
        """Returns True if this selection is fresh within ttl_seconds."""
        return (time.time() - self.timestamp) <= ttl_seconds

    @property
    def width(self) -> int:
        return max(0, self.rect[2] - self.rect[0])

    @property
    def height(self) -> int:
        return max(0, self.rect[3] - self.rect[1])


class SelectionManager:
    """Thread-safe store for the latest active selection context."""

    def __init__(self):
        self._lock = threading.Lock()
        self._current: Optional[SelectionContext] = None

    def set_selection(self, context: SelectionContext) -> None:
        with self._lock:
            self._current = context

    def get_selection(self, ttl_seconds: float = 300.0) -> Optional[SelectionContext]:
        with self._lock:
            if self._current is not None and self._current.is_valid(ttl_seconds):
                return self._current
            return None

    def clear(self) -> None:
        with self._lock:
            self._current = None


_global_manager = SelectionManager()


def get_selection_manager() -> SelectionManager:
    return _global_manager
