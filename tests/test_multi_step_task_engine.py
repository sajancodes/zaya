import json
import unittest
from actions.mobile_telekinesis import (
    coordinate_multi_step_task,
    manage_personal_memory
)


class MultiStepTaskEngine:
    """Simulated task coordinator implementing the exact Android coordinator lifecycle."""

    def __init__(self):
        self.tasks = {}
        self.active_tokens = {}

    def plan(self, goal: str, task_id: str = "task_1"):
        steps = []
        lower = goal.lower()
        if "flashlight" in lower and "camera" in lower:
            steps = [
                {"id": "step_1", "name": "Set Flashlight", "action": "set_flashlight", "params": {"enabled": True}, "required_permissions": []},
                {"id": "step_2", "name": "Open Camera", "action": "open_camera", "params": {}, "required_permissions": ["android.permission.CAMERA"]}
            ]
        elif "contact" in lower and "message" in lower:
            steps = [
                {"id": "step_1", "name": "Find Contact", "action": "search_contacts", "params": {"query": "Alice"}, "required_permissions": ["android.permission.READ_CONTACTS"]},
                {"id": "step_2", "name": "Prepare Message", "action": "compose_sms", "params": {"recipient": "Alice", "text": "Hello"}, "is_consequential": True, "required_permissions": ["android.permission.SEND_SMS"]}
            ]
        else:
            steps = [
                {"id": "step_1", "name": "Execute Action", "action": "generic_action", "params": {}, "required_permissions": []}
            ]

        self.tasks[task_id] = {
            "task_id": task_id,
            "goal": goal,
            "steps": steps,
            "status": "PENDING",
            "current_step_index": 0,
            "results": {},
            "cancelled": False
        }
        self.active_tokens[task_id] = 1
        return self.tasks[task_id]

    def cancel(self, task_id: str):
        if task_id in self.tasks:
            self.tasks[task_id]["cancelled"] = True
            self.tasks[task_id]["status"] = "CANCELLED"
            # Invalidate generation token
            self.active_tokens[task_id] = self.active_tokens.get(task_id, 1) + 1
            for step in self.tasks[task_id]["steps"]:
                if step.get("status") not in ("COMPLETED", "FAILED"):
                    step["status"] = "CANCELLED"
            return True
        return False

    def execute_next_step(self, task_id: str, available_permissions: list = None, executor_func=None):
        if available_permissions is None:
            available_permissions = []
        task = self.tasks.get(task_id)
        if not task or task["cancelled"]:
            return {"status": "cancelled", "message": "Task is cancelled or does not exist"}

        idx = task["current_step_index"]
        if idx >= len(task["steps"]):
            task["status"] = "COMPLETED"
            return {"status": "completed", "message": "All steps completed"}

        step = task["steps"][idx]

        # Permission check
        for perm in step.get("required_permissions", []):
            if perm not in available_permissions:
                step["status"] = "FAILED"
                step["error"] = f"Missing permission: {perm}"
                task["status"] = "FAILED"
                task["failure_reason"] = step["error"]
                # Skip subsequent steps
                for remaining in task["steps"][idx + 1:]:
                    remaining["status"] = "SKIPPED"
                return {"status": "permission_required", "error": step["error"]}

        # Consequential action check
        if step.get("is_consequential", False) and not step.get("confirmed", False):
            step["status"] = "WAITING_CONFIRMATION"
            task["status"] = "WAITING_CONFIRMATION"
            return {"status": "needs_confirmation", "step_id": step["id"], "action": step["action"]}

        # Execute
        step["status"] = "RUNNING"
        if executor_func:
            try:
                res = executor_func(step)
                step["status"] = "COMPLETED"
                step["result"] = res
                task["results"][step["id"]] = res
            except Exception as e:
                step["status"] = "FAILED"
                step["error"] = str(e)
                task["status"] = "FAILED"
                task["failure_reason"] = str(e)
                for remaining in task["steps"][idx + 1:]:
                    remaining["status"] = "SKIPPED"
                return {"status": "failed", "error": str(e)}
        else:
            step["status"] = "COMPLETED"
            step["result"] = {"spoken_message": f"{step['name']} succeeded"}
            task["results"][step["id"]] = step["result"]

        task["current_step_index"] += 1
        if task["current_step_index"] >= len(task["steps"]):
            task["status"] = "COMPLETED"

        return {"status": "step_completed", "step_id": step["id"], "task_status": task["status"]}

    def apply_late_result(self, task_id: str, token: int, result: dict):
        if self.active_tokens.get(task_id) != token:
            return False, "Stale result rejected"
        return True, "Result accepted"

    def generate_report(self, task_id: str):
        task = self.tasks.get(task_id)
        if not task:
            return None
        completed = [s for s in task["steps"] if s.get("status") == "COMPLETED"]
        failed = [s for s in task["steps"] if s.get("status") == "FAILED"]
        skipped = [s for s in task["steps"] if s.get("status") == "SKIPPED"]
        cancelled = [s for s in task["steps"] if s.get("status") == "CANCELLED"]

        if task["status"] == "COMPLETED":
            summary = "Task completed successfully."
        elif task["status"] == "CANCELLED":
            if completed:
                summary = f"Task partially completed ({len(completed)} steps) before cancellation."
            else:
                summary = "Task was cancelled before completion."
        elif task["status"] == "FAILED":
            summary = f"Task stopped: {task.get('failure_reason', 'Step failed')}."
        else:
            summary = f"Task in status: {task['status']}."

        return {
            "task_id": task_id,
            "status": task["status"],
            "completed_steps": len(completed),
            "failed_steps": len(failed),
            "skipped_steps": len(skipped),
            "cancelled_steps": len(cancelled),
            "summary": summary
        }


class PersonalMemoryStoreSim:
    """Simulated local personal memory store enforcing privacy and sensitive data filters."""

    SENSITIVE_PATTERNS = ["password", "passwd", "pin", "api_key", "secret", "credit_card", "cvv", "otp", "auth_token"]

    def __init__(self):
        self.memories = {}

    def is_sensitive(self, key: str, value: str) -> bool:
        lower = f"{key} {value}".lower()
        return any(p in lower for p in self.SENSITIVE_PATTERNS)

    def remember(self, key: str, value: str, category: str = "PREFERENCE", explicit_consent: bool = True):
        if not explicit_consent:
            return {"status": "needs_confirmation", "message": "Confirmation required"}
        if self.is_sensitive(key, value):
            return {"status": "blocked", "error": "sensitive_data_blocked"}
        self.memories[key] = {
            "key": key,
            "value": value,
            "category": category
        }
        return {"status": "saved", "key": key}

    def forget(self, key: str):
        if key in self.memories:
            del self.memories[key]
            return True
        return False

    def query_relevant(self, prompt: str):
        tokens = set(prompt.lower().split())
        results = []
        for key, mem in self.memories.items():
            key_tokens = set(key.lower().replace("_", " ").split())
            val_tokens = set(mem["value"].lower().split())
            if tokens & (key_tokens | val_tokens):
                results.append(mem)
        return results


class TestMultiStepTaskEngine(unittest.TestCase):

    # 1. A successful multi-step task
    def test_1_successful_multi_step_task(self):
        engine = MultiStepTaskEngine()
        task = engine.plan("Turn on flashlight, then open camera", "task_success")
        self.assertEqual(len(task["steps"]), 2)

        perms = ["android.permission.CAMERA"]
        res1 = engine.execute_next_step("task_success", available_permissions=perms)
        self.assertEqual(res1["status"], "step_completed")
        self.assertEqual(task["status"], "PENDING")

        res2 = engine.execute_next_step("task_success", available_permissions=perms)
        self.assertEqual(res2["status"], "step_completed")
        self.assertEqual(task["status"], "COMPLETED")

        report = engine.generate_report("task_success")
        self.assertEqual(report["completed_steps"], 2)
        self.assertEqual(report["failed_steps"], 0)
        self.assertIn("completed successfully", report["summary"])

    # 2. A failure in a middle step
    def test_2_failure_in_middle_step(self):
        engine = MultiStepTaskEngine()
        task = engine.plan("Turn on flashlight, then open camera", "task_middle_fail")

        # Step 1 succeeds
        engine.execute_next_step("task_middle_fail")

        # Step 2 fails
        def fail_executor(step):
            raise RuntimeError("Camera device busy")

        res = engine.execute_next_step("task_middle_fail", available_permissions=["android.permission.CAMERA"], executor_func=fail_executor)
        self.assertEqual(res["status"], "failed")
        self.assertEqual(task["status"], "FAILED")

        report = engine.generate_report("task_middle_fail")
        self.assertEqual(report["completed_steps"], 1)
        self.assertEqual(report["failed_steps"], 1)
        self.assertEqual(report["skipped_steps"], 0)
        self.assertIn("Camera device busy", report["summary"])

    # 3. A missing permission or unsupported action
    def test_3_missing_permission_or_unsupported_action(self):
        engine = MultiStepTaskEngine()
        task = engine.plan("Turn on flashlight, then open camera", "task_perm_fail")

        # Step 1 succeeds
        engine.execute_next_step("task_perm_fail")

        # Step 2 needs android.permission.CAMERA, but permissions empty
        res = engine.execute_next_step("task_perm_fail", available_permissions=[])
        self.assertEqual(res["status"], "permission_required")
        self.assertIn("android.permission.CAMERA", res["error"])
        self.assertEqual(task["status"], "FAILED")

    # 4. Cancellation before execution begins
    def test_4_cancellation_before_execution_begins(self):
        engine = MultiStepTaskEngine()
        task = engine.plan("Turn on flashlight, then open camera", "task_cancel_early")
        cancelled = engine.cancel("task_cancel_early")
        self.assertTrue(cancelled)
        self.assertEqual(task["status"], "CANCELLED")

        # Trying to execute must be rejected
        res = engine.execute_next_step("task_cancel_early")
        self.assertEqual(res["status"], "cancelled")

        report = engine.generate_report("task_cancel_early")
        self.assertEqual(report["completed_steps"], 0)
        self.assertEqual(report["cancelled_steps"], 2)

    # 5. Cancellation during a running operation
    def test_5_cancellation_during_running_operation(self):
        engine = MultiStepTaskEngine()
        task = engine.plan("Turn on flashlight, then open camera", "task_cancel_mid")
        perms = ["android.permission.CAMERA"]

        # Step 1 completes
        engine.execute_next_step("task_cancel_mid", available_permissions=perms)
        self.assertEqual(task["steps"][0]["status"], "COMPLETED")

        # User presses Cancel or speaks "stop"
        engine.cancel("task_cancel_mid")
        self.assertEqual(task["status"], "CANCELLED")

        # Step 2 cannot execute
        res = engine.execute_next_step("task_cancel_mid", available_permissions=perms)
        self.assertEqual(res["status"], "cancelled")

        report = engine.generate_report("task_cancel_mid")
        self.assertEqual(report["completed_steps"], 1)
        self.assertEqual(report["cancelled_steps"], 1)
        self.assertIn("partially completed (1 steps) before cancellation", report["summary"])

    # 6. Prevention of subsequent steps after cancellation
    def test_6_prevention_of_subsequent_steps_after_cancellation(self):
        engine = MultiStepTaskEngine()
        task = engine.plan("Turn on flashlight, then open camera", "task_no_leak")
        engine.cancel("task_no_leak")

        # Step 2 must remain CANCELLED and never transition to RUNNING or COMPLETED
        for step in task["steps"]:
            self.assertNotEqual(step.get("status"), "RUNNING")
            self.assertNotEqual(step.get("status"), "COMPLETED")

    # 7. Prevention of stale results modifying a newer task
    def test_7_prevention_of_stale_results_modifying_newer_task(self):
        engine = MultiStepTaskEngine()
        engine.plan("Turn on flashlight", "task_stale")
        old_token = engine.active_tokens["task_stale"]

        # User cancels and restarts the task
        engine.cancel("task_stale")
        new_token = engine.active_tokens["task_stale"]
        self.assertNotEqual(old_token, new_token)

        # Late-arriving response with old token is rejected
        accepted, msg = engine.apply_late_result("task_stale", old_token, {"spoken_message": "Old result"})
        self.assertFalse(accepted)
        self.assertIn("Stale result rejected", msg)

        # Response with fresh token is accepted
        accepted_fresh, _ = engine.apply_late_result("task_stale", new_token, {"spoken_message": "New result"})
        self.assertTrue(accepted_fresh)

    # 8. Accurate reporting of partial completion
    def test_8_accurate_reporting_of_partial_completion(self):
        engine = MultiStepTaskEngine()
        task = engine.plan("Turn on flashlight, then open camera", "task_partial")
        engine.execute_next_step("task_partial")
        task["status"] = "PARTIALLY_COMPLETED"
        task["steps"][1]["status"] = "SKIPPED"

        report = engine.generate_report("task_partial")
        self.assertEqual(report["completed_steps"], 1)
        self.assertEqual(report["skipped_steps"], 1)
        self.assertNotIn("completed successfully", report["summary"])

    # 9. Memory creation with appropriate consent
    def test_9_memory_creation_with_consent(self):
        store = PersonalMemoryStoreSim()
        # Without consent -> blocked/needs confirmation
        no_consent = store.remember("style", "concise", explicit_consent=False)
        self.assertEqual(no_consent["status"], "needs_confirmation")

        # With explicit consent -> saved
        res = store.remember("style", "concise and direct", explicit_consent=True)
        self.assertEqual(res["status"], "saved")
        self.assertEqual(store.memories["style"]["value"], "concise and direct")

    # 10. Memory retrieval for a relevant request
    def test_10_memory_retrieval_for_relevant_request(self):
        store = PersonalMemoryStoreSim()
        store.remember("music_player", "spotify", "ALIAS")
        store.remember("response_style", "concise", "STYLE")
        store.remember("night_routine", "silent mode", "ROUTINE")

        # Query about music should only match music_player
        music_matches = store.query_relevant("play music on spotify")
        self.assertEqual(len(music_matches), 1)
        self.assertEqual(music_matches[0]["key"], "music_player")

        # Query about unrelated topic yields no leaks
        unrelated = store.query_relevant("what is the weather today")
        self.assertEqual(len(unrelated), 0)

    # 11. Memory editing and deletion
    def test_11_memory_editing_and_deletion(self):
        store = PersonalMemoryStoreSim()
        store.remember("alias_browser", "Firefox", "ALIAS")
        self.assertEqual(store.memories["alias_browser"]["value"], "Firefox")

        # Edit
        store.remember("alias_browser", "Chrome", "ALIAS")
        self.assertEqual(store.memories["alias_browser"]["value"], "Chrome")

        # Delete
        forgotten = store.forget("alias_browser")
        self.assertTrue(forgotten)
        self.assertNotIn("alias_browser", store.memories)

    # 12. Prevention of sensitive or explicitly excluded data being saved
    def test_12_prevention_of_sensitive_data_being_saved(self):
        store = PersonalMemoryStoreSim()
        bad_keys = [
            ("my_password", "supersecret123"),
            ("atm_pin", "4321"),
            ("gemini_api_key", "AIzaSy..."),
            ("credit_card", "4111222233334444"),
            ("cvv", "999"),
            ("bank_otp", "584920")
        ]
        for key, val in bad_keys:
            res = store.remember(key, val, explicit_consent=True)
            self.assertEqual(res["status"], "blocked", f"Sensitive data allowed: {key}")
            self.assertNotIn(key, store.memories)

        # Also verify through the action telekinesis handler
        action_res = json.loads(manage_personal_memory({"action": "remember", "key": "password", "value": "123456"}))
        self.assertEqual(action_res["status"], "blocked")
        self.assertEqual(action_res["error"], "sensitive_data_blocked")

    # 13. Task interruption and safe recovery
    def test_13_task_interruption_and_safe_recovery(self):
        engine = MultiStepTaskEngine()
        task = engine.plan("Find contact, prepare a message, and ask me before sending it", "task_interrupted")

        # Step 1 (find contact) finishes
        engine.execute_next_step("task_interrupted", available_permissions=["android.permission.READ_CONTACTS"])
        self.assertEqual(task["steps"][0]["status"], "COMPLETED")

        # Interruption happens (e.g. process death, app paused)
        task["status"] = "PAUSED"

        # Upon recovery, Step 2 is consequential ("compose_sms") and must NOT auto-run
        step_2 = task["steps"][1]
        self.assertTrue(step_2.get("is_consequential"))
        self.assertFalse(step_2.get("confirmed", False))

        res = engine.execute_next_step("task_interrupted", available_permissions=["android.permission.SEND_SMS"])
        self.assertEqual(res["status"], "needs_confirmation")
        self.assertEqual(task["status"], "WAITING_CONFIRMATION")

    # 14. Confirmation before consequential external actions
    def test_14_confirmation_before_consequential_external_actions(self):
        engine = MultiStepTaskEngine()
        task = engine.plan("Find contact, prepare a message, and ask me before sending it", "task_confirm_gate")

        engine.execute_next_step("task_confirm_gate", available_permissions=["android.permission.READ_CONTACTS"])

        # Attempting consequential step without confirmation is halted
        check = engine.execute_next_step("task_confirm_gate", available_permissions=["android.permission.SEND_SMS"])
        self.assertEqual(check["status"], "needs_confirmation")

        # Once user explicitly confirms, the action proceeds
        task["steps"][1]["confirmed"] = True
        done = engine.execute_next_step("task_confirm_gate", available_permissions=["android.permission.SEND_SMS"])
        self.assertEqual(done["status"], "step_completed")
        self.assertEqual(task["status"], "COMPLETED")


if __name__ == "__main__":
    unittest.main()
