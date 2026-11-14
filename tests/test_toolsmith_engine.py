"""Tests for Toolsmith Engine — Dynamic Tool Synthesis & Runtime Plugin Compiler (Cycle 74).
Created and developed by Sajan Rai for Zaya.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch
import pytest

from core.toolsmith_engine import ToolsmithEngine, SynthesizedToolMeta
from actions.toolsmith_action import handle_toolsmith
from core.execution_policy import with_trust, TRUST_LOCAL_OWNER, TRUST_EXTERNAL_MESSAGE
from core.action_loader import get_action_registry


SAMPLE_TOOL_CODE = """
def sample_calculator(params: dict) -> str:
    a = params.get("a", 0)
    b = params.get("b", 0)
    op = params.get("op", "add")
    if op == "add":
        return f"Result: {a + b}"
    elif op == "multiply":
        return f"Result: {a * b}"
    return "Unknown operation"

TOOL = {
    "name": "sample_calc",
    "description": "Calculates basic arithmetic.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "a": {"type": "NUMBER"},
            "b": {"type": "NUMBER"},
            "op": {"type": "STRING"},
        },
    },
    "handler": sample_calculator,
}
"""

UNSAFE_TOOL_CODE_CTYPES = """
import ctypes

def bad_tool(params: dict) -> str:
    return "Unsafe"

TOOL = {
    "name": "bad_tool",
    "description": "Unsafe tool",
    "handler": bad_tool,
}
"""

UNSAFE_TOOL_CODE_EVAL = """
def bad_eval_tool(params: dict) -> str:
    cmd = params.get("cmd", "")
    return str(eval(cmd))

TOOL = {
    "name": "bad_eval_tool",
    "description": "Unsafe eval",
    "handler": bad_eval_tool,
}
"""


class TestToolsmithEngine:
    def test_ast_security_validation_catches_unsafe_code(self, tmp_path):
        engine = ToolsmithEngine(custom_tools_dir=tmp_path)

        # Ctypes import blocked
        ok1, reason1 = engine.validate_code_safety(UNSAFE_TOOL_CODE_CTYPES)
        assert ok1 is False
        assert "not in the approved safe modules list" in reason1 or "Forbidden import 'ctypes'" in reason1

        # Eval call blocked
        ok2, reason2 = engine.validate_code_safety(UNSAFE_TOOL_CODE_EVAL)
        assert ok2 is False
        assert "Forbidden built-in call 'eval()'" in reason2

        # Valid tool passes
        ok3, reason3 = engine.validate_code_safety(SAMPLE_TOOL_CODE)
        assert ok3 is True
        assert "passed" in reason3.lower()

    def test_synthesize_test_and_register_tool(self, tmp_path):
        engine = ToolsmithEngine(custom_tools_dir=tmp_path)

        with with_trust(TRUST_LOCAL_OWNER):
            ok, msg, meta = engine.synthesize_tool(
                name="sample_calc",
                code=SAMPLE_TOOL_CODE,
                description="Test calculator",
                test_args={"a": 5, "b": 10, "op": "add"},
            )
            assert ok is True
            assert meta is not None
            assert meta.name == "sample_calc"

            # Check that it is registered in ActionRegistry and callable!
            reg = get_action_registry()
            assert reg.has("sample_calc")
            res = reg.run("sample_calc", {"a": 20, "b": 4, "op": "multiply"})
            assert "Result: 80" in res

            # Cleanup
            removed = engine.remove_tool("sample_calc")
            assert removed is True
            assert not reg.has("sample_calc")

    def test_owner_trust_gate_enforcement(self, tmp_path):
        engine = ToolsmithEngine(custom_tools_dir=tmp_path)

        with with_trust(TRUST_EXTERNAL_MESSAGE):
            with pytest.raises(PermissionError):
                engine.synthesize_tool(name="test", code=SAMPLE_TOOL_CODE)

            with pytest.raises(PermissionError):
                engine.remove_tool("test")


class TestToolsmithAction:
    def test_action_synthesize_and_list(self, tmp_path):
        with with_trust(TRUST_LOCAL_OWNER):
            # Synthesize
            res_syn = handle_toolsmith(
                action="synthesize",
                name="sample_calc",
                code=SAMPLE_TOOL_CODE,
                description="Sample Calc via Action",
                test_args_json=json.dumps({"a": 2, "b": 3, "op": "add"}),
            )
            data_syn = json.loads(res_syn)
            assert data_syn["status"] == "success"

            # List
            res_list = handle_toolsmith(action="list")
            data_list = json.loads(res_list)
            assert data_list["count"] >= 1
            assert any(t["name"] == "sample_calc" for t in data_list["tools"])

            # Remove
            res_rem = handle_toolsmith(action="remove", name="sample_calc")
            data_rem = json.loads(res_rem)
            assert data_rem["status"] == "success"
