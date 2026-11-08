"""Tests for Scratch Sandbox and Scratch Eval Action.
Created and developed by Sajan Rai for Zaya.
"""
from __future__ import annotations

import tempfile
from pathlib import Path
import pytest

from core.execution_policy import TRUST_EXTERNAL_MESSAGE, with_trust
from core.scratch_sandbox import ScratchSandbox
from actions.scratch_eval import scratch_eval


@pytest.fixture
def temp_sandbox():
    with tempfile.TemporaryDirectory() as td:
        sandbox = ScratchSandbox(scratch_dir=Path(td))
        yield sandbox


def test_successful_python_evaluation(temp_sandbox):
    sandbox = temp_sandbox
    code = """
import math
print(f"PI={math.pi:.4f}")
print("READY")
"""
    res = sandbox.eval_python(code, timeout=5.0)
    assert res.status == "success"
    assert res.exit_code == 0
    assert "PI=3.1416" in res.stdout
    assert "READY" in res.stdout
    assert res.duration_ms > 0.0


def test_python_runtime_error(temp_sandbox):
    sandbox = temp_sandbox
    code = """
x = 10 / 0
"""
    res = sandbox.eval_python(code, timeout=5.0)
    assert res.status == "error"
    assert res.exit_code != 0
    assert "ZeroDivisionError" in res.stderr


def test_python_timeout(temp_sandbox):
    sandbox = temp_sandbox
    code = """
import time
time.sleep(5.0)
"""
    # Bound to 0.8s
    res = sandbox.eval_python(code, timeout=0.8)
    assert res.status == "timeout"
    assert "timed out" in res.stderr.lower()


def test_scratch_cleanup(temp_sandbox):
    sandbox = temp_sandbox
    # Create persistent scratch file with cleanup=False
    res = sandbox.eval_python("print('Hello')", cleanup=False)
    assert res.scratch_file is not None
    assert Path(res.scratch_file).exists()

    # Clean
    purged = sandbox.clean_scratch()
    assert purged >= 1
    assert not Path(res.scratch_file).exists()


def test_scratch_eval_action(temp_sandbox, monkeypatch):
    monkeypatch.setattr("actions.scratch_eval.get_scratch_sandbox", lambda: temp_sandbox)

    # Success run
    res = scratch_eval({
        "action": "eval_python",
        "code": "print(2 + 2)",
    })
    assert res.status == "success"
    assert "4" in res.data["stdout"]

    # Clean action
    res_clean = scratch_eval({"action": "clean"})
    assert res_clean.status == "success"

    # Unauthorized access check
    with with_trust(TRUST_EXTERNAL_MESSAGE):
        with pytest.raises(PermissionError):
            scratch_eval({"action": "eval_python", "code": "print('fail')"})
