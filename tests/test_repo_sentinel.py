"""Unit tests for Developer Git Repo Telemetry & Workspace Health Sentinel.
Created and developed by Sajan Rai for Zaya.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from actions.repo_sentinel import (
    TOOL,
    _get_branch_list,
    _get_recent_commits,
    _inspect_repo_status,
    _run_git,
    _scan_workspaces,
    repo_sentinel,
)
from core.execution_policy import TRUST_EXTERNAL_MESSAGE, TRUST_LOCAL_OWNER, with_trust
from core.fast_reflex import FastReflexRouter
from core.tools.routing import ToolRouter


def test_repo_sentinel_requires_owner():
    with with_trust(TRUST_EXTERNAL_MESSAGE):
        with pytest.raises(PermissionError):
            repo_sentinel({"action": "status"})


def test_repo_sentinel_status_live():
    with with_trust(TRUST_LOCAL_OWNER):
        res_raw = repo_sentinel({"action": "status"})
        res = json.loads(res_raw)
        assert res["status"] == "success"
        assert "Repo 'Zaya':" in res["summary"]
        assert res["data"]["branch"] == "main"
        assert res["data"]["is_git_repo"] is True


def test_repo_sentinel_status_mocked_dirty():
    mock_status = (
        "## feature-branch...origin/feature-branch [ahead 2]\n"
        " M core/fast_reflex.py\n"
        "M  actions/new_tool.py\n"
        "?? untracked_file.txt\n"
    )
    mock_log = "abcdef1|sajancodes|5 minutes ago|wip: feature commit"

    with patch("actions.repo_sentinel._run_git", side_effect=[mock_status, mock_log]):
        with with_trust(TRUST_LOCAL_OWNER):
            res_raw = repo_sentinel({"action": "status"})
            res = json.loads(res_raw)
            assert res["status"] == "success"
            assert res["data"]["clean"] is False
            assert res["data"]["ahead"] == 2
            assert res["data"]["staged_count"] == 1
            assert res["data"]["unstaged_count"] == 1
            assert res["data"]["untracked_count"] == 1
            assert res["data"]["last_commit"]["author"] == "sajancodes"


def test_repo_sentinel_scan_workspaces():
    with with_trust(TRUST_LOCAL_OWNER):
        res_raw = repo_sentinel({"action": "scan_workspaces"})
        res = json.loads(res_raw)
        assert res["status"] == "success"
        assert isinstance(res["data"], list)
        assert len(res["data"]) >= 1


def test_repo_sentinel_recent_commits():
    with with_trust(TRUST_LOCAL_OWNER):
        res_raw = repo_sentinel({"action": "recent_commits", "limit": 3})
        res = json.loads(res_raw)
        assert res["status"] == "success"
        assert isinstance(res["data"], list)
        if res["data"]:
            assert "hash" in res["data"][0]
            assert "author" in res["data"][0]
            assert "message" in res["data"][0]


def test_repo_sentinel_branch_list():
    with with_trust(TRUST_LOCAL_OWNER):
        res_raw = repo_sentinel({"action": "branch_list"})
        res = json.loads(res_raw)
        assert res["status"] == "success"
        assert isinstance(res["data"], list)


def test_tool_declaration_schema():
    assert TOOL["name"] == "repo_sentinel"
    assert "status" in TOOL["parameters"]["properties"]["action"]["enum"]
    assert "scan_workspaces" in TOOL["parameters"]["properties"]["action"]["enum"]
    assert callable(TOOL["handler"])


def test_fast_reflex_repo_status():
    router = FastReflexRouter()
    
    intent, score = router.match("git status")
    assert intent == "REPO_STATUS_QUERY"
    assert score >= 0.88

    intent, score = router.match("check git status")
    assert intent == "REPO_STATUS_QUERY"
    assert score >= 0.88

    res = router.execute_intent("REPO_STATUS_QUERY")
    assert res.matched is True
    assert "Repository 'Zaya'" in res.ack


def test_tool_router_maps_repo_sentinel():
    router = ToolRouter()
    declarations = [
        {"name": "repo_sentinel", "description": "inspect git repository status and commits"},
        {"name": "web_search", "description": "search web"},
    ]
    routed = router.route("check if git repository has uncommitted changes", declarations)
    names = [d["name"] for d in routed.declarations]
    assert "repo_sentinel" in names
