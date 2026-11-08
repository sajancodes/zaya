"""Real-Time Audio Latency & Acoustic Calibration Engine for Zaya.
Created and developed by Sajan Rai.

Continuously calibrates ambient room noise floors, speech Signal-to-Noise Ratio (SNR),
voice turn-around latency, and dynamically tunes adaptive speech silence boundaries.
"""
from __future__ import annotations

import collections
import logging
import math
import struct
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Deque, List, Optional, Tuple

from core.runtime_paths import mutable_path

logger = logging.getLogger(__name__)

_CALIBRATION_PATH = mutable_path(Path(__file__).resolve().parent.parent / "memory" / "acoustic_calibration.json")


@dataclass
class AcousticProfile:
    noise_floor_db: float = -55.0
    speech_snr_db: float = 24.0
    recommended_silence_sec: float = 0.45
    speech_cadence: str = "normal"  # brisk, normal, deliberate
    last_turnaround_ms: float = 280.0
    avg_turnaround_ms: float = 310.0
    samples_calibrated: int = 0
    updated_at: float = field(default_factory=time.time)


class VoiceCalibrationEngine:
    """Passively computes acoustic telemetry and dynamically tunes speech boundaries."""

    def __init__(self, storage_path: Optional[Path] = None) -> None:
        self.storage_path = storage_path or _CALIBRATION_PATH
        self._lock = threading.RLock()
        self._profile = AcousticProfile()
        self._energy_history: Deque[float] = collections.deque(maxlen=100)
        self._latency_history: Deque[float] = collections.deque(maxlen=20)
        self._load()

    def _load(self) -> None:
        with self._lock:
            if self.storage_path.exists():
                try:
                    import json
                    data = json.loads(self.storage_path.read_text(encoding="utf-8"))
                    self._profile = AcousticProfile(**data)
                except Exception as exc:
                    logger.warning("Failed to load acoustic calibration profile: %s", exc)

    def _save(self) -> None:
        with self._lock:
            import json
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            self.storage_path.write_text(json.dumps(asdict(self._profile), indent=2), encoding="utf-8")

    def analyze_audio_frame(self, pcm_bytes: bytes) -> Tuple[float, float]:
        """Compute RMS energy and dBFS for a 16-bit mono PCM audio chunk."""
        count = len(pcm_bytes) // 2
        if count == 0:
            return 0.0, -96.0

        samples = struct.unpack(f"<{count}h", pcm_bytes[:count * 2])
        sum_sq = sum(s * s for s in samples)
        rms = math.sqrt(sum_sq / float(count)) / 32768.0

        db = 20.0 * math.log10(max(rms, 1e-5))
        return rms, round(db, 1)

    def feed_ambient_sample(self, pcm_bytes: bytes) -> AcousticProfile:
        """Feed ambient microphone background audio to update dynamic noise floor."""
        rms, db = self.analyze_audio_frame(pcm_bytes)

        with self._lock:
            self._energy_history.append(rms)
            # Noise floor is estimated as the 10th percentile of energy history
            sorted_energies = sorted(self._energy_history)
            p10_idx = max(0, int(len(sorted_energies) * 0.10))
            noise_rms = sorted_energies[p10_idx]
            noise_db = 20.0 * math.log10(max(noise_rms, 1e-5))

            self._profile.noise_floor_db = round(noise_db, 1)
            self._profile.samples_calibrated += 1
            self._profile.updated_at = time.time()
            self._save()
            return self._profile

    def record_turn_metrics(
        self,
        speech_pcm_bytes: bytes,
        turnaround_latency_ms: float,
        inter_phrase_pause_sec: float = 0.35,
    ) -> AcousticProfile:
        """Record completed voice turn acoustic telemetry and adapt silence thresholds."""
        speech_rms, speech_db = self.analyze_audio_frame(speech_pcm_bytes)

        with self._lock:
            # Calculate speech SNR relative to calibrated noise floor
            snr = max(0.0, speech_db - self._profile.noise_floor_db)
            self._profile.speech_snr_db = round(snr, 1)

            # Record turnaround latency
            if turnaround_latency_ms > 0:
                self._latency_history.append(turnaround_latency_ms)
                self._profile.last_turnaround_ms = round(turnaround_latency_ms, 1)
                self._profile.avg_turnaround_ms = round(
                    sum(self._latency_history) / float(len(self._latency_history)), 1
                )

            # Classify cadence and adapt silence threshold
            if inter_phrase_pause_sec > 0.55:
                self._profile.speech_cadence = "deliberate"
                self._profile.recommended_silence_sec = 0.65
            elif inter_phrase_pause_sec < 0.28:
                self._profile.speech_cadence = "brisk"
                self._profile.recommended_silence_sec = 0.35
            else:
                self._profile.speech_cadence = "normal"
                self._profile.recommended_silence_sec = 0.45

            self._profile.updated_at = time.time()
            self._save()
            return self._profile

    def get_profile(self) -> AcousticProfile:
        with self._lock:
            return self._profile


_calibration_engine: Optional[VoiceCalibrationEngine] = None
_calib_lock = threading.Lock()


def get_voice_calibration_engine() -> VoiceCalibrationEngine:
    global _calibration_engine
    with _calib_lock:
        if _calibration_engine is None:
            _calibration_engine = VoiceCalibrationEngine()
        return _calibration_engine
