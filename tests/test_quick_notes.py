import json
import tempfile
from pathlib import Path
from unittest.mock import patch
from actions.quick_notes import quick_notes, TOOL, _init_db


def test_tool_declaration():
    assert TOOL["name"] == "quick_notes"
    assert "notes" in TOOL["description"].lower()
    assert callable(TOOL["handler"])


def test_quick_notes_lifecycle(tmp_path):
    test_db = tmp_path / "test_notes.db"

    with patch("actions.quick_notes._get_db_path", return_value=test_db), \
         patch("core.execution_policy.require_owner"):

        # 1. Create notes
        raw1 = quick_notes({
            "action": "create",
            "content": "Look into WebGPU rendering for 3D holographic avatar",
            "tags": "dev, graphics"
        })
        res1 = json.loads(raw1)
        assert res1["status"] == "success"
        assert res1["note_id"] == 1
        assert "WebGPU" in res1["title"]

        raw2 = quick_notes({
            "action": "create",
            "title": "Hardware Order",
            "content": "Order new mechanical keyboard and mouse pad",
            "tags": "shopping"
        })
        res2 = json.loads(raw2)
        assert res2["status"] == "success"
        assert res2["note_id"] == 2
        assert res2["title"] == "Hardware Order"

        # 2. List notes
        raw_list = quick_notes({"action": "list", "limit": 10})
        res_list = json.loads(raw_list)
        assert res_list["status"] == "success"
        assert res_list["count"] == 2
        assert len(res_list["notes"]) == 2

        # 3. Search notes
        raw_search = quick_notes({"action": "search", "query": "WebGPU"})
        res_search = json.loads(raw_search)
        assert res_search["status"] == "success"
        assert res_search["count"] == 1
        assert "WebGPU" in res_search["notes"][0]["content"]

        # Search with no match
        raw_search_none = quick_notes({"action": "search", "query": "NonExistentKeywordXYZ"})
        res_search_none = json.loads(raw_search_none)
        assert res_search_none["status"] == "success"
        assert res_search_none["count"] == 0

        # 4. Delete note
        raw_del = quick_notes({"action": "delete", "note_id": 1})
        res_del = json.loads(raw_del)
        assert res_del["status"] == "success"

        # Verify deletion in list
        raw_list2 = quick_notes({"action": "list"})
        res_list2 = json.loads(raw_list2)
        assert res_list2["count"] == 1
        assert res_list2["notes"][0]["id"] == 2


def test_quick_notes_empty_content(tmp_path):
    test_db = tmp_path / "test_notes.db"
    with patch("actions.quick_notes._get_db_path", return_value=test_db), \
         patch("core.execution_policy.require_owner"):
        raw = quick_notes({"action": "create", "content": ""})
        res = json.loads(raw)
        assert res["status"] == "error"
        assert "cannot be empty" in res["message"]
