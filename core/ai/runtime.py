"""Build the modular engine from owner settings without touching UI code."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.ai.settings import LocalPipelineSettings, local_pipeline_settings
from core.llm.registry import ProviderConfig, ProviderRegistry
from core.llm.router import LLMRouter
from core.providers.speech.base import SpeechError, STTProvider, TTSProvider
from core.providers.speech.piper import PiperTTS
from core.providers.speech.whisper import FasterWhisperSTT


@dataclass
class LocalRuntimeBundle:
    settings: LocalPipelineSettings
    registry: ProviderRegistry
    provider: ProviderConfig
    llm: LLMRouter
    stt: STTProvider
    tts: TTSProvider


def build_local_runtime(settings: LocalPipelineSettings | None = None) -> LocalRuntimeBundle:
    values = settings or local_pipeline_settings()
    registry = ProviderRegistry()
    registry.load_from_config()
    registry.allow_cloud_fallback = bool(values.allow_cloud_fallback)
    provider = registry.get(values.provider)
    if provider is None:
        raise SpeechError("llm", f"Provider '{values.provider}' is not configured.", provider=values.provider)
    if values.model:
        provider.model = values.model
    if values.base_url:
        provider.base_url = values.base_url
    if values.api_key:
        provider.api_keys = [values.api_key]
    llm = LLMRouter(registry=registry)
    if values.stt_provider not in {"faster_whisper", "whisper", "faster-whisper"}:
        raise SpeechError("stt", f"Unknown STT provider '{values.stt_provider}'.", provider=values.stt_provider)
    stt = FasterWhisperSTT(
        values.stt_model,
        device=values.stt_device,
        compute_type=values.stt_compute_type,
        language=values.stt_language,
    )
    if values.tts_provider != "piper":
        raise SpeechError("tts", f"Unknown TTS provider '{values.tts_provider}'.", provider=values.tts_provider)
    tts = PiperTTS(
        values.tts_model,
        voice_map=values.tts_voice_map,
        fallback_voice=values.tts_fallback_voice,
        default_voice=values.tts_model,
    )
    return LocalRuntimeBundle(values, registry, provider, llm, stt, tts)
