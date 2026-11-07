"""Synthesize Skill Action Tool for Zaya.
Created and developed by Sajan Rai for Zaya.

Exposes runtime skill synthesis, self-testing, and dynamic tool management
to the model and autonomous agents.
"""
from __future__ import annotations

from core.execution_policy import require_owner
from core.skill_synthesizer import get_skill_synthesizer
from core.tool_result import ToolResult


def synthesize_skill(parameters: dict, **_kwargs) -> ToolResult:
    """Dynamically synthesizes, tests, lists, or removes custom skills/tools."""
    require_owner()
    action = str(parameters.get("action") or "create").lower().strip()
    synthesizer = get_skill_synthesizer()

    if action == "list":
        skills = synthesizer.list_skills()
        return ToolResult(
            "success",
            f"Found {len(skills)} custom synthesized skills.",
            data={"skills": skills},
        )

    if action == "remove":
        name = str(parameters.get("name") or "").strip()
        if not name:
            return ToolResult("failed", "Parameter 'name' is required to remove a skill.")
        res = synthesizer.remove_skill(name)
        status = res.get("status", "failed")
        return ToolResult(status, res.get("message", "Remove completed."), data=res, side_effect=True)

    # action == "create" / "synthesize"
    name = str(parameters.get("name") or "").strip()
    description = str(parameters.get("description") or f"Custom synthesized tool for {name}").strip()
    params = parameters.get("parameters") or {"type": "OBJECT", "properties": {}}
    code = str(parameters.get("python_code") or "").strip()
    test_params = parameters.get("test_parameters")

    if not name:
        return ToolResult("failed", "Parameter 'name' is required for skill synthesis.")
    if not code:
        return ToolResult("failed", "Parameter 'python_code' is required for skill synthesis.")

    res = synthesizer.synthesize(
        name=name,
        description=description,
        parameters=params,
        python_code=code,
        test_parameters=test_params,
    )

    if res.get("status") == "success":
        return ToolResult("success", res.get("message", "Skill created."), data=res, side_effect=True)
    return ToolResult("failed", res.get("error", "Skill synthesis failed."), data=res)


TOOL = {
    "name": "synthesize_skill",
    "description": "Synthesizes, tests, and hot-loads a new Python tool or skill into Zaya's live runtime. Enables creating on-the-fly capabilities for unhandled tasks.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["create", "list", "remove"],
                "description": "Action to perform: 'create' to synthesize a new tool, 'list' to show active custom tools, 'remove' to delete one."
            },
            "name": {
                "type": "STRING",
                "description": "Unique identifier for the new tool (e.g. 'currency_converter' or 'repo_summarizer')."
            },
            "description": {
                "type": "STRING",
                "description": "Clear explanation of what the tool does and when to call it."
            },
            "parameters": {
                "type": "OBJECT",
                "description": "Schema dict for Gemini parameters (must have 'type': 'OBJECT' and 'properties')."
            },
            "python_code": {
                "type": "STRING",
                "description": "Python source code defining the handler or execution logic."
            },
            "test_parameters": {
                "type": "OBJECT",
                "description": "Optional parameters to test-run the tool immediately after synthesis."
            }
        }
    },
    "handler": synthesize_skill
}
