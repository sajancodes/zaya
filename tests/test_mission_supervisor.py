"""Unit and integration tests for MissionSupervisor and mission_control tool."""
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
from core.mission_supervisor import Mission, MissionSupervisor
from actions.mission_control import mission_control


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
                    [{"id": 1, "description": "Step 1", "tool": "", "parameters": {}, "status": "pending", "result": "", "error": ""}],
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
                "steps": [{"id": i, "description": f"Step {i}", "tool": "", "parameters": {}} for i in range(1, 10)],
                "checks": [f"Check {i}" for i in range(1, 8)],
            }
            steps, checks = supervisor.plan_mission("Test large mission")
            self.assertLessEqual(len(steps), 5)
            self.assertLessEqual(len(checks), 4)

    def test_persistence_and_cancellation(self):
        supervisor = MissionSupervisor(store_path=self.store_path)
        token = trust_context.set(TRUST_AUTHENTICATED_REMOTE_OWNER)
        try:
            with patch.object(supervisor, "plan_mission") as mock_plan:
                mock_plan.return_value = (
                    [{"id": 1, "description": "Step 1", "tool": "", "parameters": {}, "status": "pending", "result": "", "error": ""}],
                    ["Check 1"]
                )
                m = supervisor.start_mission("Test persistent mission")
                # Cancel mission
                ok = supervisor.cancel_mission(m.id)
                self.assertTrue(ok)
                m_updated = supervisor.get_mission(m.id)
                self.assertEqual(m_updated.status, "cancelled")

                # Verify persistent reload
                supervisor2 = MissionSupervisor(store_path=self.store_path)
                m_reloaded = supervisor2.get_mission(m.id)
                self.assertIsNotNone(m_reloaded)
                self.assertEqual(m_reloaded.status, "cancelled")
        finally:
            trust_context.reset(token)

    def test_mission_control_action_dispatch(self):
        token = trust_context.set(TRUST_LOCAL_OWNER)
        try:
            # Start
            with patch("core.mission_supervisor._json_call", return_value={"steps": [{"id": 1, "description": "Step 1"}], "checks": ["Check 1"]}):
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

                # Cancel
                res_cancel = mission_control({"action": "cancel", "mission_id": mid})
                self.assertEqual(res_cancel.status, "success")
        finally:
            trust_context.reset(token)


if __name__ == "__main__":
    unittest.main()
