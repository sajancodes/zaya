"""Unit and integration tests for MissionSupervisor and mission_control tool."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from core.execution_policy import (
    TRUST_AUTHENTICATED_REMOTE_OWNER,
    TRUST_LOCAL_OWNER,
    TRUST_WEB_CONTENT,
    trust_context,
)
from core.mission_supervisor import (
    Mission,
    MissionSupervisor,
    classify_goal_scope,
    validate_step,
    MISSION_ALLOWED_TOOLS,
)
from actions.mission_control import mission_control
from core.tool_result import ToolResult


class TestMissionSupervisor(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.store_path = Path(self.tmp_dir.name) / "missions.json"

    def tearDown(self):
        try:
            self.tmp_dir.cleanup()
        except Exception:
            pass

    def test_trust_enforcement(self):
        supervisor = MissionSupervisor(store_path=self.store_path)

        # External untrusted context must be rejected
        token = trust_context.set(TRUST_WEB_CONTENT)
        try:
            with self.assertRaises(PermissionError):
                supervisor.start_mission("Download untrusted script")
        finally:
            trust_context.reset(token)

        # Owner context allowed
        token = trust_context.set(TRUST_LOCAL_OWNER)
        try:
            with patch.object(supervisor, "plan_mission") as mock_plan:
                mock_plan.return_value = (
                    [{"id": 1, "description": "Step 1", "tool": "system_diagnostics", "parameters": {}, "status": "pending", "result": "", "error": ""}],
                    ["Check 1"]
                )
                m = supervisor.start_mission("Clean temp files")
                self.assertIsNotNone(m.id)
                self.assertEqual(m.trust_level, TRUST_LOCAL_OWNER)
                self.assertEqual(len(m.steps), 1)
        finally:
            trust_context.reset(token)

    def test_plan_bounds(self):
        supervisor = MissionSupervisor(store_path=self.store_path)
        with patch("core.mission_supervisor._json_call") as mock_call:
            # Return over 5 steps and over 4 checks
            mock_call.return_value = {
                "steps": [{"id": i, "description": f"Step {i}", "tool": "system_diagnostics", "parameters": {}} for i in range(1, 10)],
                "checks": [f"Check {i}" for i in range(1, 8)],
            }
            steps, checks = supervisor.plan_mission("Test large mission")
            self.assertLessEqual(len(steps), 5)
            self.assertLessEqual(len(checks), 4)

    def test_scope_classification_and_escalation_rejection(self):
        # Read-only diagnosis goal
        scope_read = classify_goal_scope("Check why my PC is slow")
        self.assertIn("inspect_system", scope_read)
        self.assertNotIn("delete", scope_read)
        self.assertNotIn("git_push", scope_read)
        self.assertNotIn("terminate_process", scope_read)

        # Explicit terminate goal
        scope_kill = classify_goal_scope("Find what is using RAM and kill the offending process")
        self.assertIn("terminate_process", scope_kill)

        # Tool outside goal scope must be rejected
        err = validate_step("terminate_app", {"app_name": "chrome.exe"}, scope_read)
        self.assertIn("requires operation classes", err)

        # Git control on read-only goal must be rejected if git action is not in scope
        err_git = validate_step("terminal_exec", {"command": "dir"}, scope_read)
        self.assertIn("requires operation classes", err_git)

    def test_tool_allowlist_and_parameter_validation(self):
        scope = {"read", "write_files", "inspect_system", "run_command", "delete"}

        # Unknown / unallowed tool rejected
        err_unallowed = validate_step("unregistered_dangerous_tool", {}, scope)
        self.assertIn("not in the mission allowed tools set", err_unallowed)

        # Empty tool rejected
        err_empty = validate_step("", {}, scope)
        self.assertIn("Empty tool name", err_empty)

        # Missing required parameter for session_activity
        err_missing = validate_step("session_activity", {}, scope)
        self.assertIn("Missing required parameter 'action'", err_missing)

        # Invalid enum parameter for session_activity
        err_enum = validate_step("session_activity", {"action": "invalid_action"}, scope)
        self.assertIn("Invalid value 'invalid_action' for 'action'", err_enum)

        # Valid step accepted
        err_valid = validate_step("system_diagnostics", {}, scope)
        self.assertIsNone(err_valid)

    def test_verification_checks(self):
        supervisor = MissionSupervisor(store_path=self.store_path)
        m = Mission(id="test_verif", goal="Create test file")

        # Create a temp file to verify
        test_file = Path(self.tmp_dir.name) / "output.txt"
        test_file.write_text("ok")

        # 1. Existing file passes verification
        m.checks = [f"File exists: {test_file}"]
        m.steps = [{"id": 1, "description": "Write", "tool": "file_processor", "status": "completed", "result": "done"}]
        supervisor._missions[m.id] = m
        supervisor._review_and_verify_mission(m.id)
        self.assertEqual(m.status, "completed")
        self.assertIn("Verified", m.summary)

        # 2. Missing file fails verification -> completed_unverified
        m.status = "running"
        m.round_number = 3  # exhaust review rounds
        m.checks = [f"File exists: {Path(self.tmp_dir.name) / 'missing.txt'}"]
        supervisor._review_and_verify_mission(m.id)
        self.assertEqual(m.status, "completed_unverified")
        self.assertIn("inconclusive", m.summary)

    def test_confirmation_pausing_and_continue(self):
        supervisor = MissionSupervisor(store_path=self.store_path)
        token = trust_context.set(TRUST_LOCAL_OWNER)
        try:
            m = Mission(
                id="m-confirm",
                goal="Kill bad process",
                status="running",
                steps=[{"id": 1, "description": "Kill process", "tool": "terminate_app", "parameters": {"app": "calc.exe"}, "status": "pending"}],
                checks=["Check process dead"],
            )
            supervisor._missions[m.id] = m

            # Execute step when confirmation is needed
            with patch("memory.config_manager.get_auto_execute_enabled", return_value=False):
                supervisor.execute_step_sync(m.id)

            # Should be in waiting_confirmation state
            self.assertEqual(m.status, "waiting_confirmation")
            self.assertIsNotNone(m.pending_confirmation)

            # Continue with approved=False cancels the mission
            supervisor.continue_mission(m.id, approved=False)
            self.assertEqual(m.status, "cancelled")

            # Reset mission and test approved=True
            m2 = Mission(
                id="m-confirm-2",
                goal="Kill bad process 2",
                status="waiting_confirmation",
                steps=[{"id": 1, "description": "Kill process", "tool": "terminate_app", "parameters": {"app": "calc.exe"}, "status": "pending"}],
                checks=[],
                pending_confirmation={"step_id": 1, "tool": "terminate_app", "parameters": {"app": "calc.exe"}},
            )
            supervisor._missions[m2.id] = m2

            with patch.object(supervisor, "_spawn_worker") as mock_spawn:
                supervisor.continue_mission(m2.id, approved=True)
                mock_spawn.assert_called_once()
                self.assertEqual(m2.status, "running")
                self.assertIsNone(m2.pending_confirmation)
        finally:
            trust_context.reset(token)

    def test_crash_recovery_and_corrupt_persistence(self):
        # 1. Test restart recovery
        missions_data = {
            "m_run": {
                "id": "m_run",
                "goal": "running mission",
                "status": "running",
                "current_step": 1,
                "steps": [],
                "checks": [],
                "created_at": 100.0,
                "updated_at": 100.0,
            },
            "m_wait": {
                "id": "m_wait",
                "goal": "waiting mission",
                "status": "waiting_confirmation",
                "current_step": 1,
                "steps": [],
                "checks": [],
                "created_at": 100.0,
                "updated_at": 100.0,
            }
        }
        self.store_path.write_text(json.dumps(missions_data))
        supervisor = MissionSupervisor(store_path=self.store_path)
        self.assertEqual(supervisor.get_mission("m_run").status, "interrupted")
        self.assertEqual(supervisor.get_mission("m_wait").status, "paused")

        # 2. Corrupt JSON recovery
        self.store_path.write_text("invalid json {{{{{")
        supervisor_corrupt = MissionSupervisor(store_path=self.store_path)
        self.assertEqual(len(supervisor_corrupt.list_missions()), 0)

    def test_history_pruning(self):
        supervisor = MissionSupervisor(store_path=self.store_path)
        # Add 160 finished missions
        for i in range(160):
            m = Mission(id=f"m_{i:03d}", goal=f"goal {i}", status="completed")
            supervisor._missions[m.id] = m
        supervisor._prune_history(keep=150)
        self.assertLessEqual(len(supervisor._missions), 150)

    def test_mission_control_actions(self):
        token = trust_context.set(TRUST_LOCAL_OWNER)
        try:
            # Start
            with patch("core.mission_supervisor._json_call", return_value={"steps": [{"id": 1, "description": "Step 1", "tool": "system_diagnostics", "parameters": {}}], "checks": ["Check 1"]}):
                res = mission_control({"action": "start", "goal": "Verify system health"})
                self.assertEqual(res.status, "success")
                self.assertIn("mission", res.data)
                mid = res.data["mission"]["id"]

                # Status
                res_status = mission_control({"action": "status", "mission_id": mid})
                self.assertEqual(res_status.status, "success")

                # List
                res_list = mission_control({"action": "list"})
                self.assertEqual(res_list.status, "success")
                self.assertGreaterEqual(len(res_list.data["missions"]), 1)

                # Set mission to paused so continue succeeds
                m = get_supervisor_mission = None
                from core.mission_supervisor import get_supervisor
                sup = get_supervisor()
                mission_obj = sup.get_mission(mid)
                if mission_obj:
                    mission_obj.status = "paused"

                # Continue
                res_cont = mission_control({"action": "continue", "mission_id": mid, "approved": True})
                self.assertEqual(res_cont.status, "success")

                # Cancel
                res_cancel = mission_control({"action": "cancel", "mission_id": mid})
                self.assertEqual(res_cancel.status, "success")
        finally:
            trust_context.reset(token)


if __name__ == "__main__":
    unittest.main()
