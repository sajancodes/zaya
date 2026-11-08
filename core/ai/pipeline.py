"""Zaya's modular conversation engine: microphone -> STT -> LLM -> TTS.

The engine owns no UI and no live-session details. It consumes the same
16 kHz microphone packets as the live path, returns 24 kHz PCM to the same
speaker queue, and executes tools through Zaya's standard Operator-backed
callback. That keeps the avatar, transcript, memory, missions, phone captions
and permissions identical regardless of which engine is selected.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Mapping, Optional

from core.ai.capabilities import EngineCapabilities, local_pipeline_capabilities
from core.ai.settings import LocalPipelineSettings
from core.llm.router import LLMRouter
from core.llm.types import LLMError, LLMMessage, StreamChunk, ToolCall, ToolDefinition
from core.providers.speech.base import SpeechError, STTProvider, TTSProvider
from core.security.untrusted_content import boundary_prompt
from core.speech.chunker import SemanticChunker
from core.speech.playback import SpeechPipeline, SpeechTiming
from core.speech.reasoning_filter import ReasoningFilter
from core.speech.text import speakable_text
from core.tool_result import ToolResult
from core.tools.loop_guard import LoopGuard
from core.tools.routing import ToolRouter, normalize_declaration

logger = logging.getLogger(__name__)


@dataclass
class Utterance:
    text: str = ""
    pcm: bytes = b""
    language: str = ""
    source: str = "microphone"


@dataclass
class PipelineCallbacks:
    on_state: Optional[Callable[[str], None]] = None
    on_user_text: Optional[Callable[[str, str, str], None]] = None
    on_display_delta: Optional[Callable[[str], None]] = None
    on_display_final: Optional[Callable[[str], None]] = None
    on_tool_result: Optional[Callable[[str, ToolResult], None]] = None
    on_error: Optional[Callable[[str], None]] = None
    on_readiness: Optional[Callable[[dict[str, Any]], None]] = None
    on_timing: Optional[Callable[[dict[str, Any]], None]] = None
    is_speaking: Optional[Callable[[], bool]] = None
    on_barge_in: Optional[Callable[[], None]] = None
    on_speakable: Optional[Callable[[str], None]] = None


class LocalConversationPipeline:
    def __init__(
        self,
        *,
        stt: STTProvider,
        tts: TTSProvider,
        llm: LLMRouter,
        provider: Any,
        settings: LocalPipelineSettings,
        input_queue: asyncio.Queue,
        audio_queue: asyncio.Queue,
        tool_executor: Callable[[str, dict], Any],
        tool_declarations: Iterable[Any],
        system_prompt: str | Callable[[], str],
        callbacks: PipelineCallbacks | None = None,
        tool_router: ToolRouter | None = None,
        max_tool_rounds: int = 4,
    ) -> None:
        self.stt = stt
        self.tts = tts
        self.llm = llm
        self.provider = provider
        self.settings = settings
        self.input_queue = input_queue
        self.audio_queue = audio_queue
        self.tool_executor = tool_executor
        self.tool_declarations = list(tool_declarations)
        self.system_prompt = system_prompt
        self.callbacks = callbacks or PipelineCallbacks()
        self.tool_router = tool_router or ToolRouter()
        self.max_tool_rounds = max(1, int(max_tool_rounds))
        self.capabilities: EngineCapabilities = local_pipeline_capabilities(provider)
        self.speech = SpeechPipeline(
            provider=tts,
            audio_queue=audio_queue,
            on_error=self._on_tts_error,
            on_timing=self._on_tts_timing,
        )
        self._utterances: asyncio.Queue = asyncio.Queue(maxsize=2)
        self._history: deque[LLMMessage] = deque(maxlen=max(2, settings.max_history_messages))
        self._turn_task: asyncio.Task | None = None
        self._capture_task: asyncio.Task | None = None
        self._running = False
        self._closed = False
        self._readiness: dict[str, Any] = {
            "STT_READY": False, "LLM_READY": False, "TTS_READY": False,
            "PIPELINE_READY": False,
        }
        self._last_timing: dict[str, Any] = {}
        self._last_speech_timing: dict[str, Any] = {}
        self._vad = self._make_vad()
        self._stt_lock = asyncio.Lock()

    # ── readiness ────────────────────────────────────────────────────────────

    @property
    def readiness(self) -> dict[str, Any]:
        return dict(self._readiness)

    def _set_readiness(self, **values: Any) -> None:
        self._readiness.update(values)
        self._readiness["PIPELINE_READY"] = bool(
            self._readiness.get("LLM_READY") and
            (self._readiness.get("STT_READY") or self._readiness.get("STT_TEXT_ONLY"))
        )
        if self.callbacks.on_readiness:
            try:
                self.callbacks.on_readiness(dict(self._readiness))
            except Exception:
                pass

    async def warmup(self) -> dict[str, Any]:
        self._set_readiness(LLM_READY=False, STT_READY=False, TTS_READY=False)
        llm_ok, llm_error = await self._warm_llm()
        self._set_readiness(LLM_READY=llm_ok, LLM_ERROR=llm_error)
        stt_ok, stt_error = await self._warm_component("stt", self.stt.warmup)
        self._set_readiness(STT_READY=stt_ok, STT_ERROR=stt_error,
                            STT_TEXT_ONLY=not stt_ok)
        tts_ok, tts_error = await self._warm_component("tts", self.tts.warmup)
        self._set_readiness(TTS_READY=tts_ok, TTS_ERROR=tts_error, TTS_TEXT_ONLY=not tts_ok)
        if not llm_ok and self.callbacks.on_error:
            self.callbacks.on_error(llm_error)
        if not stt_ok and self.callbacks.on_error:
            self.callbacks.on_error(stt_error)
        if not tts_ok and self.callbacks.on_error:
            self.callbacks.on_error(tts_error)
        return dict(self._readiness)

    async def _warm_component(self, name: str, warmup: Callable[[], None]) -> tuple[bool, str]:
        try:
            await asyncio.to_thread(warmup)
            return True, ""
        except SpeechError as error:
            return False, str(error)
        except Exception as error:
            return False, f"{name.upper()} failed: {type(error).__name__}: {error}"

    async def _warm_llm(self) -> tuple[bool, str]:
        provider = self.provider
        if provider is None:
            return False, "LLM failed: the selected provider is not available."
        if not getattr(provider, "configured", False):
            if getattr(provider, "requires_key", True) and not getattr(provider, "api_key", ""):
                return False, f"LLM failed: {provider.label} has no API key."
            return False, f"LLM failed: {provider.label} is not configured."
        if getattr(provider, "local", False):
            ok, error = await asyncio.to_thread(self._probe_local_llm, provider)
            if not ok:
                return False, error
        return True, ""

    @staticmethod
    def _probe_local_llm(provider: Any) -> tuple[bool, str]:
        import requests
        url = str(provider.base_url or "").rstrip("/")
        if not url:
            return False, f"LLM failed: {provider.label} has no endpoint."
        if provider.provider_type == "ollama" and not url.endswith("/v1"):
            probe = url + "/api/tags"
        else:
            probe = url + "/models"
        headers = {}
        if provider.api_key:
            headers["Authorization"] = f"Bearer {provider.api_key}"
        try:
            response = requests.get(probe, headers=headers, timeout=3.0)
            if response.status_code in (200, 204):
                return True, ""
            if response.status_code in (404, 405):
                # Some compatible servers do not expose /models but do serve
                # chat completions. A listening endpoint is ready for the real
                # turn; the turn itself will name any protocol failure.
                return True, ""
            if response.status_code in (401, 403):
                return False, f"LLM failed: {provider.label} rejected its credentials (HTTP {response.status_code})."
            return False, f"LLM failed: {provider.label} readiness check returned HTTP {response.status_code}."
        except Exception as error:
            return False, f"LLM failed: cannot reach {provider.label} at {url} ({type(error).__name__})."

    # ── lifecycle ────────────────────────────────────────────────────────────

    async def run(self) -> None:
        if self._running:
            return
        self._running = True
        await self.speech.start()
        self._capture_task = asyncio.create_task(self._capture_loop(), name="zaya-local-vad")
        self._set_state("LISTENING")
        try:
            while not self._closed:
                utterance = await self._utterances.get()
                if utterance is None:
                    break
                if self._turn_task and not self._turn_task.done():
                    self._turn_task.cancel()
                    try:
                        await self._turn_task
                    except (asyncio.CancelledError, Exception):
                        pass
                    self.speech.interrupt()
                    if self.callbacks.on_barge_in:
                        try:
                            self.callbacks.on_barge_in()
                        except Exception:
                            pass
                self._turn_task = asyncio.create_task(self._handle_utterance(utterance))
        finally:
            self._running = False
            await self.stop()

    async def stop(self) -> None:
        self._closed = True
        if self._turn_task:
            self._turn_task.cancel()
            try:
                await self._turn_task
            except (asyncio.CancelledError, Exception):
                pass
            self._turn_task = None
        if self._capture_task:
            self._capture_task.cancel()
            try:
                await self._capture_task
            except (asyncio.CancelledError, Exception):
                pass
            self._capture_task = None
        await self.speech.stop()
        try:
            self.stt.close()
        except Exception:
            pass
        try:
            self.tts.close()
        except Exception:
            pass
        try:
            self._utterances.put_nowait(None)
        except asyncio.QueueFull:
            pass

    def interrupt(self) -> None:
        self.speech.interrupt()
        if self._turn_task and not self._turn_task.done():
            self._turn_task.cancel()

    # ── input ────────────────────────────────────────────────────────────────

    async def submit_text(self, text: str, *, source: str = "typed") -> bool:
        value = str(text or "").strip()
        if not value:
            return False
        if self._turn_task and not self._turn_task.done():
            self._turn_task.cancel()
            self.speech.interrupt()
        item = Utterance(text=value, source=source)
        while True:
            try:
                self._utterances.put_nowait(item)
                return True
            except asyncio.QueueFull:
                # A deliberate typed turn supersedes queued speech from the
                # previous moment; dropping the oldest item is better than
                # silently losing the owner's newest command.
                try:
                    self._utterances.get_nowait()
                except asyncio.QueueEmpty:
                    return False

    async def speak_text(self, text: str, *, language: str = "", display: bool = True) -> None:
        value = str(text or "").strip()
        if not value:
            return
        spoken = speakable_text(value)
        if display and self.callbacks.on_display_final:
            self.callbacks.on_display_final(value)
        await self.speech.enqueue(spoken, language=language)

    async def _capture_loop(self) -> None:
        sample_rate = 16000
        frame_samples = 480  # 30 ms
        frame_bytes = frame_samples * 2
        pending = bytearray()
        pre_roll: deque[bytes] = deque(maxlen=10)
        speech: list[bytes] = []
        speaking = False
        speech_ms = 0
        silence_ms = 0
        min_speech = max(100, self.settings.vad_min_speech_ms)
        end_silence = max(250, self.settings.vad_silence_ms)
        while not self._closed:
            try:
                packet = await self.input_queue.get()
            except asyncio.CancelledError:
                return
            if packet is None:
                continue
            data = packet.get("data") if isinstance(packet, dict) else packet
            if not isinstance(data, (bytes, bytearray)):
                continue
            pending.extend(bytes(data))
            while len(pending) >= frame_bytes:
                frame = bytes(pending[:frame_bytes])
                del pending[:frame_bytes]
                voiced = self._is_voiced(frame, sample_rate)
                duration = 30
                if not speaking:
                    pre_roll.append(frame)
                    if voiced:
                        speaking = True
                        speech = list(pre_roll)
                        speech_ms = duration
                        silence_ms = 0
                    continue
                speech.append(frame)
                if voiced:
                    speech_ms += duration
                    silence_ms = 0
                else:
                    silence_ms += duration
                    if silence_ms >= end_silence:
                        if speech_ms >= min_speech:
                            pcm = b"".join(speech)
                            try:
                                self._utterances.put_nowait(Utterance(pcm=pcm, source="microphone"))
                            except asyncio.QueueFull:
                                pass
                        speaking = False
                        speech = []
                        speech_ms = 0
                        silence_ms = 0
                        pre_roll.clear()

    def _make_vad(self):
        try:
            import webrtcvad
            return webrtcvad.Vad(2)
        except Exception:
            return None

    def _is_voiced(self, frame: bytes, sample_rate: int) -> bool:
        if self._vad is not None:
            try:
                return bool(self._vad.is_speech(frame, sample_rate))
            except Exception:
                pass
        try:
            import numpy as np
            values = np.frombuffer(frame, dtype=np.int16)
            if values.size == 0:
                return False
            return float(np.sqrt(np.mean(values.astype(np.float64) ** 2))) >= 380.0
        except Exception:
            return False

    # ── turn ─────────────────────────────────────────────────────────────────

    def resolve_language(self, detected: str = "", utterance_language: str = "") -> str:
        """Resolve spoken/transcribed language using documented fallback chain:
        detected -> utterance.language -> settings.stt_language -> "" (let model infer).
        """
        chain = [
            ("detected", detected),
            ("utterance", utterance_language),
            ("settings", getattr(self.settings, "stt_language", "")),
            ("fallback", ""),
        ]
        for source, val in chain:
            clean = str(val or "").strip()
            if clean:
                logger.debug("Language resolved to '%s' from %s", clean, source)
                return clean
        logger.debug("Language resolved to empty string (fallback to model inference)")
        return ""

    async def _handle_utterance(self, utterance: Utterance) -> None:
        turn_started = time.monotonic()
        self._set_state("THINKING")
        initial_hint = self.resolve_language("", utterance.language)
        text = utterance.text.strip()
        if not text and utterance.pcm:
            self._set_state("LISTENING")
            stt_started = time.monotonic()
            try:
                async with self._stt_lock:
                    result = await asyncio.to_thread(
                        self.stt.transcribe, utterance.pcm,
                        sample_rate=16000, language=initial_hint or None)
            except SpeechError as error:
                self._error(str(error))
                self._set_state("LISTENING")
                return
            except Exception as error:
                self._error(f"STT failed: {type(error).__name__}: {error}")
                self._set_state("LISTENING")
                return
            stt_ms = (time.monotonic() - stt_started) * 1000.0
            text = result.text.strip()
            detected = getattr(result, "language", "")
            language = self.resolve_language(detected, utterance.language)
            if not text:
                self._set_state("LISTENING")
                return
            self._last_timing = {"stt_ms": round(stt_ms, 1), "language": language}
        else:
            language = self.resolve_language("", utterance.language)
            self._last_timing = {"stt_ms": 0.0, "language": language}
        if self.callbacks.on_user_text:
            try:
                self.callbacks.on_user_text(text, language, utterance.source)
            except Exception:
                pass
        if self.callbacks.on_display_final:
            # The owner's words are not model display text; the UI uses the
            # dedicated callback above. No-op keeps callbacks simple.
            pass
        messages: list[LLMMessage] = [LLMMessage.system(self._system_text())]
        messages.extend(self._history)
        messages.append(LLMMessage.user(text))
        self._history.append(LLMMessage.user(text))
        assistant_text = ""
        turn_display: list[str] = []
        loop_guard = LoopGuard(max_calls=max(6, self.max_tool_rounds * 4),
                               max_same_tool=max(2, self.max_tool_rounds))
        llm_started = time.monotonic()
        first_text_ms = 0.0
        try:
            for round_index in range(self.max_tool_rounds + 1):
                final_round = round_index >= self.max_tool_rounds
                route = self.tool_router.route(
                    text, [] if final_round else self.tool_declarations,
                    max_tools=self._max_tools(), max_schema_chars=self._max_schema_chars(),
                    allow_fallback=not final_round,
                )
                tools = None if final_round else [
                    ToolDefinition(
                        name=normalize_declaration(item)["name"],
                        description=normalize_declaration(item)["description"],
                        parameters=_lower_schema(normalize_declaration(item)["parameters"]),
                    )
                    for item in route.declarations
                ]
                chunks, calls = await self._stream_llm(
                    messages, tools, final_round=final_round, original_text=text)
                if chunks and not first_text_ms:
                    first_text_ms = (time.monotonic() - llm_started) * 1000.0
                assistant_text += chunks
                turn_display.append(chunks)
                if not calls or final_round:
                    messages.append(LLMMessage.assistant(chunks))
                    break
                messages.append(LLMMessage.assistant(chunks, tool_calls=calls))
                for index, call in enumerate(calls):
                    decision = loop_guard.check("turn", call.name, call.arguments)
                    if not decision.allowed:
                        result = ToolResult(
                            "partial", decision.reason,
                            {"loop_limited": True, "tool": call.name}, retryable=False)
                    else:
                        try:
                            result = await self.tool_executor(call.name, dict(call.arguments or {}))
                            if not isinstance(result, ToolResult):
                                result = ToolResult("partial", str(result), {"legacy": True, "verified": False})
                        except asyncio.CancelledError:
                            raise
                        except Exception as error:
                            result = ToolResult("failed", f"{call.name} failed: {type(error).__name__}: {error}")
                    if self.callbacks.on_tool_result:
                        try:
                            self.callbacks.on_tool_result(call.name, result)
                        except Exception:
                            pass
                    payload = json.dumps(result.to_dict(), ensure_ascii=False, default=str)
                    messages.append(LLMMessage.tool_result(
                        call.id or f"call_{round_index}_{index}", payload, name=call.name))
                if assistant_text.strip():
                    # The preamble is already being spoken. Keep it in history
                    # and start the next generation on a clean display buffer.
                    self._history.append(LLMMessage.assistant(assistant_text))
                    if (self.callbacks.on_display_delta
                            and not assistant_text[-1].isspace()):
                        try:
                            self.callbacks.on_display_delta(" ")
                        except Exception:
                            pass
                    assistant_text = ""
            if not assistant_text.strip():
                assistant_text = "I finished the request, but I do not have a verified result to report."
                turn_display.append(assistant_text)
        except asyncio.CancelledError:
            raise
        except LLMError as error:
            detail = str(error)
            label = str(getattr(self.provider, "label", "") or "")
            if label and label not in detail:
                detail = f"{label}: {detail}"
            self._error(f"LLM failed: {detail}")
            self._set_state("LISTENING")
            return
        except Exception as error:
            self._error(f"LLM failed: {type(error).__name__}: {error}")
            self._set_state("LISTENING")
            return
        finally:
            self._timing({
                "turn_ms": round((time.monotonic() - turn_started) * 1000.0, 1),
                "llm_first_text_ms": round(first_text_ms, 1),
                "provider": getattr(self.provider, "name", ""),
            })
        full_display = ""
        for part in turn_display:
            if not part:
                continue
            if (full_display and not full_display[-1].isspace()
                    and not part[0].isspace() and part[0] not in ".!?,;:"):
                full_display += " "
            full_display += part
        full_display = full_display.strip()
        if assistant_text.strip():
            self._history.append(LLMMessage.assistant(assistant_text))
        if full_display and self.callbacks.on_display_final:
            try:
                self.callbacks.on_display_final(full_display)
            except Exception:
                pass
        self._set_state("LISTENING")

    async def _stream_llm(self, messages: list[LLMMessage], tools: list[ToolDefinition] | None,
                          *, final_round: bool, original_text: str) -> tuple[str, list[ToolCall]]:
        loop = asyncio.get_running_loop()
        bridge: asyncio.Queue = asyncio.Queue(maxsize=64)
        cancelled = False
        filter_ = ReasoningFilter()
        chunker = SemanticChunker()
        display_parts: list[str] = []
        calls: list[ToolCall] = []

        def offer(item) -> bool:
            """Put without losing the worker when the consumer is slow or gone."""
            if loop.is_closed():
                return False
            try:
                future = asyncio.run_coroutine_threadsafe(bridge.put(item), loop)
            except RuntimeError:
                return False
            while True:
                if cancelled:
                    future.cancel()
                    return False
                try:
                    future.result(timeout=0.1)
                    return True
                except TimeoutError:
                    continue
                except Exception:
                    return False

        def produce() -> None:
            try:
                stream = self.llm.stream_route(
                    messages=messages,
                    tools=tools,
                    task="chat",
                    preferred_provider=getattr(self.provider, "name", None),
                    temperature=0.6,
                    max_tokens=1200,
                    allow_failover=bool(self.settings.allow_cloud_fallback),
                )
                for chunk in stream:
                    if cancelled or not offer(chunk):
                        break
            except BaseException as error:
                offer(error)
            finally:
                if not cancelled:
                    offer(None)

        task = asyncio.create_task(asyncio.to_thread(produce))
        try:
            while True:
                item = await bridge.get()
                if item is None:
                    break
                if isinstance(item, BaseException):
                    raise item
                if not isinstance(item, StreamChunk):
                    continue
                calls.extend(item.tool_calls or [])
                if item.delta_text:
                    filtered = filter_.feed(item.delta_text)
                    if filtered.display:
                        display_parts.append(filtered.display)
                        if self.callbacks.on_display_delta:
                            try:
                                self.callbacks.on_display_delta(filtered.display)
                            except Exception:
                                pass
                    if filtered.speech:
                        for sentence in chunker.feed(speakable_text(filtered.speech)):
                            await self._queue_sentence(sentence)
            tail = filter_.flush()
            if tail.display:
                display_parts.append(tail.display)
                if self.callbacks.on_display_delta:
                    try:
                        self.callbacks.on_display_delta(tail.display)
                    except Exception:
                        pass
            for sentence in chunker.feed(speakable_text(tail.speech)):
                await self._queue_sentence(sentence)
            for sentence in chunker.flush():
                await self._queue_sentence(sentence)
        finally:
            cancelled = True
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
        return "".join(display_parts), calls

    # ── helpers ──────────────────────────────────────────────────────────────

    async def _queue_sentence(self, sentence: str) -> None:
        value = str(sentence or "").strip()
        if not value:
            return
        # Do not claim the speaker is active merely because text was queued.
        # The playback pipeline marks speaking on the first real PCM chunk and
        # clears it on silence, so a failed synthesis cannot leave the echo
        # guard believing Zaya is still talking forever.
        await self.speech.enqueue(
            value, language=self._last_timing.get("language", ""))

    def _system_text(self) -> str:
        value = self.system_prompt() if callable(self.system_prompt) else self.system_prompt
        return f"{boundary_prompt()}\n\n{value}"

    def _max_tools(self) -> int:
        value = int(self.settings.max_tools or self.capabilities.max_tools or 10)
        return max(1, min(value, int(self.capabilities.max_tools or value)))

    def _max_schema_chars(self) -> int:
        value = int(self.settings.max_tool_schema_chars or self.capabilities.max_tool_schema_chars or 9000)
        return max(256, min(value, int(self.capabilities.max_tool_schema_chars or value)))

    def _set_state(self, state: str) -> None:
        if self.callbacks.on_state:
            try:
                self.callbacks.on_state(state)
            except Exception:
                pass

    def _error(self, message: str) -> None:
        if self.callbacks.on_error:
            try:
                self.callbacks.on_error(message)
            except Exception:
                pass

    def _timing(self, values: dict[str, Any]) -> None:
        self._last_timing.update(values)
        if self.settings.timings and self.callbacks.on_timing:
            try:
                self.callbacks.on_timing(dict(self._last_timing))
            except Exception:
                pass

    def _on_tts_error(self, message: str) -> None:
        text = str(message or "unknown synthesis error")
        if not text.lower().startswith("tts failed"):
            text = f"TTS failed: {text}"
        self._error(text)

    def _on_tts_timing(self, timing: SpeechTiming) -> None:
        self._last_speech_timing = timing.public()
        self._timing({"tts": self._last_speech_timing})


def _lower_schema(value: Any) -> Any:
    if isinstance(value, dict):
        result = {key: _lower_schema(item) for key, item in value.items()}
        if isinstance(result.get("type"), str):
            result["type"] = result["type"].lower()
        return result
    if isinstance(value, list):
        return [_lower_schema(item) for item in value]
    return value
