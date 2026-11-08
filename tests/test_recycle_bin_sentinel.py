"""Tests for Windows Recycle Bin & Storage Trash Sentinel."""
from __future__ import annotations

import json
from unittest.mock import patch
import pytest

from actions.recycle_bin_sentinel import (
    empty_recycle_bin,
    get_recycle_bin_stats,
    recycle_bin_sentinel,
    TOOL,
)
from core.execution_policy import set_trust, TRUST_LOCAL_OWNER, TRUST_UNKNOWN
from core.fast_reflex import FastReflexRouter


@pytest.fixture(autouse=True)
def _owner_trust():
    set_trust(TRUST_LOCAL_OWNER)
    yield
    set_trust(TRUST_LOCAL_OWNER)


def test_owner_security_gate():
    set_trust(TRUST_UNKNOWN)
    with pytest.raises(PermissionError):
        recycle_bin_sentinel({"action": "status"})


def test_get_recycle_bin_stats_live():
    res = get_recycle_bin_stats()
    assert isinstance(res, dict)
    assert res["status"] == "success"
    assert "items_count" in res
    assert "size_bytes" in res
    assert "size_mb" in res
    assert "is_empty" in res


def test_get_recycle_bin_stats_mocked():
    import actions.recycle_bin_sentinel as rbs

    with patch.object(rbs, "get_recycle_bin_stats", return_value={
        "status": "success",
        "items_count": 14,
        "size_bytes": 52428800,
        "size_mb": 50.0,
        "size_gb": 0.049,
        "drive": "All Drives",
        "is_empty": False,
    }):
        stats = rbs.get_recycle_bin_stats()
        assert stats["items_count"] == 14
        assert stats["size_mb"] == 50.0
        assert stats["is_empty"] is False


def test_empty_recycle_bin_mocked():
    mock_stats = {
        "status": "success",
        "items_count": 5,
        "size_bytes": 10485760,
        "size_mb": 10.0,
        "size_gb": 0.01,
        "drive": "All Drives",
        "is_empty": False,
    }
    mock_post = {
        "status": "success",
        "items_count": 0,
        "size_bytes": 0,
        "size_mb": 0.0,
        "size_gb": 0.0,
        "drive": "All Drives",
        "is_empty": True,
    }

    with patch("actions.recycle_bin_sentinel.get_recycle_bin_stats", side_effect=[mock_stats, mock_post]), \
         patch("ctypes.windll.shell32.SHEmptyRecycleBinW", return_value=0) as mock_empty:
        res = empty_recycle_bin(confirm=True)
        assert res["status"] == "success"
        assert res["freed_items"] == 5
        assert res["freed_mb"] == 10.0
        mock_empty.assert_called_once()


def test_empty_recycle_bin_safety_and_hresult_handling():
    mock_stats = {
        "status": "success",
        "items_count": 5,
        "size_bytes": 10485760,
        "size_mb": 10.0,
        "size_gb": 0.01,
        "drive": "All Drives",
        "is_empty": False,
    }

    # 1. Confirmation required when confirm=False
    with patch("actions.recycle_bin_sentinel.get_recycle_bin_stats", return_value=mock_stats):
        res_confirm = empty_recycle_bin(confirm=False)
        assert res_confirm["status"] == "confirmation_required"
        assert "Confirmation required" in res_confirm["message"]

    # 2. Cancelled HRESULT
    with patch("actions.recycle_bin_sentinel.get_recycle_bin_stats", return_value=mock_stats), \
         patch("ctypes.windll.shell32.SHEmptyRecycleBinW", return_value=0x80004004):
        res_cancel = empty_recycle_bin(confirm=True)
        assert res_cancel["status"] == "cancelled"

    # 3. Access denied HRESULT
    with patch("actions.recycle_bin_sentinel.get_recycle_bin_stats", return_value=mock_stats), \
         patch("ctypes.windll.shell32.SHEmptyRecycleBinW", return_value=0x80070005):
        res_denied = empty_recycle_bin(confirm=True)
        assert res_denied["status"] == "error"
        assert "Permission denied" in res_denied["message"]

    # 4. Query failure must not report is_empty: True
    with patch("ctypes.windll.shell32.SHQueryRecycleBinW", return_value=1):
        stats_err = get_recycle_bin_stats()
        assert stats_err["status"] == "error"
        assert stats_err["is_empty"] is False



def test_recycle_bin_sentinel_actions():
    mock_stats_nonempty = {
        "status": "success",
        "items_count": 8,
        "size_bytes": 2097152,
        "size_mb": 2.0,
        "size_gb": 0.002,
        "drive": "All Drives",
        "is_empty": False,
    }
    mock_stats_empty = {
        "status": "success",
        "items_count": 0,
        "size_bytes": 0,
        "size_mb": 0.0,
        "size_gb": 0.0,
        "drive": "All Drives",
        "is_empty": True,
    }

    with patch("actions.recycle_bin_sentinel.get_recycle_bin_stats", return_value=mock_stats_nonempty):
        out = json.loads(recycle_bin_sentinel({"action": "status"}))
        assert out["status"] == "success"
        assert "8 item(s)" in out["summary"]

    with patch("actions.recycle_bin_sentinel.get_recycle_bin_stats", return_value=mock_stats_empty):
        out_empty = json.loads(recycle_bin_sentinel({"action": "status"}))
        assert out_empty["status"] == "success"
        assert "completely empty" in out_empty["summary"]

    with patch("actions.recycle_bin_sentinel.empty_recycle_bin", return_value={"status": "success", "message": "Emptied"}):
        out_del = json.loads(recycle_bin_sentinel({"action": "empty"}))
        assert out_del["status"] == "success"

    out_err = json.loads(recycle_bin_sentinel({"action": "invalid"}))
    assert out_err["status"] == "error"


def test_tool_declaration():
    assert TOOL["name"] == "recycle_bin_sentinel"
    assert "parameters" in TOOL
    assert callable(TOOL["handler"])


def test_fast_reflex_recycle_bin():
    router = FastReflexRouter()

    # Query
    intent, score = router.match("check recycle bin")
    assert intent == "RECYCLE_BIN_QUERY"
    assert score >= 0.88

    res = router.execute_intent(intent)
    assert res.matched is True
    assert "Recycle Bin" in res.ack

    # Empty
    empty_intent, e_score = router.match("empty recycle bin")
    assert empty_intent == "RECYCLE_BIN_EMPTY"
    assert e_score >= 0.88

    with patch("actions.recycle_bin_sentinel.empty_recycle_bin", return_value={"status": "success", "freed_mb": 5.2, "freed_items": 3}):
        res_empty = router.execute_intent(empty_intent)
        assert res_empty.matched is True
        assert "Recycle Bin emptied" in res_empty.ack

    # Fast reflex partial success and unverified handling
    with patch("actions.recycle_bin_sentinel.empty_recycle_bin", return_value={"status": "partial_success", "freed_mb": 4.0, "freed_items": 2, "remaining_items": 1}):
        res_part = router.execute_intent(empty_intent)
        assert res_part.matched is True
        assert "partially emptied" in res_part.ack

    with patch("actions.recycle_bin_sentinel.empty_recycle_bin", return_value={"status": "unverified"}):
        res_unv = router.execute_intent(empty_intent)
        assert res_unv.matched is True
        assert "could not be verified" in res_unv.ack


def test_recycle_bin_post_verification_and_telemetry():
    initial_stats = {
        "status": "success",
        "items_count": 10,
        "size_bytes": 20971520,
        "size_mb": 20.0,
        "size_gb": 0.02,
        "drive": "All Drives",
        "is_empty": False,
    }
    empty_stats = {
        "status": "success",
        "items_count": 0,
        "size_bytes": 0,
        "size_mb": 0.0,
        "size_gb": 0.0,
        "drive": "All Drives",
        "is_empty": True,
    }
    partial_stats = {
        "status": "success",
        "items_count": 3,
        "size_bytes": 6291456,
        "size_mb": 6.0,
        "size_gb": 0.006,
        "drive": "All Drives",
        "is_empty": False,
    }
    failed_post_stats = {
        "status": "error",
        "message": "Access denied querying shell stats",
        "items_count": 0,
        "size_bytes": 0,
        "is_empty": False,
    }

    # 1. Successful API call and successful post-verification
    with patch("actions.recycle_bin_sentinel.get_recycle_bin_stats", side_effect=[initial_stats, empty_stats]), \
         patch("ctypes.windll.shell32.SHEmptyRecycleBinW", return_value=0):
        res_full = empty_recycle_bin(confirm=True)
        assert res_full["status"] == "success"
        assert res_full["freed_items"] == 10
        assert res_full["freed_bytes"] == 20971520
        assert res_full["freed_mb"] == 20.0
        assert res_full["remaining_items"] == 0

    # 2. Successful API call but failed post-verification (returns unverified, NOT zero remaining)
    with patch("actions.recycle_bin_sentinel.get_recycle_bin_stats", side_effect=[initial_stats, failed_post_stats]), \
         patch("ctypes.windll.shell32.SHEmptyRecycleBinW", return_value=0):
        res_unverified = empty_recycle_bin(confirm=True)
        assert res_unverified["status"] == "unverified"
        assert res_unverified["freed_items"] is None
        assert "post-operation verification failed" in res_unverified["message"]

    # 3. Partial deletion: 10 items initially, 3 remaining
    with patch("actions.recycle_bin_sentinel.get_recycle_bin_stats", side_effect=[initial_stats, partial_stats]), \
         patch("ctypes.windll.shell32.SHEmptyRecycleBinW", return_value=0):
        res_partial = empty_recycle_bin(confirm=True)
        assert res_partial["status"] == "partial_success"
        assert res_partial["freed_items"] == 7  # 10 - 3
        assert res_partial["freed_bytes"] == 14680064  # 20971520 - 6291456
        assert res_partial["freed_mb"] == 14.0  # actual difference, not 20.0!
        assert res_partial["remaining_items"] == 3
        assert res_partial["remaining_bytes"] == 6291456

    # 4. No items initially
    with patch("actions.recycle_bin_sentinel.get_recycle_bin_stats", return_value=empty_stats):
        res_empty = empty_recycle_bin(confirm=True)
        assert res_empty["status"] == "success"
        assert res_empty["freed_items"] == 0
        assert "already empty" in res_empty["message"]

