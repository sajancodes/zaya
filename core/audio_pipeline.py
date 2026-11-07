"""Audio output playback pipeline and speaker stream management."""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Callable

import numpy as np

logger = logging.getLogger(__name__)

RECEIVE_SAMPLE_RATE = 24000
CHANNELS = 1
CHUNK_SIZE = 1200
_VIS_HOP = 480
_TAIL_MARGIN = 0.05
_FIRST_SOUND = 0.04
_CURSOR_SLACK = 0.08


class AudioPlaybackPipeline:
    """Manages audio queue draining, speaker device streaming, viseme sync, and mobile audio relay."""

    def __init__(
        self,
        audio_in_queue: asyncio.Queue,
        ui: Any,
        echo_guard: Any,
        viseme_tracker: Any,
        set_speaking_cb: Callable[[bool], None],
        turn_done_event: asyncio.Event | None = None,
        pcm_visemes: Callable | None = None,
        pcm_level: Callable | None = None,
    ):
        self.audio_in_queue = audio_in_queue
        self.ui = ui
        self.echo_guard = echo_guard
        self.viseme_tracker = viseme_tracker
        self.set_speaking = set_speaking_cb
        self.turn_done_event = turn_done_event
        self.pcm_visemes = pcm_visemes
        self.pcm_level = pcm_level
        self.out_latency = 0.15
        self.play_cursor = 0.0
        self.out_level = 0.0

    async def run(self) -> None:
        """Run the audio output stream and playback loop."""
        print("[Zaya] 🔊 Audio playback pipeline started")

        try:
            from core.mobile_bridge import get_bridge
            mobile = get_bridge()
        except Exception:
            mobile = None

        try:
            import sounddevice as sd
            from memory.config_manager import get_output_device
            from core import audio_devices

            spk_name = get_output_device()
            spk_dev = audio_devices.resolve(spk_name, "output")
            if spk_dev is not None:
                print(f"[Zaya] 🔊 Output device: {spk_name}")

            def _open_spk(dev):
                st = sd.RawOutputStream(
                    samplerate=RECEIVE_SAMPLE_RATE,
                    channels=CHANNELS,
                    dtype="int16",
                    blocksize=CHUNK_SIZE,
                    device=dev,
                )
                st.start()
                return st

            try:
                stream = _open_spk(spk_dev)
            except Exception as e:
                if spk_dev is None:
                    raise
                print(f"[Zaya] ⚠️ Output device '{spk_name}' failed: {e} — using default")
                self.ui.write_log(f"SYS: Speaker '{spk_name}' unavailable — using system default.")
                stream = _open_spk(None)

            try:
                lat = float(getattr(stream, "latency", 0.0) or 0.0)
                if 0.0 < lat < 1.0:
                    self.out_latency = lat
                print(f"[Zaya] 🔊 Output latency {self.out_latency*1000:.0f} ms "
                      f"→ echo tail {(self.out_latency + _TAIL_MARGIN)*1000:.0f} ms")
            except Exception:
                pass

        except Exception as e:
            logger.error("Failed to initialize audio output stream: %s", e)
            return

        last_audio = time.monotonic()
        is_speaking = False
        try:
            _pcm_visemes = self.pcm_visemes
            _pcm_level = self.pcm_level
            if _pcm_level is None:
                def _pcm_level(samples) -> float:
                    try:
                        x = np.asarray(samples, dtype=np.float32)
                        return 0.0 if x.size == 0 else min(1.0, float(np.sqrt(np.mean(x * x))) / 32768.0)
                    except Exception:
                        return 0.0

            while True:
                try:
                    chunk = await asyncio.wait_for(
                        self.audio_in_queue.get(),
                        timeout=0.1,
                    )
                except asyncio.TimeoutError:
                    if is_speaking and time.monotonic() - last_audio >= 0.35:
                        is_speaking = False
                        self.set_speaking(False)
                    if self.turn_done_event and self.turn_done_event.is_set():
                        if is_speaking:
                            is_speaking = False
                            self.set_speaking(False)
                        self.turn_done_event.clear()
                    continue

                if not is_speaking:
                    is_speaking = True
                    self.set_speaking(True)

                batch = bytearray(chunk)
                while len(batch) < 9600:
                    try:
                        batch.extend(self.audio_in_queue.get_nowait())
                    except asyncio.QueueEmpty:
                        break

                try:
                    pcm = np.frombuffer(bytes(batch), dtype=np.int16)
                    hop = _VIS_HOP / RECEIVE_SAMPLE_RATE
                    lvl = _pcm_level(pcm)
                    self.out_level = lvl
                    # Echo protection must not depend on optional animation or
                    # the entry point's module name (main versus __main__).
                    if self.echo_guard:
                        self.echo_guard.note_output(pcm, RECEIVE_SAMPLE_RATE, lvl)
                    frames = _pcm_visemes(pcm, sr=RECEIVE_SAMPLE_RATE) if _pcm_visemes else []

                    now = time.time()
                    horizon = self.out_latency + _CURSOR_SLACK
                    if not (now <= self.play_cursor <= now + horizon):
                        self.play_cursor = now + _FIRST_SOUND
                    at = self.play_cursor
                    self.play_cursor += pcm.size / RECEIVE_SAMPLE_RATE

                    if frames and self.viseme_tracker:
                        frames = self.viseme_tracker.frames(frames, hop)
                        self.ui.push_visemes(frames, hop, at)
                        self.out_level = max(f[0] for f in frames)
                    else:
                        self.ui.set_audio_level(lvl)
                        self.out_level = lvl
                except Exception:
                    pass

                try:
                    if mobile is None or mobile.desktop_enabled():
                        await asyncio.to_thread(stream.write, bytes(batch))
                    if mobile is not None:
                        mobile.push_output_audio(bytes(batch))
                    last_audio = time.monotonic()
                except asyncio.CancelledError:
                    raise
        finally:
            if is_speaking:
                is_speaking = False
                self.set_speaking(False)
            try:
                stream.stop()
                stream.close()
            except Exception:
                pass
