"""Comprehensive unit tests for Zaya Conversational Intelligence and Context-Aware Voice Follow-ups.
Covers Section 11 requirements from Prompt 4.
"""
from __future__ import annotations

import unittest

from core.conversational_agent import ConversationalAgent, FollowUpResolution


class ConversationalAgentTests(unittest.TestCase):

    def setUp(self) -> None:
        self.agent = ConversationalAgent()

    # 1. Follow-up reference resolution: "Explain that again"
    def test_01_explain_that_again_references_prior_response(self) -> None:
        self.agent.record_assistant_turn("The Wi-Fi network 'HomeNet' is currently connected with 85% signal.")
        self.agent.record_user_turn("Explain that again")

        res = self.agent.resolve_follow_up("Explain that again")
        self.assertEqual(res.intent, "repeat")
        self.assertIn("HomeNet", res.resolved_text)
        self.assertIn("re-explain", res.resolved_text.lower(), msg="Should request re-explanation")

    # 2. Follow-up reference resolution: "Make it shorter"
    def test_02_make_it_shorter_requests_concise_summary(self) -> None:
        long_response = (
            "We audited your system battery health. The current state is charging at 18W. "
            "Battery percentage is 72%. Temperature is 31 degrees Celsius, which is optimal."
        )
        self.agent.record_assistant_turn(long_response)
        self.agent.record_user_turn("Make it shorter")

        res = self.agent.resolve_follow_up("Make it shorter")
        self.assertEqual(res.intent, "summarize")
        self.assertIn("Summarize this in 1-2 short sentences", res.resolved_text)

    # 3. Follow-up reference resolution: "Do the second option"
    def test_03_do_second_option_selects_correct_item(self) -> None:
        assistant_turn = (
            "I found two ways to handle this:\n"
            "1. Reboot your router\n"
            "2. Reset network settings"
        )
        self.agent.record_assistant_turn(assistant_turn)

        res = self.agent.resolve_follow_up("Do the second option")
        self.assertEqual(res.intent, "select_option")
        self.assertEqual(res.selected_option, "Reset network settings")

    # 4. Ambiguous consequential voice command requires explicit confirmation
    def test_04_consequential_option_requires_explicit_confirmation(self) -> None:
        assistant_turn = (
            "Available actions:\n"
            "1. Keep existing files\n"
            "2. Delete all downloads and temporary data"
        )
        self.agent.record_assistant_turn(assistant_turn)

        res = self.agent.resolve_follow_up("Do option 2")
        self.assertEqual(res.intent, "select_option")
        self.assertTrue(res.requires_confirmation)
        self.assertIn("permanent changes", res.confirmation_reason)

    # 5. Ambiguous "continue" with consequential pending action
    def test_05_ambiguous_continue_does_not_bypass_consequential_confirmation(self) -> None:
        self.agent.record_assistant_turn(
            "Do you want me to transfer $500 to recipient?",
            action_pending={'action': 'transfer', 'consequential': True}
        )

        res = self.agent.resolve_follow_up("Continue")
        self.assertEqual(res.intent, "continue")
        self.assertTrue(res.requires_confirmation)
        self.assertIn("explicitly confirm", res.confirmation_reason)

    # 6. Speech silence vs task cancellation
    def test_06_speech_silence_distinguished_from_task_cancellation(self) -> None:
        # "Stop speaking" stops audio playback
        res_speech = self.agent.resolve_follow_up("Stop speaking", is_task_running=True)
        self.assertEqual(res_speech.intent, "stop_speech")

        # "Cancel task" halts background task
        res_task = self.agent.resolve_follow_up("Cancel task", is_task_running=True)
        self.assertEqual(res_task.intent, "cancel_task")

    # 7. Ambiguous "cancel" when task is running cancels the task
    def test_07_ambiguous_cancel_stops_running_task(self) -> None:
        res = self.agent.resolve_follow_up("cancel", is_task_running=True)
        self.assertEqual(res.intent, "cancel_task")

    # 8. Ambiguous "cancel" when no task is running mutes speech
    def test_08_ambiguous_cancel_when_no_task_silences_speech(self) -> None:
        res = self.agent.resolve_follow_up("stop", is_task_running=False)
        self.assertEqual(res.intent, "stop_speech")

    # 9. Acoustic echo feedback loop prevention
    def test_09_acoustic_feedback_loop_detected_and_ignored(self) -> None:
        spoken_by_zaya = "Your morning alarm is set for 7:00 AM tomorrow."
        self.agent.record_assistant_turn(spoken_by_zaya)

        # Microphone hears Zaya's own voice coming through speaker
        echo_heard = "Your morning alarm is set for"
        res = self.agent.resolve_follow_up(echo_heard)
        self.assertEqual(res.intent, "echo_ignored")
        self.assertEqual(res.confidence, 0.0)

    # 10. Normal user query passes through directly
    def test_10_normal_speech_input_passes_through(self) -> None:
        res = self.agent.resolve_follow_up("What is the weather in Tokyo?")
        self.assertEqual(res.intent, "normal")
        self.assertEqual(res.resolved_text, "What is the weather in Tokyo?")

    # 11. Context history is strictly bounded
    def test_11_context_history_is_bounded_to_max_turns(self) -> None:
        for i in range(12):
            self.agent.record_user_turn(f"User message {i}")
            self.agent.record_assistant_turn(f"Assistant answer {i}")

        self.assertLessEqual(len(self.agent.history), ConversationalAgent.MAX_HISTORY_TURNS)

    # 12. Sensitive credentials redacted from conversation turns
    def test_12_credentials_redacted_from_conversation_history(self) -> None:
        self.agent.record_user_turn("My password is SecretPassword123 and api_key=sk-1234567890abcdef1234567890")
        last_turn = self.agent.history[-1]
        self.assertNotIn("SecretPassword123", last_turn.text)
        self.assertNotIn("sk-1234567890abcdef1234567890", last_turn.text)
        self.assertIn("[REDACTED]", last_turn.text)


if __name__ == '__main__':
    unittest.main()
