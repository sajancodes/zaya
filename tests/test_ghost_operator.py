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


def test_ghost_operator_high_dpi_and_bezier():
    engine = GhostOperatorEngine()

    # Test metrics
    metrics = engine.get_display_metrics()
    assert "width" in metrics
    assert "height" in metrics
    assert "dpi" in metrics
    assert "scale_factor" in metrics
    assert metrics["scale_factor"] >= 1.0

    # Test coordinate mapping
    with patch.object(engine, "get_display_metrics", return_value={
        "virtual_left": 0,
        "virtual_top": 0,
        "virtual_width": 1920,
        "virtual_height": 1080,
        "dpi": 144,
        "scale_factor": 1.5,
    }):
        px, py = engine.map_vision_coordinate(0, 0)
        assert px == 0 and py == 0

        px, py = engine.map_vision_coordinate(500, 500)
        assert 950 <= px <= 970
        assert 530 <= py <= 550

        px, py = engine.map_vision_coordinate(1000, 1000)
        assert px == 1919 and py == 1079

    # Test Bezier trajectory
    traj = engine.generate_bezier_trajectory((100, 100), (500, 400), steps=10)
    assert len(traj) == 10
    assert traj[-1] == (500, 400)


def test_ghost_operator_action_metrics_and_norm():
    with patch("core.execution_policy.require_owner"):
        # Metrics action
        res_metrics = ghost_operator({"action": "metrics"})
        assert res_metrics.status == "success"
        assert "DPI" in res_metrics.summary

        # Move with normalized coordinates
        with patch("core.ghost_operator.GhostOperatorEngine.move_cursor", return_value=True) as mock_move, \
             patch("core.ghost_operator.GhostOperatorEngine.map_vision_coordinate", return_value=(960, 540)):
            res_move = ghost_operator({"action": "move", "normalized_x": 500, "normalized_y": 500})
            assert res_move.status == "success"
            assert "(960, 540)" in res_move.summary
            mock_move.assert_called_with(960, 540, smooth=True, bezier=True)

