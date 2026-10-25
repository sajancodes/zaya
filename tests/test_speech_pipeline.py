import asyncio

from core.providers.speech.base import AudioChunk, SpeechError, resample_pcm
from core.speech.chunker import SemanticChunker
from core.speech.playback import SpeechPipeline
from core.speech.reasoning_filter import ReasoningFilter
from core.speech.text import speakable_text


def test_reasoning_filter_handles_tags_split_across_chunks():
    filter_ = ReasoningFilter()
    output = []
    for piece in ("<thi", "nk>private", " thoughts</thi", "nk>Hello", " owner."):
        output.append(filter_.feed(piece))
    display = "".join(item.display for item in output)
    reasoning = "".join(item.reasoning for item in output)
    assert display == "Hello owner."
    assert "private thoughts" in reasoning
    assert "private" not in display
    assert filter_.flush().display == ""


def test_chunker_preserves_decimals_urls_and_unicode_sentences():
    chunker = SemanticChunker(max_chars=120, clause_chars=80)
    pieces = chunker.feed(
        "Version 1.2 costs 3.50 dollars. Visit https://example.com/a.b now. "
        "これは日本語です。元気ですか？")
    joined = " ".join(pieces)
    assert "1.2" in joined
    assert "https://example.com/a.b" in joined
    assert "これは日本語です。" in joined
    assert any("元気ですか？" in piece for piece in pieces + chunker.flush())


def test_chunker_releases_a_long_clause_without_sentence_punctuation():
    chunker = SemanticChunker(max_chars=200, clause_chars=40, min_chars=5)
    pieces = chunker.feed(
        "alpha, beta, gamma, delta, epsilon, zeta, eta, theta, iota, kappa")
    assert pieces
    assert "alpha" in pieces[0]
    assert " ".join(pieces + chunker.flush()) == (
        "alpha, beta, gamma, delta, epsilon, zeta, eta, theta, iota, kappa")


def test_display_and_speakable_text_are_separate():
    text = "**Done.** See [the docs](https://example.com) `code` :sparkles:"
    assert "**Done.**" in text
    spoken = speakable_text(text)
    assert "**" not in spoken
    assert "https://example.com" not in spoken
    assert "code" in spoken
    assert "sparkles" not in spoken


def test_resample_keeps_pcm_shape_and_duration():
    pcm = (b"\x00\x01" * 16000)
    out = resample_pcm(pcm, 16000, 24000)
    assert len(out) == 48000


class SlowTTS:
    component = "tts"

    def __init__(self):
        self.spoken = []

    def warmup(self):
        pass

    def synthesize(self, text, *, language="", voice=""):
        self.spoken.append((text, language, voice))
        return AudioChunk(b"\x01\x00" * 240, 24000)

    def close(self):
        pass


class FailingTTS(SlowTTS):
    def synthesize(self, text, *, language="", voice=""):
        raise SpeechError("tts", "voice file disappeared", provider="piper")


def test_speech_pipeline_preserves_text_order_and_reports_failures():
    async def scenario():
        queue = asyncio.Queue()
        tts = SlowTTS()
        spoken = []
        failures = []
        pipeline = SpeechPipeline(
            provider=tts, audio_queue=queue,
            on_spoken=lambda text: spoken.append(text),
            on_error=lambda text: failures.append(text),
        )
        await pipeline.start()
        for text in ("one", "two", "three"):
            await pipeline.enqueue(text, language="en")
        for _ in range(80):
            if len(spoken) == 3:
                break
            await asyncio.sleep(0.01)
        await pipeline.stop()
        assert spoken == ["one", "two", "three"]
        assert failures == []

        failing = SpeechPipeline(
            provider=FailingTTS(), audio_queue=asyncio.Queue(),
            on_error=lambda text: failures.append(text),
        )
        await failing.start()
        await failing.enqueue("will fail")
        for _ in range(80):
            if failures:
                break
            await asyncio.sleep(0.01)
        await failing.stop()
        assert failures and failures[0].startswith("TTS failed")
        assert "piper" in failures[0]
    asyncio.run(scenario())
