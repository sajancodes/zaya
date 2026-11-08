"""Dynamic Scratch Sandbox & Script Evaluator Action for Zaya.
Created and developed by Sajan Rai.

Safely evaluates Python snippets, mathematical models, and data transformation scripts
with captured IO, execution time profiling, and sandbox isolation.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Any

from core.execution_policy import require_owner
from core.scratch_sandbox import get_scratch_sandbox
from core.tool_result import ToolResult


def scratch_eval(parameters: dict[str, Any], **_kwargs) -> ToolResult:
    """Execute dynamic code evaluation in the isolated scratch sandbox."""
    require_owner()
    action = str(parameters.get("action", "eval_python")).lower().strip()
    sandbox = get_scratch_sandbox()

    if action == "eval_python":
        code = str(parameters.get("code", "")).strip()
        if not code:
            return ToolResult("failed", "Parameter 'code' is required for Python evaluation.", {})

        timeout = float(parameters.get("timeout", 5.0))
        cleanup = bool(parameters.get("cleanup", True))

        res = sandbox.eval_python(code=code, timeout=timeout, cleanup=cleanup)

        if res.status == "success":
            summary = f"Code executed successfully in {res.duration_ms}ms (exit code 0)."
            evidence = [{"source": "scratch_sandbox", "exit_code": 0, "duration_ms": res.duration_ms}]
            return ToolResult("success", summary, asdict(res), evidence=evidence)
        elif res.status == "timeout":
            summary = f"Code evaluation timed out: {res.stderr}"
            return ToolResult("failed", summary, asdict(res))
        else:
            summary = f"Code execution failed (exit code {res.exit_code}): {res.stderr}"
            return ToolResult("failed", summary, asdict(res))

    elif action == "clean":
        purged = sandbox.clean_scratch()
        return ToolResult("success", f"Purged {purged} scratch artifact(s) from sandbox.", {"purged_count": purged})

    return ToolResult("failed", f"Unknown action '{action}'. Valid actions are 'eval_python', 'clean'.", {})


TOOL = {
    "name": "scratch_eval",
    "description": (
        "Evaluate dynamic Python code snippets, mathematical algorithms, or data transforms "
        "in an isolated, bounded scratch sandbox. Captures stdout, stderr, and execution duration."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["eval_python", "clean"],
                "description": "Action to perform: 'eval_python' (default) or 'clean'.",
            },
            "code": {
                "type": "STRING",
                "description": "Python code snippet to execute (required for 'eval_python').",
            },
            "timeout": {
                "type": "NUMBER",
                "description": "Maximum execution time in seconds (default: 5.0, max: 30.0).",
            },
            "cleanup": {
                "type": "BOOLEAN",
                "description": "Whether to automatically delete the scratch script after execution (default: true).",
            },
        },
        "required": [],
    },
    "handler": scratch_eval,
}
