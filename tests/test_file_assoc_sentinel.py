"""Tests for Windows Default Applications & File Associations Sentinel."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch
import pytest

from actions.file_assoc_sentinel import (
    file_assoc_sentinel,
    get_common_associations_audit,
    get_default_app_for_extension,
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
        file_assoc_sentinel({"action": "summary"})


def test_get_default_app_for_extension_live():
    res = get_default_app_for_extension(".txt")
    assert isinstance(res, dict)
    assert res["status"] == "associated"
    assert res["is_associated"] is True
    assert "Notepad" in res["friendly_name"]


def test_get_default_app_for_extension_mocked():
    with patch("actions.file_assoc_sentinel._query_assoc_string") as mock_query:
        # First call: friendly name, second call: exe path
        mock_query.side_effect = ["VLC Media Player", "C:\\Program Files\\VideoLAN\\VLC\\vlc.exe"]
        info = get_default_app_for_extension("mp4")

    assert info["status"] == "associated"
    assert info["extension"] == ".mp4"
    assert info["friendly_name"] == "VLC Media Player"
    assert info["executable_path"] == "C:\\Program Files\\VideoLAN\\VLC\\vlc.exe"
    assert info["is_associated"] is True


def test_get_default_app_for_extension_not_associated():
    with patch("actions.file_assoc_sentinel._query_assoc_string", return_value=None):
        info = get_default_app_for_extension(".xyz123_unknown")

    assert info["status"] == "not_associated"
    assert info["friendly_name"] == "Unknown / Not Associated"
    assert info["is_associated"] is False


def test_get_common_associations_audit():
    audit = get_common_associations_audit()
    assert audit["status"] == "success"
    assert "highlights" in audit
    assert "browser_default" in audit["highlights"]
    assert "pdf_reader" in audit["highlights"]
    assert "categories" in audit
    assert "Documents" in audit["categories"]
    assert "Media" in audit["categories"]
    assert "Archives" in audit["categories"]


def test_file_assoc_sentinel_actions():
    mock_audit = {
        "status": "success",
        "highlights": {
            "browser_default": "Brave",
            "pdf_reader": "Edge",
            "archive_manager": "WinRAR",
            "text_editor": "Notepad",
        },
        "categories": {},
    }
    mock_info = {
        "status": "associated",
        "extension": ".pdf",
        "friendly_name": "Microsoft Edge",
        "executable_path": "C:\\edge.exe",
        "is_associated": True,
    }

    with patch("actions.file_assoc_sentinel.get_common_associations_audit", return_value=mock_audit), \
         patch("actions.file_assoc_sentinel.get_default_app_for_extension", return_value=mock_info):

        out_sum = json.loads(file_assoc_sentinel({"action": "summary"}))
        assert out_sum["status"] == "success"
        assert "Default Applications:" in out_sum["summary"]
        assert "Brave" in out_sum["summary"]

        out_lookup = json.loads(file_assoc_sentinel({"action": "lookup", "extension": ".pdf"}))
        assert out_lookup["status"] == "success"
        assert "Microsoft Edge" in out_lookup["summary"]

        out_err_ext = json.loads(file_assoc_sentinel({"action": "lookup"}))
        assert out_err_ext["status"] == "error"

        out_err_act = json.loads(file_assoc_sentinel({"action": "invalid"}))
        assert out_err_act["status"] == "error"


def test_tool_declaration():
    assert TOOL["name"] == "file_assoc_sentinel"
    assert "parameters" in TOOL
    assert callable(TOOL["handler"])


def test_fast_reflex_default_apps():
    router = FastReflexRouter()

    intent, score = router.match("what opens pdf")
    assert intent == "DEFAULT_APP_QUERY"
    assert score >= 0.88

    res = router.execute_intent(intent)
    assert res.matched is True
    assert "Default Apps:" in res.ack
