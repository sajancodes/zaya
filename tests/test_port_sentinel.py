"""Unit tests for Developer Port & Service Inspector.
Created and developed by Sajan Rai for Zaya.
"""
from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, patch
import pytest

from actions.port_sentinel import (
    TOOL,
    _free_port,
    _get_process_details,
    _inspect_port,
    _list_listening_ports,
    _scan_dev_ports,
    port_sentinel,
)
from core.execution_policy import TRUST_EXTERNAL_MESSAGE, TRUST_LOCAL_OWNER, with_trust
from core.fast_reflex import FastReflexRouter
from core.tools.routing import ToolRouter


def test_port_sentinel_requires_owner():
    with with_trust(TRUST_EXTERNAL_MESSAGE):
        with pytest.raises(PermissionError):
            port_sentinel({"action": "inspect", "port": 8000})


def test_port_sentinel_inspect_occupied():
    mock_inspection = {
        "port": 3000,
        "occupied": True,
        "count": 1,
        "matches": [{
            "port": 3000,
            "protocol": "TCP",
            "status": "LISTEN",
            "local_address": "127.0.0.1:3000",
            "pid": 5555,
            "process_name": "node.exe",
            "path": "C:\\Program Files\\nodejs\\node.exe",
            "memory_mb": 112.4,
        }]
    }
    with patch("actions.port_sentinel._inspect_port", return_value=mock_inspection):
        with with_trust(TRUST_LOCAL_OWNER):
            res_raw = port_sentinel({"action": "inspect", "port": 3000})
            res = json.loads(res_raw)
            assert res["status"] == "success"
            assert "OCCUPIED by 'node.exe'" in res["summary"]
            assert res["data"]["occupied"] is True


def test_port_sentinel_inspect_free():
    mock_inspection = {"port": 9999, "occupied": False, "count": 0, "matches": []}
    with patch("actions.port_sentinel._inspect_port", return_value=mock_inspection):
        with with_trust(TRUST_LOCAL_OWNER):
            res_raw = port_sentinel({"action": "inspect", "port": 9999})
            res = json.loads(res_raw)
            assert res["status"] == "success"
            assert "Port 9999 is FREE" in res["summary"]
            assert res["data"]["occupied"] is False


def test_port_sentinel_list():
    with with_trust(TRUST_LOCAL_OWNER):
        res_raw = port_sentinel({"action": "list", "limit": 10})
        res = json.loads(res_raw)
        assert res["status"] == "success"
        assert isinstance(res["data"], list)


def test_port_sentinel_dev_ports():
    with with_trust(TRUST_LOCAL_OWNER):
        res_raw = port_sentinel({"action": "dev_ports"})
        res = json.loads(res_raw)
        assert res["status"] == "success"
        assert "Dev Ports:" in res["summary"]
        assert "occupied" in res["data"]
        assert "free" in res["data"]


def test_port_sentinel_free_blocks_system_process():
    mock_inspection = {
        "port": 135,
        "occupied": True,
        "matches": [{
            "port": 135,
            "pid": 1612,
            "process_name": "svchost.exe",
        }]
    }
    mock_proc = MagicMock()
    mock_proc.name.return_value = "svchost.exe"

    with patch("actions.port_sentinel._inspect_port", return_value=mock_inspection), \
         patch("psutil.Process", return_value=mock_proc):
        with with_trust(TRUST_LOCAL_OWNER):
            res_raw = port_sentinel({"action": "free_port", "port": 135})
            res = json.loads(res_raw)
            assert res["status"] == "error"
            assert "protected system service" in res["message"]


def test_port_sentinel_free_blocks_zaya():
    mock_inspection = {
        "port": 8000,
        "occupied": True,
        "matches": [{
            "port": 8000,
            "pid": os.getpid(),
            "process_name": "python.exe",
        }]
    }
    with patch("actions.port_sentinel._inspect_port", return_value=mock_inspection):
        with with_trust(TRUST_LOCAL_OWNER):
            res_raw = port_sentinel({"action": "free_port", "port": 8000})
            res = json.loads(res_raw)
            assert res["status"] == "error"
            assert "Zaya assistant process" in res["message"]


def test_tool_declaration_schema():
    assert TOOL["name"] == "port_sentinel"
    assert "inspect" in TOOL["parameters"]["properties"]["action"]["enum"]
    assert "free_port" in TOOL["parameters"]["properties"]["action"]["enum"]
    assert callable(TOOL["handler"])


def test_fast_reflex_dev_ports():
    router = FastReflexRouter()
    intent, score = router.match("check dev ports")
    assert intent == "DEV_PORTS_QUERY"
    assert score >= 0.88

    intent, score = router.match("list listening ports")
    assert intent == "DEV_PORTS_QUERY"
    assert score >= 0.88

    res = router.execute_intent("DEV_PORTS_QUERY")
    assert res.matched is True
    assert "dev port(s) active" in res.ack or "common dev ports are completely free" in res.ack


def test_tool_router_maps_port_sentinel():
    router = ToolRouter()
    declarations = [
        {"name": "port_sentinel", "description": "inspect listening ports and resolve EADDRINUSE"},
        {"name": "web_search", "description": "search web"},
    ]
    routed = router.route("what process is listening on port 3000", declarations)
    names = [d["name"] for d in routed.declarations]
    assert "port_sentinel" in names
