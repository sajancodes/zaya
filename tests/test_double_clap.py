"""Unit tests for double-clap acoustic detection and toggle action.
Created and developed by Sajan Rai for Zaya.
"""

import unittest
from unittest.mock import patch

import numpy as np

from core.double_clap import DoubleClapDetector, is_double_clap_enabled, set_double_clap_enabled


class TestDoubleClapDetector(unittest.TestCase):
    def setUp(self):
        self.sample_rate = 16000
        self.detected_calls = 0

    def _on_detect(self):
        self.detected_calls += 1

    def _generate_clap(self, duration_sec=0.03, peak_amp=15000):
        """Generates a realistic percussive clap: high amplitude, rapid decay, noise."""
        num_samples = int(self.sample_rate * duration_sec)
        t = np.linspace(0, duration_sec, num_samples, endpoint=False)
        decay = np.exp(-t * 120)
        noise = np.random.uniform(-1, 1, num_samples)
        clap = (noise * decay * peak_amp).astype(np.int16)
        return clap

    def _generate_silence(self, duration_sec=0.3):
        num_samples = int(self.sample_rate * duration_sec)
        return np.zeros(num_samples, dtype=np.int16)

    def test_single_clap_does_not_trigger(self):
        detector = DoubleClapDetector(on_detect=self._on_detect, sample_rate=self.sample_rate)
        clap = self._generate_clap()
        silence = self._generate_silence(1.0)

        detector.process_chunk(clap)
        detector.process_chunk(silence)

        self.assertEqual(self.detected_calls, 0, "Single clap should not trigger double clap")

    def test_double_clap_triggers(self):
        detector = DoubleClapDetector(
            on_detect=self._on_detect,
            sample_rate=self.sample_rate,
            min_gap_sec=0.15,
            max_gap_sec=0.80
        )
        clap1 = self._generate_clap()
        gap = self._generate_silence(0.35)
        clap2 = self._generate_clap()
        after = self._generate_silence(0.2)

        # Process first clap at t=1.0
        detector.process_chunk(clap1, current_time=1.0)
        # Gap at t=1.2
        detector.process_chunk(gap, current_time=1.2)
        # Process second clap at t=1.35 (gap = 0.35s)
        detector.process_chunk(clap2, current_time=1.35)
        detector.process_chunk(after, current_time=1.55)

        self.assertEqual(self.detected_calls, 1, "Double clap should trigger callback exactly once")

    def test_claps_too_far_apart_do_not_trigger(self):
        detector = DoubleClapDetector(
            on_detect=self._on_detect,
            sample_rate=self.sample_rate,
            min_gap_sec=0.15,
            max_gap_sec=0.50
        )
        clap1 = self._generate_clap()
        gap = self._generate_silence(1.2)  # Exceeds max_gap_sec
        clap2 = self._generate_clap()

        detector.process_chunk(clap1, current_time=1.0)
        detector.process_chunk(gap, current_time=1.8)
        detector.process_chunk(clap2, current_time=2.3)

        self.assertEqual(self.detected_calls, 0, "Claps separated by too long should not trigger")

    def test_continuous_speech_rejected(self):
        """Speech with sustained low frequencies and low zero-crossing rate should not trigger."""
        detector = DoubleClapDetector(on_detect=self._on_detect, sample_rate=self.sample_rate)
        t = np.linspace(0, 1.0, self.sample_rate, endpoint=False)
        speech = (np.sin(2 * np.pi * 250 * t) * 12000).astype(np.int16)

        detector.process_chunk(speech)
        self.assertEqual(self.detected_calls, 0, "Sustained tone/speech should not trigger")

    def test_toggle_persistence(self):
        """The preference must actually reach the config file.

        This used to mock save_api_keys(), which took an API-key STRING and
        validated it with parse_keys(). A config DICT made it raise
        "Enter at least one Gemini API key.", so the real code never wrote
        anything and the mock hid it. The round-trip is now exercised for real.
        """
        import json
        import tempfile
        from pathlib import Path
        from unittest.mock import patch

        import memory.config_manager as config_manager

        with tempfile.TemporaryDirectory() as folder:
            config_file = Path(folder) / "api_keys.json"
            config_file.write_text(
                json.dumps({"gemini_api_key": "REAL-KEY-0123456789"}), encoding="utf-8"
            )
            with patch.object(config_manager, "CONFIG_FILE", config_file), \
                 patch.object(config_manager, "CONFIG_DIR", Path(folder)):
                self.assertFalse(is_double_clap_enabled())

                self.assertTrue(set_double_clap_enabled(True))
                self.assertTrue(is_double_clap_enabled())

                stored = json.loads(config_file.read_text(encoding="utf-8"))
                self.assertTrue(stored["double_clap_enabled"])
                # The unrelated owner setting must survive the write.
                self.assertEqual(stored["gemini_api_key"], "REAL-KEY-0123456789")

                self.assertTrue(set_double_clap_enabled(False))
                self.assertFalse(is_double_clap_enabled())


class TestDoubleClapToggleAction(unittest.TestCase):
    def test_toggle_action_reports_persist_failure(self):
        """A failed write must not be reported as success."""
        import json

        import actions.double_clap_toggle as toggle_action

        original = toggle_action.set_double_clap_enabled
        toggle_action.set_double_clap_enabled = lambda _value: False
        try:
            result = json.loads(toggle_action.double_clap_toggle({"action": "on"}))
        finally:
            toggle_action.set_double_clap_enabled = original

        self.assertEqual(result["status"], "error")
        self.assertFalse(result["double_clap_enabled"])


if __name__ == "__main__":
    unittest.main()
