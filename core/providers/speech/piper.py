"""Piper TTS provider with language-to-voice routing."""

from __future__ import annotations

import io
import re
import tempfile
import threading
import wave
from pathlib import Path
from typing import Any

from core.providers.speech.base import AudioChunk, SpeechError, TTSProvider

_LANGUAGE_ALIASES = {
    "english": "en", "eng": "en", "nepali": "ne", "nepalese": "ne", "nep": "ne",
    "hindi": "hi", "spanish": "es", "french": "fr", "german": "de", "italian": "it",
    "portuguese": "pt", "russian": "ru", "arabic": "ar", "japanese": "ja",
    "korean": "ko", "chinese": "zh", "mandarin": "zh", "dutch": "nl",
    "turkish": "tr", "polish": "pl", "ukrainian": "uk", "vietnamese": "vi",
}


def normalize_language(value: str) -> str:
    raw = str(value or "").strip().lower()
    if not raw:
        return ""
    raw = raw.replace("_", "-")
    base = raw.split("-")[0]
    return _LANGUAGE_ALIASES.get(raw, _LANGUAGE_ALIASES.get(base, base))


class VoiceRouter:
    """Resolve a detected language to an installed voice, with a safe fallback."""

    def __init__(self, voice_map: dict[str, str] | None = None,
                 fallback: str = "", default: str = ""):
        self.voice_map = {
            normalize_language(key): str(value).strip()
            for key, value in (voice_map or {}).items() if str(value).strip()
        }
        self.fallback = str(fallback or default or "").strip()
        self.default = str(default or self.fallback).strip()

    def select(self, language: str = "") -> str:
        normalized = normalize_language(language)
        if normalized and normalized in self.voice_map:
            return self.voice_map[normalized]
        if normalized:
            for key, value in self.voice_map.items():
                if key and (normalized.startswith(key) or key.startswith(normalized)):
                    return value
        return self.fallback or self.default

    def installed(self) -> list[str]:
        return sorted(set(self.voice_map.values()) | ({self.fallback} if self.fallback else set()))


class PiperTTS(TTSProvider):
    def __init__(self, model: str = "", *, voice_map: dict[str, str] | None = None,
                 fallback_voice: str = "", default_voice: str = ""):
        self.default_model = str(model or "").strip()
        self.router = VoiceRouter(voice_map or {}, fallback=fallback_voice or self.default_model,
                                  default=self.default_model)
        self._voices: dict[str, Any] = {}
        self._lock = threading.RLock()
        self._ready = False

    @property
    def ready(self) -> bool:
        return self._ready

    def _path_for(self, language: str = "", voice: str = "") -> str:
        selected = str(voice or "").strip() or self.router.select(language)
        if not selected:
            raise SpeechError(
                "tts", "No Piper voice is configured. Choose a .onnx voice in AI Engine settings.",
                provider="piper",
            )
        path = Path(selected).expanduser()
        if not path.is_file():
            raise SpeechError("tts", f"Piper voice file not found: {path}", provider="piper")
        return str(path)

    def _load(self, path: str):
        with self._lock:
            if path in self._voices:
                return self._voices[path]
            try:
                from piper import PiperVoice
            except ImportError as error:
                raise SpeechError(
                    "tts", "piper-tts is not installed. Install piper-tts to use local speech.",
                    provider="piper",
                ) from error
            try:
                loaded = PiperVoice.load(path)
            except Exception as error:
                raise SpeechError("tts", str(error), provider="piper") from error
            self._voices[path] = loaded
            return loaded

    def warmup(self) -> None:
        # A multilingual owner may configure only a language map and no default
        # voice. Prove one installed voice works instead of reporting the whole
        # TTS stage unavailable.
        choices = [self.router.fallback, *self.router.voice_map.values()]
        configured = next((item for item in choices if str(item or "").strip()), "")
        existing = next(
            (item for item in choices
             if str(item or "").strip() and Path(item).expanduser().is_file()),
            "",
        )
        path = self._path_for("", voice=existing or configured)
        voice = self._load(path)
        # A tiny synthesis proves the ONNX runtime and voice config actually work.
        try:
            self._synthesize_with(voice, "Ready.", path, discard=True)
            self._ready = True
        except SpeechError:
            raise
        except Exception as error:
            raise SpeechError("tts", f"Piper test synthesis failed: {error}", provider="piper") from error

    def synthesize(self, text: str, *, language: str = "", voice: str = "") -> AudioChunk:
        value = str(text or "").strip()
        if not value:
            return AudioChunk(b"", 24000)
        path = self._path_for(language, voice)
        loaded = self._load(path)
        audio = self._synthesize_with(loaded, value, path)
        self._ready = True
        return audio

    @staticmethod
    def _sample_rate(voice: Any, default: int = 22050) -> int:
        for candidate in (
            getattr(getattr(voice, "config", None), "sample_rate", None),
            getattr(voice, "sample_rate", None),
        ):
            try:
                rate = int(candidate)
                if 4000 <= rate <= 96000:
                    return rate
            except (TypeError, ValueError):
                pass
        return default

    def _synthesize_with(self, voice: Any, text: str, path: str, discard: bool = False) -> AudioChunk:
        sample_rate = self._sample_rate(voice)
        pcm = b""
        try:
            if hasattr(voice, "synthesize"):
                result = voice.synthesize(text)
                pcm, sample_rate = self._collect(result, voice, sample_rate)
            elif hasattr(voice, "synthesize_stream_raw"):
                result = voice.synthesize_stream_raw(text)
                pcm = b"".join(bytes(part) for part in result)
            elif hasattr(voice, "synthesize_wav"):
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as stream:
                    temp_path = Path(stream.name)
                try:
                    voice.synthesize_wav(text, str(temp_path))
                    with wave.open(str(temp_path), "rb") as wav:
                        sample_rate = int(wav.getframerate())
                        pcm = wav.readframes(wav.getnframes())
                finally:
                    temp_path.unlink(missing_ok=True)
            else:
                raise SpeechError("tts", "This Piper build exposes no synthesis method.", provider="piper")
        except SpeechError:
            raise
        except Exception as error:
            raise SpeechError("tts", str(error), provider="piper") from error
        if discard:
            return AudioChunk(b"", sample_rate)
        if not pcm:
            raise SpeechError("tts", "Piper returned no audio.", provider="piper")
        return AudioChunk(bytes(pcm), sample_rate, 1)

    @staticmethod
    def _collect(result: Any, voice: Any, sample_rate: int) -> tuple[bytes, int]:
        if isinstance(result, (bytes, bytearray)):
            return bytes(result), sample_rate
        if hasattr(result, "audio_int16_bytes"):
            rate = int(getattr(result, "sample_rate", sample_rate) or sample_rate)
            return bytes(result.audio_int16_bytes), rate
        if hasattr(result, "__iter__") and not isinstance(result, (str, dict)):
            pieces = []
            for item in result:
                if hasattr(item, "audio_int16_bytes"):
                    sample_rate = int(getattr(item, "sample_rate", sample_rate) or sample_rate)
                    pieces.append(bytes(item.audio_int16_bytes))
                elif isinstance(item, (bytes, bytearray)):
                    pieces.append(bytes(item))
            return b"".join(pieces), sample_rate
        raise SpeechError("tts", f"Unsupported Piper result type: {type(result).__name__}", provider="piper")


def piper_available() -> bool:
    try:
        import importlib.util
        return importlib.util.find_spec("piper") is not None
    except Exception:
        return False
