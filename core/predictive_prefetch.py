"""Predictive Workspace Pre-fetcher & Hot Diagnostic Cache.
Created and developed by Sajan Rai for Zaya.

Maintains hot, TTL-invalidated cached snapshots of active workspace metadata,
git branch status, system health, and open application context. Provides sub-millisecond
read access for AI agent reasoning loops without blocking on synchronous OS queries.
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    key: str
    data: Any
    created_at: float
    ttl_seconds: float
    tag: str = "general"

    @property
    def is_expired(self) -> bool:
        return (time.monotonic() - self.created_at) > self.ttl_seconds


class PredictiveWorkspacePrefetcher:
    """Hot diagnostic cache with background asynchronous pre-fetching."""

    def __init__(self, default_ttl: float = 30.0) -> None:
        self._cache: Dict[str, CacheEntry] = {}
        self._fetchers: Dict[str, Callable[[], Any]] = {}
        self._lock = threading.RLock()
        self._default_ttl = default_ttl
        self._refreshing: set[str] = set()

    def register_fetcher(self, key: str, fetcher: Callable[[], Any], ttl: Optional[float] = None) -> None:
        """Register an async-safe data fetcher for a given key."""
        with self._lock:
            self._fetchers[key] = fetcher
            if ttl is not None and key in self._cache:
                self._cache[key].ttl_seconds = ttl

    def get(self, key: str, default: Any = None) -> Any:
        """Get cached value. If expired and fetcher is registered, triggers background refresh and returns stale value."""
        with self._lock:
            entry = self._cache.get(key)
            if entry is not None:
                if entry.is_expired:
                    self._trigger_background_refresh(key)
                return entry.data

            # If not in cache but fetcher exists, run synchronous fetch once
            if key in self._fetchers:
                return self.refresh_sync(key)

            return default

    def set(self, key: str, value: Any, ttl: Optional[float] = None, tag: str = "general") -> None:
        """Explicitly set a cached item."""
        with self._lock:
            self._cache[key] = CacheEntry(
                key=key,
                data=value,
                created_at=time.monotonic(),
                ttl_seconds=ttl if ttl is not None else self._default_ttl,
                tag=tag,
            )

    def refresh_sync(self, key: str) -> Any:
        """Force a synchronous fetch and update of the cache."""
        with self._lock:
            fetcher = self._fetchers.get(key)
            if not fetcher:
                return None
        try:
            val = fetcher()
            self.set(key, val)
            return val
        except Exception as e:
            logger.warning("[PredictivePrefetch] Fetcher for '%s' failed: %s", key, e)
            return None

    def _trigger_background_refresh(self, key: str) -> None:
        with self._lock:
            if key in self._refreshing or key not in self._fetchers:
                return
            self._refreshing.add(key)

        def _worker():
            try:
                self.refresh_sync(key)
            finally:
                with self._lock:
                    self._refreshing.discard(key)

        t = threading.Thread(target=_worker, name=f"prefetch_{key}", daemon=True)
        t.start()

    def prefetch_all(self) -> Dict[str, Any]:
        """Trigger refresh of all registered fetchers synchronously and return snapshot."""
        with self._lock:
            keys = list(self._fetchers.keys())
        results = {}
        for k in keys:
            results[k] = self.refresh_sync(k)
        return results

    def invalidate_tag(self, tag: str) -> int:
        """Invalidate all cache entries with a given tag."""
        count = 0
        with self._lock:
            for entry in self._cache.values():
                if entry.tag == tag:
                    entry.created_at = 0.0  # Force expiration
                    count += 1
        return count

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "total_cached": len(self._cache),
                "registered_fetchers": len(self._fetchers),
                "keys": [
                    {
                        "key": e.key,
                        "tag": e.tag,
                        "expired": e.is_expired,
                        "age_sec": round(time.monotonic() - e.created_at, 1),
                    }
                    for e in self._cache.values()
                ],
            }


# ── Global Singleton ─────────────────────────────────────────────────────────

_prefetcher: Optional[PredictiveWorkspacePrefetcher] = None


def get_prefetcher() -> PredictiveWorkspacePrefetcher:
    global _prefetcher
    if _prefetcher is None:
        _prefetcher = PredictiveWorkspacePrefetcher()
    return _prefetcher
