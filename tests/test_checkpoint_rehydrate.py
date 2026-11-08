import json
from unittest.mock import patch

from core.project_awareness import ProjectAwarenessService, get_project_awareness


def test_simulated_checkpoint_reset_rehydrates_project(tmp_path):
    state_file = tmp_path / "project_state.json"
    state_file.write_text(json.dumps({
        "version": 1,
        "active_project": "ZayaCompanion",
        "last_known_project": "ZayaCompanion",
    }), encoding="utf-8")

    # Construct service targeting our test file
    service = ProjectAwarenessService(persisted_path=state_file)

    with patch("core.project_awareness._awareness", service), \
         patch("core.workspace_context.tracker.snapshot", return_value={"project_name": ""}):

        # Simulate checkpoint reset logic as found in main.py ~3312
        snap = get_project_awareness().rehydrate()
        assert snap["active_project"] == "ZayaCompanion"
        assert get_project_awareness().active_project() == "ZayaCompanion"
