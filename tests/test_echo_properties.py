"""Synthetic acoustic invariants, without changing the calibrated thresholds."""
import unittest

import numpy as np

from core.echo import EchoGuard
from core.viseme import VisemeStream


class EchoPropertiesTests(unittest.TestCase):
    def test_echo_stays_silent_and_distinct_speech_survives_across_gain_and_reverb(self):
        # Controlled fixtures, not a claim to reproduce every physical room.
        samples = np.arange(1024) / 16000
        reference = sum(np.sin(2 * np.pi * freq * samples)
                        for freq in (320, 850, 1400, 2300)) * 1800
        human = sum(np.sin(2 * np.pi * freq * samples + .4)
                    for freq in (510, 1850, 3300)) * 2400
        for gain in (.15, .5, 1., 1.8):
            for reverb in (0., .25, .6):
                with self.subTest(gain=gain, reverb=reverb):
                    guard = EchoGuard()
                    random = np.random.default_rng(91)
                    for index in range(45):
                        echo = gain * (reference + reverb * np.roll(reference, 27))
                        echo += random.normal(0, 4, len(reference))
                        when = index * .064
                        guard.note_output(reference, 16000, .4, when=when)
                        self.assertFalse(guard.is_user_speech(echo, 16000, .3, when=when))
                    for index in range(8):
                        when = (45 + index) * .064
                        guard.note_output(reference, 16000, .4, when=when)
                        self.assertTrue(guard.is_user_speech(echo + human, 16000, .6, when=when))

    def test_viseme_frames_accept_generators_with_the_same_result_as_lists(self):
        audio = [(0., 0., 0.), (.3, .5, .2), (.4, .6, -.2)]
        self.assertEqual(VisemeStream().frames(iter(audio), .02), VisemeStream().frames(audio, .02))
