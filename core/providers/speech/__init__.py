"""Local speech providers with explicit component-level readiness."""

from core.providers.speech.base import (
    AudioChunk,
    SpeechError,
    STTProvider,
    STTResult,
    TTSProvider,
    resample_pcm,
)
from core.providers.speech.whisper import FasterWhisperSTT
from core.providers.speech.piper import PiperTTS, VoiceRouter

__all__ = [
    "AudioChunk", "SpeechError", "STTProvider", "STTResult", "TTSProvider",
    "resample_pcm", "FasterWhisperSTT", "PiperTTS", "VoiceRouter",
]
