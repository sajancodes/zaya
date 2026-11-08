from pathlib import Path
from unittest.mock import patch
from core.skill_synthesizer import SkillSynthesizer
from actions.synthesize_skill import synthesize_skill


def test_validate_code_safety():
    synth = SkillSynthesizer()
    ok, _ = synth.validate_code_safety("def foo():\n    return 42\n")
    assert ok is True

    bad_syntax, err = synth.validate_code_safety("def foo(: return")
    assert bad_syntax is False
    assert "Syntax error" in err


def test_synthesize_and_execute_skill(tmp_path):
    synth = SkillSynthesizer(actions_dir=tmp_path)

    tool_code = """
def custom_adder(parameters: dict, **_kwargs) -> ToolResult:
    a = parameters.get("a", 0)
    b = parameters.get("b", 0)
    return ToolResult("success", f"Sum is {a + b}", data={"sum": a + b})
"""
    params = {
        "type": "OBJECT",
        "properties": {
            "a": {"type": "INTEGER"},
            "b": {"type": "INTEGER"},
        }
    }

    with patch("core.execution_policy.require_owner"):
        result = synth.synthesize(
            name="adder",
            description="Adds two numbers",
            parameters=params,
            python_code=tool_code,
            test_parameters={"a": 10, "b": 32},
        )

        assert result["status"] == "success"
        assert result["name"] == "custom_adder"
        assert "Sum is 42" in str(result["test_result"])

        # Check skill listing
        skills = synth.list_skills()
        assert any(s["name"] == "custom_adder" for s in skills)

        # Check removal
        rem = synth.remove_skill("adder")
        assert rem["status"] == "success"
        assert rem["deleted"] is True
        assert not (tmp_path / "custom_adder.py").exists()


def test_synthesize_skill_action(tmp_path):
    synth = SkillSynthesizer(actions_dir=tmp_path)
    with patch("actions.synthesize_skill.get_skill_synthesizer", return_value=synth), \
         patch("core.execution_policy.require_owner"):

        # Create
        res = synthesize_skill({
            "action": "create",
            "name": "multiplier",
            "description": "Multiplies numbers",
            "parameters": {"type": "OBJECT", "properties": {}},
            "python_code": "def custom_multiplier(parameters: dict, **_kwargs):\n    return ToolResult('success', 'Multiplied', data={'val': 100})",
            "test_parameters": {}
        })
        assert res.status == "success"

        # List
        res_list = synthesize_skill({"action": "list"})
        assert res_list.status == "success"
        assert len(res_list.data["skills"]) >= 1

        # Remove
        res_rem = synthesize_skill({"action": "remove", "name": "multiplier"})
        assert res_rem.status == "success"


def test_synthesizer_collision_and_schema_validation(tmp_path):
    synth = SkillSynthesizer(actions_dir=tmp_path)

    # 1. Invalid parameter schema (not an object)
    res_bad_schema = synth.synthesize(
        name="test_tool",
        description="desc",
        parameters="not_a_dict",
        python_code="def custom_test_tool(p, **kw): pass",
    )
    assert res_bad_schema["status"] == "failed"
    assert "parameters must be a dictionary" in res_bad_schema["error"]

    # 2. Invalid parameter schema (missing type OBJECT)
    res_bad_type = synth.synthesize(
        name="test_tool",
        description="desc",
        parameters={"type": "ARRAY", "properties": {}},
        python_code="def custom_test_tool(p, **kw): pass",
    )
    assert res_bad_type["status"] == "failed"
    assert "'type': 'OBJECT'" in res_bad_type["error"]

    # 3. Built-in collision protection
    from core.action_loader import get_action_registry
    registry = get_action_registry(tmp_path)
    registry._builtin_names.add("terminal_exec")
    registry._builtin_names.add("open_app")

    res_collision = synth.synthesize(
        name="terminal_exec",
        description="attempt overwrite",
        parameters={"type": "OBJECT", "properties": {}},
        python_code="def custom_terminal_exec(p, **kw): pass",
    )
    assert res_collision["status"] == "failed"
    assert "Collision" in res_collision["error"]
    assert "immutable" in res_collision["error"]

    # 4. Built-in unregister protection
    assert registry.unregister_action("terminal_exec") is False

