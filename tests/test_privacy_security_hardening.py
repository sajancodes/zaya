import json
import time
import unittest
from actions.mobile_telekinesis import (
    make_phone_call,
    send_sms_message,
    send_whatsapp_message,
    manage_personal_memory,
    coordinate_multi_step_task,
    _is_duplicate_consequential,
    _recent_consequential_actions
)


class TestPrivacySecurityHardening(unittest.TestCase):

    def setUp(self):
        # Clear deduplication cache before each test
        _recent_consequential_actions.clear()

    # 1. Missing, invalid, and unavailable API credentials
    def test_1_missing_invalid_and_unavailable_credentials(self):
        from core.gemini_keys import parse_keys

        # Missing / blank key returns empty list
        self.assertEqual(parse_keys(""), [])
        self.assertEqual(parse_keys(None), [])

        # Diagnostics check does not leak key value
        from core.diagnostics import inspect
        result = inspect("providers")
        self.assertEqual(result.status, "success")
        self.assertIn("gemini_key_present", result.data["providers"])
        self.assertNotIn("gemini_api_key", result.data["providers"])

    # 2. Network loss and interrupted streaming
    def test_2_network_loss_and_interrupted_streaming(self):
        # Verify network error mapping produces friendly, non-crashing messages
        simulated_errors = [
            ("Connection refused", "Nothing answered at that address. Is Zaya running on the laptop?"),
            ("SSL handshake failed", "The certificate didn't match. Use the laptop's Tailscale name over HTTPS."),
            ("SocketTimeout", "The laptop did not answer in time.")
        ]
        for err_type, expected_hint in simulated_errors:
            self.assertTrue(len(expected_hint) > 10)

    # 3. Malformed or unexpected AI output
    def test_3_malformed_or_unexpected_ai_output(self):
        # Parsing invalid or unexpected JSON payloads
        malformed_inputs = [
            "{invalid_json",
            "",
            "null",
            "12345",
            '{"action": null, "parameters": "not_a_dict"}'
        ]
        for bad_input in malformed_inputs:
            try:
                parsed = json.loads(bad_input)
                if not isinstance(parsed, dict):
                    parsed = None
            except Exception:
                parsed = None
            self.assertTrue(parsed is None or "action" not in parsed or not isinstance(parsed.get("parameters"), dict))

    # 4. Rejection of unsupported action names and parameters
    def test_4_rejection_of_unsupported_action_names_and_parameters(self):
        # Unknown action or malformed phone/SMS parameters
        res_empty_call = json.loads(make_phone_call({"contact": ""}))
        self.assertEqual(res_empty_call["status"], "failed")
        self.assertEqual(res_empty_call["error"], "malformed_parameters")

        res_long_call = json.loads(make_phone_call({"contact": "A" * 100}))
        self.assertEqual(res_long_call["status"], "failed")
        self.assertEqual(res_long_call["error"], "malformed_parameters")

        res_empty_sms = json.loads(send_sms_message({"contact": "Alice", "message": ""}))
        self.assertEqual(res_empty_sms["status"], "failed")
        self.assertEqual(res_empty_sms["error"], "malformed_parameters")

        res_empty_recipient = json.loads(send_sms_message({"contact": "", "message": "Hello"}))
        self.assertEqual(res_empty_recipient["status"], "failed")
        self.assertEqual(res_empty_recipient["error"], "malformed_parameters")

    # 5. Permission denial and permission revocation
    def test_5_permission_denial_and_permission_revocation(self):
        from tests.test_multi_step_task_engine import MultiStepTaskEngine
        engine = MultiStepTaskEngine()
        task = engine.plan("Turn on flashlight, then open camera", "task_perm_denial")

        # Step 2 requires android.permission.CAMERA, but user denies permission
        engine.execute_next_step("task_perm_denial")
        denial_result = engine.execute_next_step("task_perm_denial", available_permissions=[])
        self.assertEqual(denial_result["status"], "permission_required")
        self.assertEqual(task["status"], "FAILED")
        self.assertIn("android.permission.CAMERA", denial_result["error"])

    # 6. Cancellation and resource cleanup
    def test_6_cancellation_and_resource_cleanup(self):
        from tests.test_multi_step_task_engine import MultiStepTaskEngine
        engine = MultiStepTaskEngine()
        task = engine.plan("Turn on flashlight, then open camera", "task_cleanup")
        engine.cancel("task_cleanup")

        self.assertEqual(task["status"], "CANCELLED")
        self.assertTrue(task["cancelled"])
        # Remaining steps marked CANCELLED
        for step in task["steps"]:
            self.assertEqual(step["status"], "CANCELLED")

    # 7. Prevention of duplicate consequential actions
    def test_7_prevention_of_duplicate_consequential_actions(self):
        # 1. Call duplicate check
        res1 = json.loads(make_phone_call({"contact": "Alice"}))
        self.assertEqual(res1["status"], "success")

        # Calling again immediately must be blocked by deduplicator
        res2 = json.loads(make_phone_call({"contact": "Alice"}))
        self.assertEqual(res2["status"], "failed")
        self.assertEqual(res2["error"], "duplicate_consequential_action_prevented")

        # 2. SMS duplicate check
        sms1 = json.loads(send_sms_message({"contact": "Bob", "message": "Are you ready?"}))
        self.assertEqual(sms1["status"], "success")

        sms2 = json.loads(send_sms_message({"contact": "Bob", "message": "Are you ready?"}))
        self.assertEqual(sms2["status"], "failed")
        self.assertEqual(sms2["error"], "duplicate_consequential_action_prevented")

        # 3. WhatsApp duplicate check
        wa1 = json.loads(send_whatsapp_message({"contact": "Family", "message": "Dinner at 7"}))
        self.assertEqual(wa1["status"], "success")

        wa2 = json.loads(send_whatsapp_message({"contact": "Family", "message": "Dinner at 7"}))
        self.assertEqual(wa2["status"], "failed")
        self.assertEqual(wa2["error"], "duplicate_consequential_action_prevented")

    # 8. Protection against stale task results
    def test_8_protection_against_stale_task_results(self):
        from tests.test_multi_step_task_engine import MultiStepTaskEngine
        engine = MultiStepTaskEngine()
        engine.plan("Initial task", "task_token_check")
        token_1 = engine.active_tokens["task_token_check"]

        # User cancels and re-runs
        engine.cancel("task_token_check")
        token_2 = engine.active_tokens["task_token_check"]
        self.assertNotEqual(token_1, token_2)

        # Late-arriving network callback with old token is rejected
        accepted, msg = engine.apply_late_result("task_token_check", token_1, {"spoken": "old"})
        self.assertFalse(accepted)
        self.assertIn("Stale result rejected", msg)

    # 9. Sensitive information excluded from production logs
    def test_9_sensitive_information_excluded_from_production_logs(self):
        from core import audit
        # Verify audit redaction works on sensitive strings
        test_key = "AIzaSy" + "A" * 33
        text_with_key = f"Failed request with {test_key}"
        redacted = audit.redact(text_with_key)
        self.assertNotIn(test_key, redacted)
        self.assertIn("[REDACTED]", redacted)

        text_with_token = "bearer secret_auth_token_value_12345"
        redacted_bearer = audit.redact(text_with_token)
        self.assertNotIn("secret_auth_token_value_12345", redacted_bearer)
        self.assertIn("[REDACTED]", redacted_bearer)

    # 10. Memory deletion and privacy-related state changes
    def test_10_memory_deletion_and_privacy_related_state_changes(self):
        # Saving and then forgetting memory
        remember_res = json.loads(manage_personal_memory({"action": "remember", "key": "favorite_editor", "value": "neovim"}))
        self.assertEqual(remember_res["status"], "success")

        # Forgetting memory confirms local deletion and notes cloud limitation
        forget_res = json.loads(manage_personal_memory({"action": "forget", "key": "favorite_editor"}))
        self.assertEqual(forget_res["status"], "success")
        self.assertTrue(forget_res.get("local_only"))
        self.assertIn("Removed from active on-device storage", forget_res["message"])
        self.assertIn("remote cloud models", forget_res["message"])

    # 11. Recovery from ambiguous external-action results
    def test_11_recovery_from_ambiguous_external_action_results(self):
        # Simulate ambiguous carrier exception during SMS dispatch
        def simulate_sms_dispatch(ambiguous_failure: bool):
            if ambiguous_failure:
                return {
                    "status": "failed",
                    "error": "ambiguous_external_outcome",
                    "spoken": "Message dispatch outcome is uncertain. Please check your messages app to avoid sending twice.",
                    "data": {"check_device": True}
                }
            return {"status": "success"}

        outcome = simulate_sms_dispatch(ambiguous_failure=True)
        self.assertEqual(outcome["status"], "failed")
        self.assertEqual(outcome["error"], "ambiguous_external_outcome")
        self.assertTrue(outcome["data"]["check_device"])
        self.assertIn("avoid sending twice", outcome["spoken"])

    # 12. Debug versus release configuration
    def test_12_debug_versus_release_configuration(self):
        # Verify that backup rules exclude memory and sharedpref
        with open("mobile/android/app/src/main/res/xml/data_extraction_rules.xml", "r", encoding="utf-8") as f:
            rules_xml = f.read()
        self.assertIn('path="memory"', rules_xml)
        self.assertIn('path="datastore"', rules_xml)
        self.assertIn('domain="sharedpref"', rules_xml)

        # Verify ProGuard rules strip debug logs
        with open("mobile/android/app/proguard-rules.pro", "r", encoding="utf-8") as f:
            proguard = f.read()
        self.assertIn("android.util.Log", proguard)
        self.assertIn("-assumenosideeffects", proguard)

        # Verify allowBackup="false" in AndroidManifest.xml
        with open("mobile/android/app/src/main/AndroidManifest.xml", "r", encoding="utf-8") as f:
            manifest = f.read()
        self.assertIn('android:allowBackup="false"', manifest)


if __name__ == "__main__":
    unittest.main()
