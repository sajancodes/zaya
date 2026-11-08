"""Unit tests for Storage Sentinel & Disk Waste Analyzer.
Created and developed by Sajan Rai for Zaya.
"""
from __future__ import annotations

import json
from pathlib import Path
import time
from unittest.mock import MagicMock, patch
import pytest

from actions.storage_sentinel import (
    TOOL,
    _clean_temp_waste,
    _find_large_files,
    _get_drive_telemetry,
    _scan_temp_waste,
    storage_sentinel,
)
from core.execution_policy import TRUST_EXTERNAL_MESSAGE, TRUST_LOCAL_OWNER, with_trust
from core.fast_reflex import FastReflexRouter
from core.tools.routing import ToolRouter


def test_storage_sentinel_requires_owner():
    with with_trust(TRUST_EXTERNAL_MESSAGE):
        with pytest.raises(PermissionError):
            storage_sentinel({"action": "free_space"})


def test_storage_sentinel_free_space():
    with with_trust(TRUST_LOCAL_OWNER):
        res_raw = storage_sentinel({"action": "free_space"})
        res = json.loads(res_raw)
        assert res["status"] == "success"
        assert "Disk Space:" in res["summary"]
        assert isinstance(res["data"], list)
        if res["data"]:
            assert "mountpoint" in res["data"][0]
            assert "free_gb" in res["data"][0]


def test_storage_sentinel_analyze_junk():
    with patch("actions.storage_sentinel._scan_temp_waste") as mock_scan:
        mock_scan.return_value = {
            "temp_path": "C:\\MockTemp",
            "total_files_scanned": 150,
            "stale_files_found": 42,
            "reclaimable_mb": 128.5,
            "max_age_hours": 24,
        }
        with with_trust(TRUST_LOCAL_OWNER):
            res_raw = storage_sentinel({"action": "analyze_junk", "max_age_hours": 24})
            res = json.loads(res_raw)
            assert res["status"] == "success"
            assert "128.5 MB reclaimable" in res["summary"]
            assert res["data"]["stale_files_found"] == 42


def test_storage_sentinel_clean_junk(tmp_path):
    # Create test stale files
    test_file_old = tmp_path / "old.tmp"
    test_file_old.write_text("dummy old data " * 100)
    old_time = time.time() - (48 * 3600)
    import os
    os.utime(test_file_old, (old_time, old_time))

    test_file_new = tmp_path / "new.tmp"
    test_file_new.write_text("fresh active data")

    with patch("tempfile.gettempdir", return_value=str(tmp_path)):
        with with_trust(TRUST_LOCAL_OWNER):
            res_raw = storage_sentinel({"action": "clean_junk", "max_age_hours": 24})
            res = json.loads(res_raw)
            assert res["status"] == "success"
            assert res["data"]["deleted_count"] >= 1
            assert not test_file_old.exists()
            assert test_file_new.exists()


def test_storage_sentinel_large_files(tmp_path):
    # Create mock large file
    large_file = tmp_path / "big_video.mp4"
    large_file.write_bytes(b"0" * (1024 * 1024 * 5))  # 5 MB

    small_file = tmp_path / "readme.txt"
    small_file.write_text("small text")

    with with_trust(TRUST_LOCAL_OWNER):
        res_raw = storage_sentinel({
            "action": "large_files",
            "directory": str(tmp_path),
            "min_size_mb": 4,
            "limit": 5,
        })
        res = json.loads(res_raw)
        assert res["status"] == "success"
        assert len(res["data"]) == 1
        assert res["data"][0]["name"] == "big_video.mp4"


def test_storage_sentinel_summary():
    with with_trust(TRUST_LOCAL_OWNER):
        res_raw = storage_sentinel({"action": "summary"})
        res = json.loads(res_raw)
        assert res["status"] == "success"
        assert "Storage Health:" in res["summary"]
        assert "drives" in res["data"]
        assert "waste" in res["data"]


def test_tool_declaration_schema():
    assert TOOL["name"] == "storage_sentinel"
    assert "free_space" in TOOL["parameters"]["properties"]["action"]["enum"]
    assert "clean_junk" in TOOL["parameters"]["properties"]["action"]["enum"]
    assert callable(TOOL["handler"])


def test_fast_reflex_disk_space():
    router = FastReflexRouter()
    intent, score = router.match("how much disk space")
    assert intent == "DISK_SPACE_QUERY"
    assert score >= 0.88

    intent, score = router.match("free disk space")
    assert intent == "DISK_SPACE_QUERY"
    assert score >= 0.88

    res = router.execute_intent("DISK_SPACE_QUERY")
    assert res.matched is True
    assert "free out of" in res.ack or "unavailable" in res.ack


def test_tool_router_maps_storage():
    router = ToolRouter()
    declarations = [
        {"name": "storage_sentinel", "description": "manage disk space and clean temp files"},
        {"name": "web_search", "description": "search web"},
    ]
    routed = router.route("clean temporary files and check storage disk space", declarations)
    names = [d["name"] for d in routed.declarations]
    assert "storage_sentinel" in names
