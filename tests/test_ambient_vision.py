"""Tests for Ambient Vision and Workspace Error Peeler.
Created and developed by Sajan Rai for Zaya.
"""
from __future__ import annotations

import pytest

from core.ambient_vision import WorkspaceErrorPeeler
from core.execution_policy import TRUST_EXTERNAL_MESSAGE, with_trust
from actions.ambient_vision_action import ambient_vision


def test_python_traceback_peeling():
    peeler = WorkspaceErrorPeeler()
    sample = """
Traceback (most recent call last):
  File "C:\\Users\\sajan\\Desktop\\Zaya\\main.py", line 142, in run
    from actions.non_existent import missing_tool
ModuleNotFoundError: No module named 'actions.non_existent'
"""
    findings = peeler.parse_traceback(sample)
    assert len(findings) == 1
    f = findings[0]
    assert f.language == "python"
    assert f.error_type == "ModuleNotFoundError"
    assert "non_existent" in f.message
    assert f.line_number == 142
    assert "pip install" in f.recommended_fix or "import" in f.recommended_fix


def test_typescript_error_peeling():
    peeler = WorkspaceErrorPeeler()
    sample = """
TypeError: Cannot read properties of undefined (reading 'split')
    at processCommand (C:\\Users\\sajan\\Desktop\\App\\src\\index.ts:45:12)
    at run (C:\\Users\\sajan\\Desktop\\App\\src\\runner.ts:12:5)
"""
    findings = peeler.parse_traceback(sample)
    assert len(findings) >= 1
    f = findings[0]
    assert f.language == "typescript"
    assert f.error_type == "TypeError"
    assert f.line_number == 45
    assert "undefined" in f.message


def test_kotlin_compiler_error_peeling():
    peeler = WorkspaceErrorPeeler()
    sample = """
e: C:\\Users\\sajan\\Desktop\\Zaya\\android\\app\\src\\main\\java\\com\\zaya\\companion\\ActionExecutor.kt:89:15 Unresolved reference: sendNotification
"""
    findings = peeler.parse_traceback(sample)
    assert len(findings) == 1
    f = findings[0]
    assert f.language == "kotlin"
    assert f.line_number == 89
    assert "sendNotification" in f.message


def test_rust_compiler_error_peeling():
    peeler = WorkspaceErrorPeeler()
    sample = """
error[E0382]: use of moved value: `buffer`
 --> src/main.rs:18:9
  |
"""
    findings = peeler.parse_traceback(sample)
    assert len(findings) == 1
    f = findings[0]
    assert f.language == "rust"
    assert f.error_type == "E0382"
    assert f.line_number == 18


def test_go_panic_peeling():
    peeler = WorkspaceErrorPeeler()
    sample = """
panic: runtime error: invalid memory address or nil pointer dereference

goroutine 1 [running]:
main.process(...)
	/home/sajan/app/main.go:34 +0x26
"""
    findings = peeler.parse_traceback(sample)
    assert len(findings) == 1
    f = findings[0]
    assert f.language == "go"
    assert f.error_type == "Panic"
    assert f.line_number == 34


def test_ambient_vision_action_handler():
    sample = """
Traceback (most recent call last):
  File "C:\\Users\\sajan\\app.py", line 10, in <module>
    d["missing"]
KeyError: 'missing'
"""
    res = ambient_vision({"action": "peel_error", "text": sample, "project": "Zaya"})
    assert res.status == "success"
    assert "KeyError" in res.summary
    assert res.data["has_errors"] is True
    assert len(res.data["findings"]) == 1

    # Unauthorized access check
    with with_trust(TRUST_EXTERNAL_MESSAGE):
        with pytest.raises(PermissionError):
            ambient_vision({"action": "peel_error", "text": sample})
