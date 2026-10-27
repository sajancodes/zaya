import unittest
import numpy as np
import time
from unittest.mock import MagicMock, patch
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
        # 250Hz sine wave (voiced speech fundamental)
        speech = (np.sin(2 * np.pi * 250 * t) * 12000).astype(np.int16)
        
        detector.process_chunk(speech)
        self.assertEqual(self.detected_calls, 0, "Sustained tone/speech should not trigger")

    @patch("core.double_clap._load_config")
    @patch("core.double_clap._save_config")
    def test_toggle_persistence(self, mock_save, mock_load):
        mock_load.return_value = {"double_clap_enabled": False}
        self.assertFalse(is_double_clap_enabled())
        
        set_double_clap_enabled(True)
        mock_save.assert_called_with({"double_clap_enabled": True})

if __name__ == "__main__":
    unittest.main()
