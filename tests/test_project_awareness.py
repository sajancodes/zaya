import json
import time
from unittest.mock import patch

from core.project_awareness import ProjectAwarenessService


def test_project_active_with_no_process(tmp_path):
    persisted_path = tmp_path / "project_state.json"
    service = ProjectAwarenessService(persisted_path=persisted_path)

    # Empty task runtime and no running process, but project registered in project_index
    registered_mock = {
        "/path/to/project": {
            "name": "AlphaCore",
            "path": "/path/to/project",
            "aliases": ["alpha"],
            "last_seen": time.time(),
        }
    }

    index_mock = tmp_path / "projects.json"
    index_mock.write_text(json.dumps(registered_mock), encoding="utf-8")

    with patch("memory.project_index.INDEX_PATH", index_mock), \
         patch("core.workspace_context.tracker.snapshot", return_value={"project_name": ""}), \
         patch("core.task_runtime.get_runtime") as mock_runtime:
        mock_runtime.return_value.list.return_value = []
        snap = service.snapshot()
        assert snap["active_project"] == "AlphaCore"
        assert service.active_project() == "AlphaCore"


def test_conversation_does_not_set_active_project(tmp_path):
    persisted_path = tmp_path / "project_state.json"
    service = ProjectAwarenessService(persisted_path=persisted_path)

    # No workspace project, no registered project
    empty_index = tmp_path / "non_existent_projects.json"
    with patch("core.workspace_context.tracker.snapshot", return_value={"project_name": ""}), \
         patch("memory.project_index.INDEX_PATH", empty_index), \
         patch("memory.conversation_store.ConversationStore.recent", return_value=[
             {"id": 1, "role": "user", "text": "let's work on secret_super_app", "created": time.time()}
         ]):
        snap = service.snapshot()
        # Active project must NOT be inferred from conversation text alone
        assert snap["active_project"] == ""
        # But conversation rows should populate history
        assert len(snap["history"]) == 1
        assert snap["history"][0]["kind"] == "history"
        assert snap["history"][0]["stale"] is True


def test_workspace_sets_active_project(tmp_path):
    persisted_path = tmp_path / "project_state.json"
    service = ProjectAwarenessService(persisted_path=persisted_path)

    with patch("core.workspace_context.tracker.snapshot", return_value={
        "project_name": "BetaService",
        "process_name": "Code.exe",
        "window_title": "BetaService - Visual Studio Code",
        "changed_at": time.time(),
        "age_seconds": 10,
    }):
        snap = service.snapshot()
        assert snap["active_project"] == "BetaService"
        assert snap["last_known_project"] == "BetaService"

        # Verify it was persisted to disk
        assert persisted_path.exists()
        persisted_data = json.loads(persisted_path.read_text(encoding="utf-8"))
        assert persisted_data["active_project"] == "BetaService"


def test_rehydrate_restores_active_project(tmp_path):
    persisted_path = tmp_path / "project_state.json"
    persisted_path.write_text(json.dumps({
        "version": 1,
        "active_project": "GammaEngine",
        "last_known_project": "GammaEngine",
    }), encoding="utf-8")

    # Start a fresh service instance without live workspace
    service = ProjectAwarenessService(persisted_path=persisted_path)
    with patch("core.workspace_context.tracker.snapshot", return_value={"project_name": ""}):
        snap = service.rehydrate()
        assert snap["active_project"] == "GammaEngine"
        assert service.active_project() == "GammaEngine"


def test_conflicting_observations_reconciled_by_confidence(tmp_path):
    persisted_path = tmp_path / "project_state.json"
    service = ProjectAwarenessService(persisted_path=persisted_path)

    # Manual override has high confidence
    service.set_active_project("PriorityApp", source="manual", confidence=0.99)

    index_mock = tmp_path / "projects.json"
    index_mock.write_text(json.dumps({
        "/p": {"name": "OldApp", "path": "/p", "last_seen": 1000.0}
    }), encoding="utf-8")

    with patch("memory.project_index.INDEX_PATH", index_mock), \
         patch("core.workspace_context.tracker.snapshot", return_value={"project_name": ""}):
        snap = service.snapshot()
        assert snap["active_project"] == "PriorityApp"

def test_coding_job_running_process_detected(tmp_path):
    from unittest.mock import MagicMock
    persisted_path = tmp_path / "project_state.json"
    service = ProjectAwarenessService(persisted_path=persisted_path)

    mock_job = MagicMock()
    mock_job.project = "/Users/test/CodeProject"
    mock_job.phase = "working"
    mock_job.progress = "Editing files"
    mock_job.updated_at = time.time()

    mock_jobs = MagicMock()
    mock_jobs.execution_status.return_value = {
        "process_running": True,
        "worker_running": True,
        "pid": 4321,
    }
    mock_jobs.active.return_value = mock_job

    with patch("core.coding_jobs.get_jobs", return_value=mock_jobs), \
         patch("core.workspace_context.tracker.snapshot", return_value={"project_name": ""}):
        snap = service.snapshot()
        assert snap["running_process"] is not None
        assert snap["running_process"]["type"] == "opencode"
        assert snap["running_process"]["pid"] == 4321
        assert snap["active_project"] == "CodeProject"


def test_clear_active_project(tmp_path):
    persisted_path = tmp_path / "project_state.json"
    service = ProjectAwarenessService(persisted_path=persisted_path)
    service.set_active_project("SomeProject")
    assert service.active_project() == "SomeProject"

    service.clear_active_project()
    with patch("core.workspace_context.tracker.snapshot", return_value={"project_name": ""}), \
         patch("memory.project_index.INDEX_PATH", tmp_path / "empty.json"):
        assert service.active_project() == ""
