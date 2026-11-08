"""Speaker Voiceprint Biometrics & Acoustic Verification Guard for Zaya.
Created and developed by Sajan Rai.

Extracts acoustic features (pitch via normalized autocorrelation, zero-crossing rate,
spectral centroid, spectral roll-off, energy envelope) from 16-bit mono PCM audio
to verify speaker identity and guard voice-activated operations.
"""
from __future__ import annotations

import json
import logging
import math
import struct
import threading
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, List, Optional, Tuple

from core.runtime_paths import mutable_path

logger = logging.getLogger(__name__)

_PROFILE_PATH = mutable_path(Path(__file__).resolve().parent.parent / "memory" / "voiceprint_profile.json")


@dataclass
class AcousticFeatures:
    pitch_hz: float
    spectral_centroid_hz: float
    zero_crossing_rate: float
    energy_rms: float
    spectral_rolloff_hz: float


@dataclass
class VerificationResult:
    match: bool
    confidence: float
    distance: float
    metrics: dict[str, Any]
    enrolled: bool


def _extract_pcm_samples(pcm_bytes: bytes) -> List[float]:
    """Convert 16-bit signed little-endian PCM bytes into normalized floats (-1.0 to 1.0)."""
    count = len(pcm_bytes) // 2
    if count == 0:
        return []
    raw = struct.unpack(f"<{count}h", pcm_bytes[:count * 2])
    return [s / 32768.0 for s in raw]


def extract_features(pcm_bytes: bytes, sample_rate: int = 16000) -> Optional[AcousticFeatures]:
    """Extract acoustic voiceprint features from raw PCM audio."""
    samples = _extract_pcm_samples(pcm_bytes)
    if len(samples) < 512:
        return None

    # 1. Energy RMS
    energy_rms = math.sqrt(sum(s * s for s in samples) / len(samples))
    if energy_rms < 0.005:
        # Too quiet / pure silence
        return None

    # 2. Zero Crossing Rate (ZCR)
    zero_crossings = sum(
        1 for i in range(1, len(samples))
        if (samples[i] >= 0 and samples[i - 1] < 0) or (samples[i] < 0 and samples[i - 1] >= 0)
    )
    zcr = zero_crossings / float(len(samples))

    # 3. Fundamental frequency (pitch) via normalized autocorrelation
    # Human speech pitch typically lies between 70 Hz and 400 Hz
    min_lag = int(sample_rate / 400)
    max_lag = int(sample_rate / 70)
    max_lag = min(max_lag, len(samples) // 2)

    best_pitch_hz = 0.0
    best_corr = 0.0
    n = len(samples) // 2

    # Downsampled fast autocorrelation
    step = 2
    for lag in range(min_lag, max_lag, step):
        num = sum(samples[i] * samples[i + lag] for i in range(0, n, step))
        denom1 = sum(samples[i] ** 2 for i in range(0, n, step))
        denom2 = sum(samples[i + lag] ** 2 for i in range(0, n, step))
        norm_denom = math.sqrt(denom1 * denom2)
        if norm_denom > 1e-9:
            corr = num / norm_denom
            if corr > best_corr and corr > 0.35:
                best_corr = corr
                best_pitch_hz = sample_rate / float(lag)

    # 4. Spectral Centroid & Spectral Roll-off (approximate discrete frequency bins)
    # Using windowed DFT magnitude estimation across 64 log-spaced filterbanks
    num_bins = 64
    bin_freqs = [80.0 * ((sample_rate / 2.0 / 80.0) ** (b / float(num_bins - 1))) for b in range(num_bins)]
    magnitudes = [0.0] * num_bins

    # Short FFT or Goertzel / discrete transform approximation
    t_vals = [i / float(sample_rate) for i in range(min(len(samples), 1024))]
    sub_samples = samples[:len(t_vals)]

    for b, freq in enumerate(bin_freqs):
        omega = 2.0 * math.pi * freq
        # Fast inner product with cosine and sine basis
        re_sum = sum(s * math.cos(omega * t) for s, t in zip(sub_samples, t_vals))
        im_sum = sum(s * math.sin(omega * t) for s, t in zip(sub_samples, t_vals))
        magnitudes[b] = math.sqrt(re_sum * re_sum + im_sum * im_sum)

    total_mag = sum(magnitudes)
    if total_mag > 1e-9:
        spectral_centroid = sum(f * m for f, m in zip(bin_freqs, magnitudes)) / total_mag

        # Spectral roll-off: frequency below which 85% of magnitude lies
        cum_threshold = total_mag * 0.85
        cum_sum = 0.0
        spectral_rolloff = bin_freqs[-1]
        for f, m in zip(bin_freqs, magnitudes):
            cum_sum += m
            if cum_sum >= cum_threshold:
                spectral_rolloff = f
                break
    else:
        spectral_centroid = 1000.0
        spectral_rolloff = 2500.0

    return AcousticFeatures(
        pitch_hz=round(best_pitch_hz, 1),
        spectral_centroid_hz=round(spectral_centroid, 1),
        zero_crossing_rate=round(zcr, 4),
        energy_rms=round(energy_rms, 4),
        spectral_rolloff_hz=round(spectral_rolloff, 1),
    )


class VoiceprintManager:
    """Manages enrollment and biometric speaker verification."""

    def __init__(self, profile_path: Optional[Path] = None) -> None:
        self.path = profile_path or _PROFILE_PATH
        self._lock = threading.RLock()
        self._profile: dict[str, Any] = self._load_profile()

    def _load_profile(self) -> dict[str, Any]:
        with self._lock:
            if self.path.exists():
                try:
                    return json.loads(self.path.read_text(encoding="utf-8"))
                except Exception as exc:
                    logger.warning("Failed to load voiceprint profile: %s", exc)
            return {"enrolled": False, "samples_count": 0, "features": {}}

    def _save_profile(self) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self._profile, indent=2), encoding="utf-8")

    def enroll(self, pcm_bytes: bytes, sample_rate: int = 16000) -> Tuple[bool, str]:
        """Enroll an audio sample to build or refine the owner's acoustic voiceprint."""
        feat = extract_features(pcm_bytes, sample_rate)
        if not feat:
            return False, "Audio sample too quiet, too short, or lacks recognizable speech."

        with self._lock:
            count = self._profile.get("samples_count", 0)
            existing = self._profile.get("features", {})

            # Exponential moving average for profile adaptation
            if count == 0:
                self._profile["features"] = asdict(feat)
                self._profile["samples_count"] = 1
                self._profile["enrolled"] = True
            else:
                alpha = 1.0 / min(count + 1, 10)
                for k, v in asdict(feat).items():
                    cur = existing.get(k, v)
                    existing[k] = round((1.0 - alpha) * cur + alpha * v, 4)
                self._profile["samples_count"] = count + 1
                self._profile["enrolled"] = True

            self._save_profile()
            return True, f"Voice sample enrolled (total samples: {self._profile['samples_count']})."

    def verify(
        self,
        pcm_bytes: bytes,
        sample_rate: int = 16000,
        threshold: float = 0.55,
    ) -> VerificationResult:
        """Verify if an audio sample matches the enrolled owner voiceprint."""
        with self._lock:
            if not self._profile.get("enrolled", False):
                # When not enrolled, permissive mode with notice
                return VerificationResult(
                    match=True,
                    confidence=1.0,
                    distance=0.0,
                    metrics={"notice": "Speaker voiceprint not yet enrolled; permissive default."},
                    enrolled=False,
                )

            feat = extract_features(pcm_bytes, sample_rate)
            if not feat:
                return VerificationResult(
                    match=False,
                    confidence=0.0,
                    distance=1.0,
                    metrics={"error": "Audio sample has insufficient speech signal."},
                    enrolled=True,
                )

            target = self._profile.get("features", {})

            # Compute normalized acoustic distance
            # Pitch distance (weight 0.40)
            t_pitch = target.get("pitch_hz", 150.0)
            p_dist = abs(feat.pitch_hz - t_pitch) / max(t_pitch, 50.0) if t_pitch > 0 else 0.0

            # Centroid distance (weight 0.35)
            t_centroid = target.get("spectral_centroid_hz", 1200.0)
            c_dist = abs(feat.spectral_centroid_hz - t_centroid) / max(t_centroid, 100.0)

            # ZCR distance (weight 0.25)
            t_zcr = target.get("zero_crossing_rate", 0.05)
            z_dist = abs(feat.zero_crossing_rate - t_zcr) / max(t_zcr, 0.01)

            weighted_dist = (0.40 * min(p_dist, 2.0)) + (0.35 * min(c_dist, 2.0)) + (0.25 * min(z_dist, 2.0))
            confidence = max(0.0, 1.0 - (weighted_dist / 1.5))
            is_match = weighted_dist <= threshold

            return VerificationResult(
                match=is_match,
                confidence=round(confidence, 3),
                distance=round(weighted_dist, 3),
                metrics={
                    "sample_features": asdict(feat),
                    "target_features": target,
                    "weighted_distance": round(weighted_dist, 3),
                },
                enrolled=True,
            )

    def reset(self) -> None:
        """Reset owner voiceprint enrollment."""
        with self._lock:
            self._profile = {"enrolled": False, "samples_count": 0, "features": {}}
            self._save_profile()

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "enrolled": self._profile.get("enrolled", False),
                "samples_count": self._profile.get("samples_count", 0),
                "features": self._profile.get("features", {}),
            }


_voiceprint_mgr: Optional[VoiceprintManager] = None
_vp_lock = threading.Lock()


def get_voiceprint_manager() -> VoiceprintManager:
    global _voiceprint_mgr
    with _vp_lock:
        if _voiceprint_mgr is None:
            _voiceprint_mgr = VoiceprintManager()
        return _voiceprint_mgr
