"""Speech provider interfaces and PCM helpers."""

from __future__ import annotations

import abc
import math
from dataclasses import dataclass, field
from typing import Any


class SpeechError(RuntimeError):
    def __init__(self, component: str, message: str, provider: str = ""):
        self.component = component
        self.provider = provider
        super().__init__(f"{component.upper()} failed" + (f" ({provider})" if provider else "") + f": {message}")


@dataclass
class STTResult:
    text: str
    language: str = ""
    language_probability: float = 0.0
    duration_sec: float = 0.0
    confidence: float = 0.0
    segments: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class AudioChunk:
    pcm: bytes
    sample_rate: int = 24000
    channels: int = 1

    def as_int16(self) -> bytes:
        return bytes(self.pcm)


class STTProvider(abc.ABC):
    component = "stt"

    @abc.abstractmethod
    def warmup(self) -> None:
        """Load models and prove the component can start."""

    @abc.abstractmethod
    def transcribe(self, pcm: bytes, *, sample_rate: int = 16000,
                   language: str | None = None) -> STTResult:
        """Transcribe 16-bit mono PCM."""

    def close(self) -> None:
        pass


class TTSProvider(abc.ABC):
    component = "tts"

    @abc.abstractmethod
    def warmup(self) -> None:
        """Load at least the fallback voice and prove synthesis can start."""

    @abc.abstractmethod
    def synthesize(self, text: str, *, language: str = "", voice: str = "") -> AudioChunk:
        """Synthesize one sentence/paragraph to 16-bit mono PCM."""

    def close(self) -> None:
        pass


def resample_pcm(pcm: bytes, source_rate: int, target_rate: int) -> bytes:
    """Linear PCM resampling; adequate for speech and dependency-free."""
    if not pcm or source_rate <= 0 or target_rate <= 0 or source_rate == target_rate:
        return bytes(pcm)
    try:
        import numpy as np
    except ImportError:
        return bytes(pcm)
    source = np.frombuffer(bytes(pcm), dtype=np.int16)
    if source.size == 0:
        return b""
    ratio = target_rate / float(source_rate)
    target_size = max(1, int(round(source.size * ratio)))
    positions = np.arange(target_size, dtype=np.float64) / ratio
    left = np.floor(positions).astype(np.int64)
    right = np.minimum(left + 1, source.size - 1)
    fraction = positions - left
    values = source[left].astype(np.float64) * (1.0 - fraction) + source[right].astype(np.float64) * fraction
    return np.clip(values, -32768, 32767).astype(np.int16).tobytes()


def pcm_rms(pcm: bytes) -> float:
    if not pcm:
        return 0.0
    try:
        import numpy as np
        values = np.frombuffer(bytes(pcm), dtype=np.int16)
        if values.size == 0:
            return 0.0
        return float(np.sqrt(np.mean(values.astype(np.float64) ** 2)) / 32768.0)
    except ImportError:
        count = len(pcm) // 2
        if not count:
            return 0.0
        total = 0
        for index in range(0, count * 2, 2):
            value = int.from_bytes(pcm[index:index + 2], "little", signed=True)
            total += value * value
        return math.sqrt(total / count) / 32768.0
