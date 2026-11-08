"""Unit tests for Smart Clipboard History & Snippet Vault Engine.
Created and developed by Sajan Rai for Zaya.
"""
from __future__ import annotations

import json
from pathlib import Path
import sqlite3
from unittest.mock import MagicMock, patch
import pytest

from actions.clipboard_vault import (
    MAX_UNPINNED_HISTORY,
    TOOL,
    _get_db_path,
    _init_db,
    _read_system_clipboard,
    _trim_history,
    _write_system_clipboard,
    clipboard_vault,
)
from core.execution_policy import TRUST_EXTERNAL_MESSAGE, TRUST_LOCAL_OWNER, with_trust
from core.fast_reflex import FastReflexRouter
from core.tools.routing import ToolRouter


@pytest.fixture
def temp_clipboard_db(tmp_path):
    db_file = tmp_path / "test_clipboard.db"
    with patch("actions.clipboard_vault._get_db_path", return_value=db_file):
        _init_db(db_file)
        yield db_file


def test_clipboard_vault_requires_owner(temp_clipboard_db):
    with with_trust(TRUST_EXTERNAL_MESSAGE):
        with pytest.raises(PermissionError):
            clipboard_vault({"action": "read"})


def test_clipboard_vault_copy_and_read(temp_clipboard_db):
    with patch("actions.clipboard_vault._write_system_clipboard", return_value=True), \
         patch("actions.clipboard_vault._read_system_clipboard", return_value="Hello Zaya Clipboard"):
        with with_trust(TRUST_LOCAL_OWNER):
            # 1. Copy text
            res_raw = clipboard_vault({
                "action": "copy",
                "text": "Hello Zaya Clipboard",
                "label": "greeting",
            })
            res = json.loads(res_raw)
            assert res["status"] == "success"
            assert "Copied 20 characters" in res["summary"]
            assert res["data"]["label"] == "greeting"

            # 2. Read back
            read_raw = clipboard_vault({"action": "read"})
            read_res = json.loads(read_raw)
            assert read_res["status"] == "success"
            assert read_res["data"]["content"] == "Hello Zaya Clipboard"


def test_clipboard_vault_save_and_recall_snippet(temp_clipboard_db):
    with patch("actions.clipboard_vault._write_system_clipboard", return_value=True) as mock_write:
        with with_trust(TRUST_LOCAL_OWNER):
            # 1. Save snippet
            save_raw = clipboard_vault({
                "action": "save_snippet",
                "label": "wifi_pwd",
                "text": "SuperSecretWifiPass123",
            })
            save_res = json.loads(save_raw)
            assert save_res["status"] == "success"
            assert "wifi_pwd" in save_res["summary"]
            clip_id = save_res["data"]["id"]

            # 2. Recall snippet by label
            recall_raw = clipboard_vault({
                "action": "copy_snippet",
                "label": "wifi_pwd",
            })
            recall_res = json.loads(recall_raw)
            assert recall_res["status"] == "success"
            assert "injected into clipboard" in recall_res["summary"]
            mock_write.assert_called_with("SuperSecretWifiPass123")

            # 3. Recall snippet by ID
            recall_id_raw = clipboard_vault({
                "action": "copy_snippet",
                "id": clip_id,
            })
            recall_id_res = json.loads(recall_id_raw)
            assert recall_id_res["status"] == "success"


def test_clipboard_vault_search_and_filter(temp_clipboard_db):
    with patch("actions.clipboard_vault._write_system_clipboard", return_value=True):
        with with_trust(TRUST_LOCAL_OWNER):
            clipboard_vault({"action": "copy", "text": "git commit -m 'initial'", "label": "git_cmd", "pinned": True})
            clipboard_vault({"action": "copy", "text": "random temporary string 123"})
            clipboard_vault({"action": "copy", "text": "git push origin main", "label": "git_push", "pinned": False})

            # Search by query
            search_raw = clipboard_vault({"action": "search", "query": "git"})
            search_res = json.loads(search_raw)
            assert search_res["status"] == "success"
            assert len(search_res["data"]) == 2

            # Filter pinned only
            pinned_raw = clipboard_vault({"action": "search", "pinned_only": True})
            pinned_res = json.loads(pinned_raw)
            assert pinned_res["status"] == "success"
            assert len(pinned_res["data"]) == 1
            assert pinned_res["data"][0]["label"] == "git_cmd"


def test_clipboard_vault_delete(temp_clipboard_db):
    with patch("actions.clipboard_vault._write_system_clipboard", return_value=True):
        with with_trust(TRUST_LOCAL_OWNER):
            save_raw = clipboard_vault({"action": "save_snippet", "label": "to_delete", "text": "temporary"})
            clip_id = json.loads(save_raw)["data"]["id"]

            del_raw = clipboard_vault({"action": "delete", "id": clip_id})
            del_res = json.loads(del_raw)
            assert del_res["status"] == "success"
            assert f"Clip #{clip_id} removed" in del_res["summary"]

            # Clear unpinned
            clear_raw = clipboard_vault({"action": "delete"})
            clear_res = json.loads(clear_raw)
            assert clear_res["status"] == "success"
            assert "Cleared all unpinned" in clear_res["summary"]


def test_clipboard_vault_trimming(temp_clipboard_db):
    with sqlite3.connect(temp_clipboard_db) as conn:
        for i in range(120):
            conn.execute(
                "INSERT INTO clips (created_at, content, label, pinned, char_count) VALUES ('2026-11-08', ?, '', 0, 5)",
                (f"clip_{i}",),
            )
        conn.commit()
        _trim_history(conn)

        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM clips WHERE pinned = 0")
        count = cur.fetchone()[0]
        assert count == MAX_UNPINNED_HISTORY


def test_tool_declaration_schema():
    assert TOOL["name"] == "clipboard_vault"
    assert "read" in TOOL["parameters"]["properties"]["action"]["enum"]
    assert "save_snippet" in TOOL["parameters"]["properties"]["action"]["enum"]
    assert callable(TOOL["handler"])


def test_fast_reflex_clipboard():
    router = FastReflexRouter()
    intent, score = router.match("what's on my clipboard")
    assert intent == "CLIPBOARD_READ_QUERY"
    assert score >= 0.88

    intent, score = router.match("read clipboard")
    assert intent == "CLIPBOARD_READ_QUERY"
    assert score >= 0.88

    with patch("actions.clipboard_vault._read_system_clipboard", return_value="https://github.com/sajancodes/zaya"):
        res = router.execute_intent("CLIPBOARD_READ_QUERY")
        assert res.matched is True
        assert "Clipboard content is:" in res.ack or "Clipboard has" in res.ack
        assert res.data["content"] == "https://github.com/sajancodes/zaya"


def test_tool_router_maps_clipboard():
    router = ToolRouter()
    declarations = [
        {"name": "clipboard_vault", "description": "manage clipboard"},
        {"name": "web_search", "description": "search web"},
    ]
    routed = router.route("search my clipboard history for password", declarations)
    names = [d["name"] for d in routed.declarations]
    assert "clipboard_vault" in names


def test_clipboard_redaction_and_exact_match(temp_clipboard_db):
    from actions.clipboard_vault import redact_sensitive_preview

    # Test token redaction
    redacted_openai = redact_sensitive_preview("sk-proj-1234567890abcdef1234567890")
    assert "...[REDACTED]" in redacted_openai
    assert "1234567890abcdef" not in redacted_openai

    redacted_gh = redact_sensitive_preview("ghp_1234567890abcdefghijklmnopqrstuv")
    assert "...[REDACTED]" in redacted_gh
    assert "1234567890abcdef" not in redacted_gh

    assert "[REDACTED PRIVATE KEY]" in redact_sensitive_preview("-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA...\n-----END RSA PRIVATE KEY-----")
    assert "[REDACTED JWT]" in redact_sensitive_preview("eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3j")
    assert "postgres://user:***@localhost:5432/db" == redact_sensitive_preview("postgres://user:secretpass123@localhost:5432/db")

    # Ordinary text and URLs must not be redacted
    normal = "https://github.com/sajancodes/zaya and regular notes 123"
    assert redact_sensitive_preview(normal) == normal

    # Test exact vs fuzzy snippet recall
    with patch("actions.clipboard_vault._write_system_clipboard", return_value=True) as mock_write:
        with with_trust(TRUST_LOCAL_OWNER):
            clipboard_vault({"action": "save_snippet", "label": "unicode_snippet", "text": "Unicode text"})
            clipboard_vault({"action": "save_snippet", "label": "code", "text": "Exact code match"})

            res_raw = clipboard_vault({"action": "copy_snippet", "label": "code"})
            res = json.loads(res_raw)
            assert res["status"] == "success"
            assert res["data"]["label"] == "code"
            mock_write.assert_called_with("Exact code match")

