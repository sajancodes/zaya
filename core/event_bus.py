"""Thread-safe, in-process event delivery; subscribers cannot break producers."""
from __future__ import annotations
import logging
import threading
import time
from collections import defaultdict
from typing import Callable


class EventBus:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._subscribers: dict[str, list[Callable]] = defaultdict(list)

    def subscribe(self, name: str, callback: Callable) -> Callable:
        with self._lock:
            self._subscribers[name].append(callback)
        def unsubscribe() -> None:
            with self._lock:
                if callback in self._subscribers[name]:
                    self._subscribers[name].remove(callback)
        return unsubscribe

    def publish(self, name: str, **data) -> None:
        event = {'event': name, 'timestamp': time.time(), **data}
        with self._lock:
            callbacks = tuple(self._subscribers[name]) + tuple(self._subscribers['*'])
        for callback in callbacks:
            try:
                callback(event)
            except Exception:
                logging.getLogger(__name__).exception('Event subscriber failed for %s', name)


bus = EventBus()
