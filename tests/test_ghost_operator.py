from unittest.mock import patch, MagicMock
from core.ghost_operator import GhostOperatorEngine, get_ghost_operator
from actions.ghost_operator import ghost_operator


def test_ghost_operator_primitives():
    engine = GhostOperatorEngine()

    with patch("ctypes.windll.user32.SetCursorPos", return_value=1) as mock_set, \
         patch("ctypes.windll.user32.mouse_event") as mock_mouse:

        assert engine.set_cursor_pos(100, 200) is True
        mock_set.assert_called_with(100, 200)

        assert engine.click(button="left", x=150, y=250) is True
        assert mock_mouse.call_count >= 2

        assert engine.drag(10, 10, 50, 50, steps=2) is True
        assert engine.scroll(-3) is True


def test_ghost_operator_workflow():
    engine = GhostOperatorEngine()

    with patch.object(engine, "click", return_value=True) as mock_click, \
         patch.object(engine, "move_cursor", return_value=True) as mock_move:

        steps = [
            {"action": "move", "x": 100, "y": 200},
            {"action": "click", "x": 100, "y": 200},
            {"action": "wait", "ms": 50},
        ]

        result = engine.execute_workflow(steps)
        assert result["status"] == "success"
        assert result["steps_executed"] == 3
        mock_move.assert_called()
        mock_click.assert_called()


def test_ghost_operator_action():
    with patch("core.execution_policy.require_owner"):
        # Inspect
        res_inspect = ghost_operator({"action": "inspect"})
        assert res_inspect.status == "success"

        # Workflow
        with patch("core.ghost_operator.GhostOperatorEngine.execute_workflow") as mock_wf:
            mock_wf.return_value = {"status": "success", "steps_executed": 2, "logs": []}
            res_wf = ghost_operator({
                "action": "workflow",
                "steps": [{"action": "wait", "ms": 10}, {"action": "wait", "ms": 10}]
            })
            assert res_wf.status == "success"
            assert "completed 2 steps" in res_wf.summary
