"""
Acoustic double-clap detection engine for Zaya.

Detects two sharp acoustic transients within a temporal window (e.g. 180ms to 750ms).
Designed to be ultra-low latency, running on int16 PCM audio chunks directly from the
microphone callback or a lightweight background thread.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Callable, Optional
import numpy as np

def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

BASE_DIR = get_base_dir()
CONFIG_PATH = BASE_DIR / "config" / "api_keys.json"

def _load_config() -> dict:
    try:
        if CONFIG_PATH.exists():
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}

def _save_config(data: dict) -> bool:
    try:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return True
    except Exception:
        return False

def is_double_clap_enabled() -> bool:
    """Returns True if double-clap detection is permanently enabled in config."""
    cfg = _load_config()
    return bool(cfg.get("double_clap_enabled", False))

def set_double_clap_enabled(enabled: bool) -> bool:
    """Persist double-clap activation preference."""
    cfg = _load_config()
    cfg["double_clap_enabled"] = bool(enabled)
    return _save_config(cfg)


class DoubleClapDetector:
    """
    Real-time acoustic clap detector.
    Features:
    - High peak amplitude threshold.
    - Steep transient energy onset ratio (current peak vs ambient floor).
    - High Zero Crossing Rate (ZCR) to distinguish percussive noise from vocal vowel sounds.
    - Rapid decay verification to reject continuous loud noise.
    - Temporal dual-peak matching window.
    """

    def __init__(
        self,
        on_detect: Callable[[], None],
        sample_rate: int = 16000,
        amp_threshold: int = 7000,
        energy_ratio_threshold: float = 3.5,
        min_zcr: float = 0.12,
        min_gap_sec: float = 0.18,
        max_gap_sec: float = 0.75,
        cooldown_sec: float = 1.0,
        logger: Callable[[str], None] = print
    ):
        self.on_detect = on_detect
        self.sample_rate = sample_rate
        self.amp_threshold = amp_threshold
        self.energy_ratio_threshold = energy_ratio_threshold
        self.min_zcr = min_zcr
        self.min_gap_sec = min_gap_sec
        self.max_gap_sec = max_gap_sec
        self.cooldown_sec = cooldown_sec
        self.logger = logger

        # State tracking
        self.ambient_energy: float = 500.0
        self.first_clap_time: float = 0.0
        self.last_detection_time: float = 0.0

    def is_clap(self, chunk: np.ndarray) -> bool:
        """Evaluates whether an audio chunk represents an impulsive clap sound."""
        if len(chunk) == 0:
            return False

        # Flatten multi-channel to 1D
        if chunk.ndim > 1:
            chunk = chunk[:, 0]

        data = chunk.astype(np.float32)
        peak = np.max(np.abs(data))
        if peak < self.amp_threshold:
            # Update ambient floor slowly during quiet periods
            self.ambient_energy = 0.95 * self.ambient_energy + 0.05 * max(peak, 100.0)
            return False

        # Energy ratio: peak must strongly exceed background ambient level
        if peak / max(self.ambient_energy, 100.0) < self.energy_ratio_threshold:
            return False

        # Zero crossing rate (ZCR)
        signs = np.sign(data)
        signs[signs == 0] = 1
        zero_crossings = np.sum(np.diff(signs) != 0)
        zcr = zero_crossings / len(data)
        if zcr < self.min_zcr:
            return False

        # Decay check: split chunk into front half and back half.
        # A true clap decays sharply: back half RMS should be significantly lower than front peak.
        mid = len(data) // 2
        front_peak = np.max(np.abs(data[:mid])) if mid > 0 else peak
        back_rms = np.sqrt(np.mean(data[mid:] ** 2)) if mid < len(data) else peak
        if back_rms > 0.75 * front_peak:
            # Sustained loud noise or tone, not a transient clap
            return False

        return True

    def process_chunk(self, chunk: np.ndarray, current_time: Optional[float] = None) -> bool:
        """
        Process a PCM int16 audio chunk.
        Returns True if a double-clap was detected in this chunk.
        """
        now = current_time if current_time is not None else time.time()

        # Cooldown guard after a successful trigger
        if now - self.last_detection_time < self.cooldown_sec:
            return False

        # Expire stale first clap if past max_gap
        if self.first_clap_time > 0 and (now - self.first_clap_time) > self.max_gap_sec:
            self.first_clap_time = 0.0

        if self.is_clap(chunk):
            if self.first_clap_time == 0.0:
                # Registered first clap
                self.first_clap_time = now
                return False
            else:
                gap = now - self.first_clap_time
                if self.min_gap_sec <= gap <= self.max_gap_sec:
                    # Double clap detected!
                    self.first_clap_time = 0.0
                    self.last_detection_time = now
                    try:
                        self.on_detect()
                    except Exception as e:
                        self.logger(f"[DoubleClap] Callback error: {e}")
                    return True
                elif gap < self.min_gap_sec:
                    # Too fast, probably reverberation or continuous burst; reset
                    return False

        return False
