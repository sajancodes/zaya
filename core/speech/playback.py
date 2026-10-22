"""Independent, bounded TTS and audio queue workers.

The language model never waits for synthesis. It hands a completed sentence to
a bounded text queue; one TTS worker synthesizes; completed audio is paced into
the existing speaker queue. If synthesis is slow, only the text producer waits.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from core.providers.speech.base import AudioChunk, SpeechError, TTSProvider, resample_pcm


@dataclass
class SpeechTiming:
    text: str = ""
    queued_at: float = 0.0
    synthesis_started_at: float = 0.0
    synthesis_finished_at: float = 0.0
    first_audio_ms: float = 0.0
    synthesis_ms: float = 0.0
    audio_chunks: int = 0
    language: str = ""
    failure: str = ""

    def public(self) -> dict[str, Any]:
        return {
            "first_audio_ms": round(self.first_audio_ms, 1),
            "synthesis_ms": round(self.synthesis_ms, 1),
            "audio_chunks": self.audio_chunks,
            "language": self.language,
            "failure": self.failure,
            "text_chars": len(self.text),
        }


@dataclass
class SpeechPipeline:
    provider: TTSProvider
    audio_queue: asyncio.Queue
    on_spoken: Optional[Callable[[str], None]] = None
    on_error: Optional[Callable[[str], None]] = None
    on_timing: Optional[Callable[[SpeechTiming], None]] = None
    target_sample_rate: int = 24000
    text_queue_size: int = 8
    audio_high_water: int = 96
    _text_queue: asyncio.Queue = field(init=False)
    _task: asyncio.Task | None = field(default=None, init=False)
    _epoch: int = field(default=0, init=False)
    _closed: bool = field(default=False, init=False)
    _sentinel = object()

    def __post_init__(self) -> None:
        self._text_queue = asyncio.Queue(maxsize=max(1, int(self.text_queue_size)))

    async def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._worker(), name="zaya-tts-worker")

    async def stop(self) -> None:
        self._closed = True
        self.interrupt()
        if self._task is not None:
            try:
                await asyncio.wait_for(self._text_queue.put(self._sentinel), timeout=0.25)
            except (asyncio.QueueFull, asyncio.TimeoutError):
                pass
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
            self._task = None

    def interrupt(self) -> None:
        """Drop unspoken text and make in-flight synthesis discard its result."""
        self._epoch += 1
        while True:
            try:
                self._text_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

    def _report_timing(self, timing: SpeechTiming) -> None:
        if self.on_timing:
            try:
                self.on_timing(timing)
            except Exception:
                # Telemetry must never stop the speech worker.
                pass

    @property
    def pending_text(self) -> int:
        return self._text_queue.qsize()

    async def enqueue(self, text: str, *, language: str = "", voice: str = "") -> bool:
        value = str(text or "").strip()
        if not value or self._closed:
            return False
        await self.start()
        item = (value, language, voice, self._epoch)
        try:
            await self._text_queue.put(item)
            return True
        except asyncio.CancelledError:
            raise
        except Exception:
            return False

    async def _worker(self) -> None:
        while not self._closed:
            try:
                item = await self._text_queue.get()
            except asyncio.CancelledError:
                return
            if item is self._sentinel:
                return
            text, language, voice, epoch = item
            timing = SpeechTiming(text=text, queued_at=time.monotonic(), language=language)
            timing.synthesis_started_at = time.monotonic()
            try:
                audio = await asyncio.to_thread(
                    self.provider.synthesize, text, language=language, voice=voice)
            except Exception as error:
                timing.synthesis_finished_at = time.monotonic()
                timing.synthesis_ms = (timing.synthesis_finished_at - timing.synthesis_started_at) * 1000.0
                timing.failure = str(error)
                if self.on_error:
                    try:
                        self.on_error(str(error))
                    except Exception:
                        pass
                self._report_timing(timing)
                continue
            timing.synthesis_finished_at = time.monotonic()
            timing.synthesis_ms = (timing.synthesis_finished_at - timing.synthesis_started_at) * 1000.0
            if epoch != self._epoch:
                # The owner interrupted while ONNX was working.
                self._report_timing(timing)
                continue
            if not isinstance(audio, AudioChunk):
                audio = AudioChunk(bytes(audio), 24000, 1)
            pcm = resample_pcm(audio.pcm, audio.sample_rate, self.target_sample_rate)
            if not pcm:
                continue
            if timing.first_audio_ms == 0.0:
                timing.first_audio_ms = (time.monotonic() - timing.queued_at) * 1000.0
            chunk_bytes = max(2, int(self.target_sample_rate * 0.1) * 2)
            for offset in range(0, len(pcm), chunk_bytes):
                if epoch != self._epoch:
                    break
                while self.audio_queue.qsize() >= self.audio_high_water:
                    if epoch != self._epoch:
                        break
                    await asyncio.sleep(0.02)
                if epoch != self._epoch:
                    break
                self.audio_queue.put_nowait(pcm[offset:offset + chunk_bytes])
                timing.audio_chunks += 1
                if timing.first_audio_ms == 0.0:
                    timing.first_audio_ms = (time.monotonic() - timing.queued_at) * 1000.0
            if self.on_spoken and epoch == self._epoch:
                try:
                    self.on_spoken(text)
                except Exception:
                    pass
            self._report_timing(timing)
