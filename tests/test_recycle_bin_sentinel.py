"""Tests for Windows Recycle Bin & Storage Trash Sentinel."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch
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

    with patch("actions.recycle_bin_sentinel.get_recycle_bin_stats", return_value=mock_stats), \
         patch("ctypes.windll.shell32.SHEmptyRecycleBinW", return_value=0) as mock_empty:
        res = empty_recycle_bin()
        assert res["status"] == "success"
        assert res["freed_items"] == 5
        assert res["freed_mb"] == 10.0
        mock_empty.assert_called_once()


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
