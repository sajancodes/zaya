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


def test_custom_skill_duplicate_collision_and_safe_replacement(tmp_path):
    from core.action_loader import discover_actions, get_action_registry
    synth = SkillSynthesizer(actions_dir=tmp_path)

    v1_code = """
def custom_worker(parameters: dict, **_kwargs) -> ToolResult:
    return ToolResult("success", "v1 output", data={"version": 1})
"""
    v2_code = """
def custom_worker(parameters: dict, **_kwargs) -> ToolResult:
    return ToolResult("success", "v2 output", data={"version": 2})
"""
    broken_code = """
def custom_worker(parameters: dict, **_kwargs) -> ToolResult:
    raise RuntimeError("Intentional broken replacement")
"""
    params = {"type": "OBJECT", "properties": {}}

    with patch("core.execution_policy.require_owner"):
        # 1. Register new custom tool v1
        res1 = synth.synthesize(
            name="worker",
            description="Worker v1",
            parameters=params,
            python_code=v1_code,
            test_parameters={},
        )
        assert res1["status"] == "success"
        assert res1["name"] == "custom_worker"
        assert "v1 output" in str(res1["test_result"])

        # 2. Attempt duplicate registration without replace=True -> Must fail
        res_dup = synth.synthesize(
            name="worker",
            description="Worker v2 duplicate attempt",
            parameters=params,
            python_code=v2_code,
            replace=False,
        )
        assert res_dup["status"] == "failed"
        assert "Collision" in res_dup["error"]
        assert "replace=True" in res_dup["error"]

        # Ensure v1 is still active
        reg = get_action_registry(tmp_path)
        out_v1 = reg.run("custom_worker", {})
        assert "v1 output" in str(out_v1)

        # 3. Failed replacement with broken code -> Must rollback to v1!
        res_bad_rep = synth.synthesize(
            name="worker",
            description="Worker broken replacement",
            parameters=params,
            python_code=broken_code,
            test_parameters={},
            replace=True,
        )
        assert res_bad_rep["status"] == "failed"

        # Verify rollback preserved v1
        out_v1_post_rollback = reg.run("custom_worker", {})
        assert "v1 output" in str(out_v1_post_rollback)

        # 4. Explicit replacement with working v2 -> Succeeds
        res2 = synth.synthesize(
            name="worker",
            description="Worker v2",
            parameters=params,
            python_code=v2_code,
            test_parameters={},
            replace=True,
        )
        assert res2["status"] == "success"
        out_v2 = reg.run("custom_worker", {})
        assert "v2 output" in str(out_v2)

        # 5. Rediscovery across restart (discover_actions)
        new_reg = discover_actions(tmp_path, logger=lambda _: None)
        assert new_reg.has("custom_worker")
        out_reloaded = new_reg.run("custom_worker", {})
        assert "v2 output" in str(out_reloaded)

        # 6. Module preservation when another skill shares or unregister happens
        reg.register_action(reg._actions["custom_worker"], allow_replace=True)
        # Attempting unregister on built-in fails
        reg._builtin_names.add("custom_worker_fake_core")
        assert reg.unregister_action("custom_worker_fake_core") is False

        # 7. Clean removal
        rem = synth.remove_skill("worker")
        assert rem["status"] == "success"
        assert rem["deleted"] is True
        assert not reg.has("custom_worker")


