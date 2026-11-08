"""Tests for Windows Hosts File & Domain Overrides Sentinel."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from actions.hosts_sentinel import (
    get_hosts_summary,
    hosts_sentinel,
    parse_hosts_file,
    search_hosts,
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
        hosts_sentinel({"action": "summary"})


def test_parse_hosts_file_live():
    mappings = parse_hosts_file()
    assert isinstance(mappings, list)
    for m in mappings:
        assert "ip" in m
        assert "domain" in m
        assert "category" in m


MOCK_HOSTS_CONTENT = """# Copyright (c) 1993-2009 Microsoft Corp.
#
# This is a sample HOSTS file used by Microsoft TCP/IP for Windows.

127.0.0.1       localhost
::1             localhost
127.0.0.1       api.dev.local # local development endpoint
0.0.0.0         tracker.ads.com # block ad tracker
192.168.1.100   myserver.lan
"""


def test_parse_hosts_file_mocked(tmp_path):
    mock_file = tmp_path / "hosts"
    mock_file.write_text(MOCK_HOSTS_CONTENT, encoding="utf-8")

    import actions.hosts_sentinel as hs
    with patch.object(hs, "_get_hosts_path", return_value=mock_file):
        mappings = hs.parse_hosts_file()
        assert len(mappings) == 5

        # Check loopback
        assert mappings[0]["ip"] == "127.0.0.1"
        assert mappings[0]["domain"] == "localhost"
        assert mappings[0]["category"] == "Loopback"

        # Check local dev
        assert mappings[2]["domain"] == "api.dev.local"
        assert mappings[2]["category"] == "Local Development"

        # Check ad filter
        assert mappings[3]["domain"] == "tracker.ads.com"
        assert mappings[3]["category"] == "Security / Filter"

        # Check custom
        assert mappings[4]["domain"] == "myserver.lan"
        assert mappings[4]["category"] == "Custom"


def test_search_hosts_mocked(tmp_path):
    mock_file = tmp_path / "hosts"
    mock_file.write_text(MOCK_HOSTS_CONTENT, encoding="utf-8")

    import actions.hosts_sentinel as hs
    with patch.object(hs, "_get_hosts_path", return_value=mock_file):
        matches = hs.search_hosts("tracker")
        assert len(matches) == 1
        assert matches[0]["domain"] == "tracker.ads.com"

        matches_ip = hs.search_hosts("192.168.1.100")
        assert len(matches_ip) == 1
        assert matches_ip[0]["domain"] == "myserver.lan"

        matches_none = hs.search_hosts("nonexistent-domain.xyz")
        assert len(matches_none) == 0


def test_get_hosts_summary_mocked(tmp_path):
    mock_file = tmp_path / "hosts"
    mock_file.write_text(MOCK_HOSTS_CONTENT, encoding="utf-8")

    import actions.hosts_sentinel as hs
    with patch.object(hs, "_get_hosts_path", return_value=mock_file):
        summary = hs.get_hosts_summary()
        assert summary["status"] == "success"
        assert summary["total_mappings"] == 5
        assert summary["local_dev_mappings"] == 3  # 2 localhost + 1 .local
        assert summary["filter_mappings"] == 1
        assert summary["custom_mappings"] == 1


def test_hosts_sentinel_actions(tmp_path):
    mock_file = tmp_path / "hosts"
    mock_file.write_text(MOCK_HOSTS_CONTENT, encoding="utf-8")

    import actions.hosts_sentinel as hs
    with patch.object(hs, "_get_hosts_path", return_value=mock_file):
        # Summary
        res_summary = json.loads(hs.hosts_sentinel({"action": "summary"}))
        assert res_summary["status"] == "success"
        assert "Hosts File Audit" in res_summary["summary"]

        # Search found
        res_search = json.loads(hs.hosts_sentinel({"action": "lookup", "domain": "localhost"}))
        assert res_search["status"] == "success"
        assert len(res_search["data"]["matches"]) >= 2

        # Search not found
        res_not_found = json.loads(hs.hosts_sentinel({"action": "lookup", "domain": "invalid"}))
        assert res_not_found["status"] == "not_found"

        # Search missing domain
        res_err = json.loads(hs.hosts_sentinel({"action": "lookup"}))
        assert res_err["status"] == "error"

        # List
        res_list = json.loads(hs.hosts_sentinel({"action": "list"}))
        assert res_list["status"] == "success"
        assert res_list["data"]["count"] == 5

        # Unknown action
        res_unknown = json.loads(hs.hosts_sentinel({"action": "delete_all"}))
        assert res_unknown["status"] == "error"


def test_hosts_tool_metadata():
    assert TOOL["name"] == "hosts_sentinel"
    assert "hosts" in TOOL["description"].lower()
    assert TOOL["handler"] == hosts_sentinel


def test_fast_reflex_hosts_file_query():
    router = FastReflexRouter()
    intent, score = router.match("check hosts file")
    assert intent == "HOSTS_FILE_QUERY"
    assert score >= 0.88

    res = router.execute_intent(intent)
    assert res.matched is True
    assert res.intent == "HOSTS_FILE_QUERY"
    assert "Hosts file contains" in res.ack
