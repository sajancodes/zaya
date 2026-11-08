"""Tests for Environment Variable & System PATH Sentinel."""
import json
import os
import pytest
from unittest.mock import MagicMock, patch

from actions.env_sentinel import (
    env_sentinel,
    _audit_path,
    _audit_developer_tools,
    _inspect_variable,
    TOOL,
)
from core.execution_policy import set_trust, TRUST_LOCAL_OWNER, TRUST_UNKNOWN


@pytest.fixture(autouse=True)
def ensure_owner_trust():
    set_trust(TRUST_LOCAL_OWNER)
    yield
    set_trust(TRUST_LOCAL_OWNER)


def test_tool_declaration():
    assert TOOL["name"] == "env_sentinel"
    assert "PATH" in TOOL["description"]
    assert callable(TOOL["handler"])


def test_audit_path_clean(tmp_path):
    p1 = str(tmp_path / "bin1")
    p2 = str(tmp_path / "bin2")
    os.makedirs(p1)
    os.makedirs(p2)

    with patch.dict(os.environ, {"PATH": f"{p1}{os.pathsep}{p2}"}):
        res = _audit_path()
        assert res["total_entries"] == 2
        assert res["valid_count"] == 2
        assert res["missing_count"] == 0
        assert res["duplicate_count"] == 0
        assert res["health"] == "Clean"


def test_audit_path_with_missing_and_duplicates(tmp_path):
    p1 = str(tmp_path / "bin1")
    dead = str(tmp_path / "dead_folder")
    os.makedirs(p1)

    fake_path = f"{p1}{os.pathsep}{dead}{os.pathsep}{p1}"
    with patch.dict(os.environ, {"PATH": fake_path}):
        res = _audit_path()
        assert res["total_entries"] == 3
        assert res["valid_count"] == 2
        assert res["missing_count"] == 1
        assert res["duplicate_count"] == 1
        assert "Requires Attention" in res["health"]


def test_audit_developer_tools():
    with patch("shutil.which") as mock_which:
        mock_which.side_effect = lambda t: f"/usr/bin/{t}" if t in ("git", "python", "node") else None
        with patch("actions.env_sentinel._get_tool_version", return_value="v1.0.0"):
            res = _audit_developer_tools()
            assert res["installed_count"] == 3
            assert any(t["name"] == "git" for t in res["installed"])
            assert "docker" in res["missing"]


def test_inspect_variable_normal():
    with patch.dict(os.environ, {"MY_TEST_VAR": "hello_world"}):
        res = _inspect_variable("MY_TEST_VAR")
        assert res["exists"] is True
        assert res["value"] == "hello_world"


def test_inspect_variable_redacted():
    with patch.dict(os.environ, {"GITHUB_API_TOKEN": "super_secret"}):
        res = _inspect_variable("GITHUB_API_TOKEN")
        assert res["status"] == "redacted"
        assert "value" not in res


def test_inspect_variable_not_set():
    res = _inspect_variable("NON_EXISTENT_VAR_12345")
    assert res["exists"] is False


def test_env_sentinel_summary():
    res = json.loads(env_sentinel({"action": "summary"}))
    assert res["status"] == "success"
    assert "Environment Sentinel" in res["summary"]
    assert "path" in res
    assert "developer_tools" in res


def test_env_sentinel_path():
    res = json.loads(env_sentinel({"action": "path"}))
    assert res["status"] == "success"
    assert "PATH Audit" in res["summary"]


def test_env_sentinel_tools():
    res = json.loads(env_sentinel({"action": "tools"}))
    assert res["status"] == "success"
    assert "Developer Toolchain" in res["summary"]


def test_env_sentinel_get():
    with patch.dict(os.environ, {"OS": "Windows_NT"}):
        res = json.loads(env_sentinel({"action": "get", "name": "OS"}))
        assert res["status"] == "success"
        assert "Windows_NT" in res["summary"]


def test_env_sentinel_get_missing_name():
    res = json.loads(env_sentinel({"action": "get"}))
    assert res["status"] == "error"
    assert "Missing required parameter" in res["message"]


def test_env_sentinel_unknown_action():
    res = json.loads(env_sentinel({"action": "unknown"}))
    assert res["status"] == "error"
    assert "Unknown action" in res["message"]


def test_env_sentinel_requires_owner():
    set_trust(TRUST_UNKNOWN)
    try:
        with pytest.raises(PermissionError):
            env_sentinel({"action": "summary"})
    finally:
        set_trust(TRUST_LOCAL_OWNER)
