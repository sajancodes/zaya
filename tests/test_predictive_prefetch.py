"""Tests for Predictive Workspace Pre-fetcher & Hot Diagnostic Cache (Cycle 71).
Created and developed by Sajan Rai for Zaya.
"""
from __future__ import annotations

import json
import time
from unittest.mock import MagicMock
import pytest

from core.predictive_prefetch import PredictiveWorkspacePrefetcher, CacheEntry
from actions.predictive_prefetch_action import handle_predictive_prefetch


class TestPredictivePrefetch:
    def test_cache_hit_and_ttl(self):
        prefetcher = PredictiveWorkspacePrefetcher(default_ttl=0.1)
        prefetcher.set("branch", "main", ttl=0.1)

        # Immediate hit
        assert prefetcher.get("branch") == "main"

        time.sleep(0.15)
        # Entry expired
        entry = prefetcher._cache.get("branch")
        assert entry is not None
        assert entry.is_expired is True

    def test_registered_fetcher_sync_and_async_refresh(self):
        prefetcher = PredictiveWorkspacePrefetcher(default_ttl=0.05)
        mock_fetcher = MagicMock(side_effect=["v1", "v2", "v3"])

        prefetcher.register_fetcher("status", mock_fetcher, ttl=0.05)

        # Initial fetch
        val1 = prefetcher.get("status")
        assert val1 == "v1"
        assert mock_fetcher.call_count == 1

        # While fresh, returns cached value without calling fetcher again
        val2 = prefetcher.get("status")
        assert val2 == "v1"
        assert mock_fetcher.call_count == 1

        # Expire
        time.sleep(0.08)
        # Next get returns stale or triggers refresh
        val3 = prefetcher.get("status")
        assert val3 in ("v1", "v2")

        # Let background thread finish
        time.sleep(0.05)
        assert mock_fetcher.call_count >= 2

    def test_invalidate_tag(self):
        prefetcher = PredictiveWorkspacePrefetcher()
        prefetcher.set("git_branch", "feat", tag="git")
        prefetcher.set("git_diff", "diff...", tag="git")
        prefetcher.set("sys_cpu", "15%", tag="system")

        count = prefetcher.invalidate_tag("git")
        assert count == 2
        assert prefetcher._cache["git_branch"].is_expired is True
        assert prefetcher._cache["git_diff"].is_expired is True
        assert prefetcher._cache["sys_cpu"].is_expired is False


class TestPredictivePrefetchAction:
    def test_action_status_and_prefetch(self):
        res = handle_predictive_prefetch(action="status")
        data = json.loads(res)
        assert data["status"] == "success"
        assert "diagnostics" in data

        prefetch_res = handle_predictive_prefetch(action="prefetch")
        prefetch_data = json.loads(prefetch_res)
        assert prefetch_data["status"] == "success"
        assert "refreshed_count" in prefetch_data

    def test_action_invalidate(self):
        prefetcher = handle_predictive_prefetch(action="invalidate", tag="git")
        data = json.loads(prefetcher)
        assert data["status"] == "success"
        assert data["invalidated_tag"] == "git"
