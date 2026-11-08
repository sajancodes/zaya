"""Tests for Windows Firewall & Network Security Sentinel."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch
import pytest

from actions.firewall_sentinel import (
    firewall_sentinel,
    _parse_netsh_key_values,
    get_firewall_profiles,
    get_firewall_rule,
    search_firewall_rules,
    get_firewall_summary,
    TOOL,
)
from core.execution_policy import set_trust, TRUST_LOCAL_OWNER, TRUST_UNKNOWN
from core.fast_reflex import FastReflexRouter

_MOCK_ALLPROFILES_TEXT = """
Domain Profile Settings: 
----------------------------------------------------------------------
State                                 ON
Firewall Policy                       BlockInbound,AllowOutbound

Private Profile Settings: 
----------------------------------------------------------------------
State                                 ON
Firewall Policy                       BlockInbound,AllowOutbound

Public Profile Settings: 
----------------------------------------------------------------------
State                                 OFF
Firewall Policy                       AllowInbound,AllowOutbound
"""

_MOCK_RULE_TEXT = """
Rule Name:                            Tailscale-In
----------------------------------------------------------------------
Enabled:                              Yes
Direction:                            In
Profiles:                             Domain,Private
Grouping:                             Tailscale
LocalIP:                              fd7a:115c:a1e0::de01:e9ca/128
RemoteIP:                             Any
Protocol:                             Any
Edge traversal:                       No
Action:                               Allow
"""


@pytest.fixture(autouse=True)
def _owner_trust():
    set_trust(TRUST_LOCAL_OWNER)
    yield
    set_trust(TRUST_LOCAL_OWNER)


def test_owner_security_gate():
    set_trust(TRUST_UNKNOWN)
    with pytest.raises(PermissionError):
        firewall_sentinel({"action": "summary"})


def test_tool_declaration():
    assert TOOL["name"] == "firewall_sentinel"
    assert "parameters" in TOOL
    assert callable(TOOL["handler"])


def test_parse_netsh_key_values_profiles():
    parsed = _parse_netsh_key_values(_MOCK_ALLPROFILES_TEXT)
    assert len(parsed) == 3
    assert parsed[0]["profile"] == "Domain"
    assert parsed[0]["state"] == "ON"
    assert parsed[0]["firewall_policy"] == "BlockInbound,AllowOutbound"
    assert parsed[2]["profile"] == "Public"
    assert parsed[2]["state"] == "OFF"


def test_parse_netsh_key_values_rules():
    parsed = _parse_netsh_key_values(_MOCK_RULE_TEXT)
    assert len(parsed) == 1
    assert parsed[0]["rule_name"] == "Tailscale-In"
    assert parsed[0]["enabled"] == "Yes"
    assert parsed[0]["direction"] == "In"
    assert parsed[0]["action"] == "Allow"


@patch("subprocess.run")
def test_get_firewall_profiles(mock_run):
    mock_run.return_value = MagicMock(returncode=0, stdout=_MOCK_ALLPROFILES_TEXT)
    profiles = get_firewall_profiles()
    assert len(profiles) == 3
    assert profiles["Domain"]["is_active"] is True
    assert profiles["Domain"]["inbound_default"] == "Block"
    assert profiles["Public"]["is_active"] is False


@patch("subprocess.run")
def test_get_firewall_rule(mock_run):
    mock_run.return_value = MagicMock(returncode=0, stdout=_MOCK_RULE_TEXT)
    rules = get_firewall_rule("Tailscale-In")
    assert len(rules) == 1
    assert rules[0]["rule_name"] == "Tailscale-In"
    assert rules[0]["enabled"] == "Yes"


@patch("subprocess.run")
def test_search_firewall_rules(mock_run):
    mock_run.return_value = MagicMock(returncode=0, stdout=_MOCK_RULE_TEXT)
    matches = search_firewall_rules("tailscale")
    assert len(matches) == 1
    assert matches[0]["rule_name"] == "Tailscale-In"


@patch("actions.firewall_sentinel.get_firewall_profiles")
def test_get_firewall_summary_secure(mock_profs):
    mock_profs.return_value = {
        "Domain": {"is_active": True},
        "Private": {"is_active": True},
        "Public": {"is_active": True},
    }
    summary = get_firewall_summary()
    assert "Secure" in summary["security_posture"]
    assert summary["all_profiles_enabled"] is True
    assert summary["disabled_profiles"] == []


@patch("actions.firewall_sentinel.get_firewall_profiles")
def test_get_firewall_summary_warning(mock_profs):
    mock_profs.return_value = {
        "Domain": {"is_active": True},
        "Private": {"is_active": True},
        "Public": {"is_active": False},
    }
    summary = get_firewall_summary()
    assert "Warning" in summary["security_posture"]
    assert summary["all_profiles_enabled"] is False
    assert "Public" in summary["disabled_profiles"]


def test_firewall_sentinel_actions():
    res_raw = firewall_sentinel({"action": "summary"})
    res = json.loads(res_raw)
    assert res["status"] == "success"
    assert "data" in res

    prof_raw = firewall_sentinel({"action": "profiles"})
    prof = json.loads(prof_raw)
    assert prof["status"] == "success"
    assert "profiles" in prof

    err_raw = firewall_sentinel({"action": "invalid"})
    err = json.loads(err_raw)
    assert err["status"] == "error"


def test_fast_reflex_firewall_status():
    router = FastReflexRouter()
    intent, score = router.match("firewall status")
    assert intent == "FIREWALL_STATUS_QUERY"
    assert score >= 0.88

    res = router.execute_intent("FIREWALL_STATUS_QUERY")
    assert res.matched is True
    assert "Windows Firewall:" in res.ack
