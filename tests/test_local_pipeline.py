import asyncio
import threading
from types import SimpleNamespace

from core.ai.pipeline import LocalConversationPipeline, PipelineCallbacks, Utterance
from core.ai.settings import LocalPipelineSettings
from core.llm.types import LLMError, StreamChunk, ToolCall
from core.providers.speech.base import AudioChunk, SpeechError
from core.tool_result import ToolResult


class FakeSTT:
    component = "stt"

    def __init__(self, failure=""):
        self.failure = failure
        self.calls = 0

    def warmup(self):
        pass

    def transcribe(self, pcm, *, sample_rate=16000, language=None):
        self.calls += 1
        if self.failure:
            raise SpeechError("stt", self.failure, provider="fake")
        from core.providers.speech.base import STTResult
        return STTResult("transcribed speech", language="en", confidence=0.9)

    def close(self):
        pass


class FakeTTS:
    component = "tts"

    def __init__(self, failure=""):
        self.failure = failure
        self.spoken = []

    def warmup(self):
        pass

    def synthesize(self, text, *, language="", voice=""):
        if self.failure:
            raise SpeechError("tts", self.failure, provider="fake")
        self.spoken.append((text, language))
        return AudioChunk(b"\x01\x00" * 240, 24000)

    def close(self):
        pass


class FakeRouter:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def stream_route(self, **kwargs):
        self.calls.append(kwargs)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        for chunk in response:
            yield chunk


class BlockingRouter(FakeRouter):
    """Hold the first generation until the test interrupts it."""

    def __init__(self):
        super().__init__([])
        self.started = threading.Event()
        self.release = threading.Event()
        self.generation = 0

    def stream_route(self, **kwargs):
        self.calls.append(kwargs)
        self.generation += 1
        if self.generation == 1:
            self.started.set()
            self.release.wait(2.0)
            return
        yield StreamChunk("new answer")


def _pipeline(router, stt=None, tts=None, **settings):
    provider = SimpleNamespace(
        configured=True, local=True, label="Fake Local", name="fake",
        base_url="http://127.0.0.1:1", api_key="", provider_type="fake",
        capabilities={"tools": True, "streaming": True, "vision": False},
        max_tools=8, max_tool_schema_chars=6000,
    )
    events = {
        "errors": [], "display": [], "deltas": [], "user": [], "spoken": [],
        "states": [], "timings": [],
    }
    tts = tts or FakeTTS()
    pipeline = LocalConversationPipeline(
        stt=stt or FakeSTT(),
        tts=tts,
        llm=router,
        provider=provider,
        settings=LocalPipelineSettings(provider="fake", **settings),
        input_queue=asyncio.Queue(),
        audio_queue=asyncio.Queue(),
        tool_executor=lambda name, args: _tool_result(name, args),
        tool_declarations=[{
            "name": "runtime_status",
            "description": "Report the current system and runtime status",
            "parameters": {"type": "OBJECT", "properties": {}},
        }],
        system_prompt="You are Zaya.",
        callbacks=PipelineCallbacks(
            on_state=events["states"].append,
            on_user_text=lambda text, language, source: events["user"].append((text, source)),
            on_display_delta=events["deltas"].append,
            on_display_final=events["display"].append,
            on_error=events["errors"].append,
            on_timing=events["timings"].append,
        ),
    )
    return pipeline, events


async def _tool_result(name, args):
    return ToolResult("success", "System is healthy.", {"tool": name, "args": args}, side_effect=False)


def test_local_pipeline_streams_speech_and_runs_one_bounded_tool_round():
    async def scenario():
        router = FakeRouter([
            [StreamChunk("Checking."), StreamChunk(
                tool_calls=[ToolCall("runtime_status", {}, id="call-1")],
                finish_reason="tool_calls")],
            [StreamChunk("It is ready.")],
        ])
        pipeline, events = _pipeline(router)
        await pipeline.speech.start()
        await pipeline._handle_utterance(Utterance(text="status please", source="microphone"))
        for _ in range(80):
            if any("ready" in item[0] for item in pipeline.tts.spoken):
                break
            await asyncio.sleep(0.01)
        await pipeline.speech.stop()
        assert len(router.calls) == 2
        assert any(call.get("allow_failover") is False for call in router.calls)
        assert router.calls[0]["tools"]
        assert "Checking. It is ready." in events["display"][-1]
        assert ("status please", "microphone") in events["user"]
        assert any("Checking." in item[0] for item in pipeline.tts.spoken)
        assert any("It is ready." in item[0] for item in pipeline.tts.spoken)
        assert events["errors"] == []
    asyncio.run(scenario())


def test_stt_failure_is_named_and_typed_turns_still_work():
    async def scenario():
        router = FakeRouter([[StreamChunk("Typed answer.")]])
        stt = FakeSTT(failure="microphone model missing")
        pipeline, events = _pipeline(router, stt=stt)
        await pipeline.speech.start()
        await pipeline._handle_utterance(Utterance(pcm=b"\x00\x00" * 160, source="microphone"))
        assert any("STT failed" in error for error in events["errors"])
        assert stt.calls == 1
        await pipeline._handle_utterance(Utterance(text="typed question", source="typed"))
        await asyncio.sleep(0.05)
        assert stt.calls == 1
        assert "Typed answer." in events["display"][-1]
        await pipeline.speech.stop()
    asyncio.run(scenario())


def test_interruption_cancels_the_old_turn_and_accepts_the_next_one():
    async def scenario():
        router = BlockingRouter()
        pipeline, events = _pipeline(router)
        await pipeline.speech.start()
        task = asyncio.create_task(
            pipeline._handle_utterance(Utterance(text="old request", source="typed")))
        pipeline._turn_task = task
        assert await asyncio.to_thread(router.started.wait, 1.0)
        pipeline.interrupt()
        router.release.set()
        try:
            await task
        except asyncio.CancelledError:
            pass
        await pipeline._handle_utterance(
            Utterance(text="new request", source="typed"))
        await asyncio.sleep(0.05)
        assert events["display"] == ["new answer"]
        assert all("old" not in item for item in events["display"])
        await pipeline.speech.stop()
    asyncio.run(scenario())


def test_llm_failure_is_not_blamed_on_speech_components():
    async def scenario():
        router = FakeRouter([LLMError("provider offline", provider="fake")])
        pipeline, events = _pipeline(router)
        await pipeline.speech.start()
        await pipeline._handle_utterance(Utterance(text="hello", source="typed"))
        await asyncio.sleep(0.05)
        assert any(error.startswith("LLM failed:") for error in events["errors"])
        assert not any(error.startswith("STT failed") for error in events["errors"])
        assert not events["display"]
        await pipeline.speech.stop()
    asyncio.run(scenario())


def test_tts_failure_keeps_the_text_answer():
    async def scenario():
        router = FakeRouter([[StreamChunk("Text survives a voice failure.")]])
        tts = FakeTTS(failure="voice file missing")
        pipeline, events = _pipeline(router, tts=tts)
        await pipeline.speech.start()
        await pipeline._handle_utterance(Utterance(text="hello", source="typed"))
        for _ in range(80):
            if events["errors"]:
                break
            await asyncio.sleep(0.01)
        assert "Text survives a voice failure." in events["display"][-1]
        assert any("TTS failed" in error for error in events["errors"])
        # A queued sentence is not proof of audio. Only the playback path may
        # mark the speaker active, so a failed synthesis cannot trap the echo
        # guard in SPEAKING forever.
        assert "SPEAKING" not in events["states"]
        await pipeline.speech.stop()
    asyncio.run(scenario())


def test_language_fallback_chain():
    pipeline, _ = _pipeline(FakeRouter([]))
    pipeline.settings.stt_language = "es"

    # 1. Detected takes precedence
    assert pipeline.resolve_language(detected="fr", utterance_language="de") == "fr"

    # 2. Utterance language is next fallback if detected is empty
    assert pipeline.resolve_language(detected="", utterance_language="de") == "de"

    # 3. Settings STT language is used if detected and utterance are empty
    assert pipeline.resolve_language(detected="", utterance_language="") == "es"

    # 4. Empty string fallback if settings also empty
    pipeline.settings.stt_language = ""
    assert pipeline.resolve_language(detected="", utterance_language="") == ""

