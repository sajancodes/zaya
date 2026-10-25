"""faster-whisper STT provider (optional local dependency)."""

from __future__ import annotations

import threading
import time
from pathlib import Path

from core.providers.speech.base import SpeechError, STTProvider, STTResult


class FasterWhisperSTT(STTProvider):
    def __init__(self, model: str = "small", *, device: str = "auto",
                 compute_type: str = "int8", download_root: str | Path | None = None,
                 language: str = ""):
        self.model_name = str(model or "small")
        self.device = str(device or "auto")
        self.compute_type = str(compute_type or "int8")
        self.download_root = str(download_root) if download_root else None
        self.language = str(language or "").strip() or None
        self._model = None
        self._lock = threading.RLock()
        self._ready = False

    @property
    def ready(self) -> bool:
        return self._ready

    def warmup(self) -> None:
        with self._lock:
            if self._ready:
                return
            try:
                from faster_whisper import WhisperModel
            except ImportError as error:
                raise SpeechError(
                    "stt", "faster-whisper is not installed. Install faster-whisper to use the local pipeline.",
                    provider="faster_whisper",
                ) from error
            try:
                self._model = WhisperModel(
                    self.model_name,
                    device=self.device,
                    compute_type=self.compute_type,
                    download_root=self.download_root,
                )
                self._ready = True
            except Exception as error:
                # A CUDA driver mismatch must fall back to CPU, not break speech.
                if self.device.lower() not in {"cpu", "auto"}:
                    try:
                        self._model = WhisperModel(
                            self.model_name, device="cpu", compute_type="int8",
                            download_root=self.download_root,
                        )
                        self.device = "cpu"
                        self.compute_type = "int8"
                        self._ready = True
                        return
                    except Exception:
                        pass
                raise SpeechError("stt", str(error), provider="faster_whisper") from error

    def transcribe(self, pcm: bytes, *, sample_rate: int = 16000,
                   language: str | None = None) -> STTResult:
        self.warmup()
        if not pcm:
            return STTResult("")
        try:
            import numpy as np
        except ImportError as error:
            raise SpeechError("stt", "numpy is required for local transcription", provider="faster_whisper") from error
        audio = np.frombuffer(bytes(pcm), dtype=np.int16).astype(np.float32) / 32768.0
        selected_language = str(language or self.language or "").strip()
        if selected_language.lower() in {"", "auto", "detect"}:
            selected_language = None
        else:
            # faster-whisper expects an ISO 639-1 code; regional tags such as
            # en-US would otherwise be rejected as an unknown language.
            selected_language = selected_language.split("-")[0].lower()
        started = time.monotonic()
        with self._lock:
            try:
                segments, info = self._model.transcribe(
                    audio,
                    language=selected_language,
                    beam_size=1,
                    vad_filter=False,
                    condition_on_previous_text=False,
                )
                rows = []
                pieces = []
                for segment in segments:
                    text = str(getattr(segment, "text", "") or "").strip()
                    if text:
                        pieces.append(text)
                    rows.append({
                        "start": float(getattr(segment, "start", 0.0) or 0.0),
                        "end": float(getattr(segment, "end", 0.0) or 0.0),
                        "text": text,
                        "avg_logprob": float(getattr(segment, "avg_logprob", 0.0) or 0.0),
                    })
            except Exception as error:
                raise SpeechError("stt", str(error), provider="faster_whisper") from error
        probability = float(getattr(info, "language_probability", 0.0) or 0.0)
        detected = str(getattr(info, "language", "") or selected_language or "")
        duration = float(getattr(info, "duration", 0.0) or (len(pcm) / 2 / max(1, sample_rate)))
        confidence = max(0.0, min(1.0, probability))
        return STTResult(
            text=" ".join(pieces).strip(),
            language=detected,
            language_probability=probability,
            duration_sec=duration,
            confidence=confidence,
            segments=rows,
        )


def faster_whisper_available() -> bool:
    try:
        import importlib.util
        return importlib.util.find_spec("faster_whisper") is not None
    except Exception:
        return False
