"""Tests for the hydrogen processing rung.

The realtime conversation stays on gemini-3.8-live. SMART one-shot work may
lead with the processing model, but it must always be able to fall back to the
existing Live/REST ladder without touching the live session.
"""
import io
from types import SimpleNamespace

import pytest
from google.genai import types as gtypes
from PIL import Image

from core import gemini


class _FakeInteractions:
    def __init__(self):
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(output_text="answer")


class _FakeClient:
    def __init__(self):
        self.interactions = _FakeInteractions()
        self.closed = False

    def close(self):
        self.closed = True


@pytest.fixture
def fake_client(monkeypatch):
    fake = _FakeClient()
    monkeypatch.setattr(gemini, "client", lambda **kwargs: fake)
    return fake


@pytest.fixture
def fake_pool(monkeypatch):
    from core import gemini_keys
    monkeypatch.setattr(gemini_keys.pool, "keys", lambda: ["test-key"])
    monkeypatch.setattr(gemini_keys.pool, "select", lambda resource="": "test-key")
    monkeypatch.setattr(gemini_keys.pool, "limited", lambda *a, **k: None)
    return gemini_keys.pool


def test_realtime_model_is_unchanged():
    assert gemini.LIVE_MODELS[0] == "models/gemini-3.8-live"
    assert gemini.PROCESS_MODEL == "gemini-4-hydrogen"


def test_only_smart_ladder_leads_with_hydrogen():
    assert gemini._LADDERS[gemini.SMART][0] == gemini.PROCESS
    assert gemini._LADDERS[gemini.FAST][0] == gemini.LIVE
    assert gemini.PROCESS not in gemini._LADDERS[gemini.FAST]


def test_text_and_dict_inputs_are_converted():
    content = gemini._to_process_input(
        ["hello", {"inline_data": {"mime_type": "image/png", "data": b"abc"}}])
    assert content[0] == {"type": "text", "text": "hello"}
    assert content[1]["type"] == "image"
    assert content[1]["mime_type"] == "image/png"
    assert isinstance(content[1]["data"], str)


def test_part_input_is_converted():
    part = gtypes.Part.from_bytes(data=b"png-bytes", mime_type="image/png")
    content = gemini._to_process_input([part, "describe"])
    assert content[0]["type"] == "image"
    assert content[0]["mime_type"] == "image/png"
    assert content[1] == {"type": "text", "text": "describe"}


def test_pil_image_is_converted():
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), (255, 0, 0)).save(buf, format="PNG")
    content = gemini._to_process_input([Image.open(io.BytesIO(buf.getvalue())), "describe"])
    assert content[0]["type"] == "image"
    assert content[0]["mime_type"] == "image/png"
    assert content[0]["data"]


def test_tools_are_left_to_the_rest_ladder(fake_client):
    config = gtypes.GenerateContentConfig(
        tools=[{"google_search": {}}], response_mime_type="application/json")
    assert gemini._process_call("search", config, 30_000, "test-key") is None
    assert fake_client.interactions.kwargs is None


def test_process_call_maps_config(fake_client):
    config = gtypes.GenerateContentConfig(
        system_instruction="Be terse.",
        response_mime_type="application/json",
        temperature=0.2,
        max_output_tokens=64,
        thinking_config=gtypes.ThinkingConfig(thinking_budget=1024),
    )
    reply = gemini._process_call("Return JSON.", config, 30_000, "test-key")

    assert reply.text == "answer"
    assert reply.model == gemini.PROCESS_MODEL
    kwargs = fake_client.interactions.kwargs
    assert kwargs["model"] == gemini.PROCESS_MODEL
    assert kwargs["input"] == "Return JSON."
    assert kwargs["generation_config"]["thinking_level"] == "medium"
    assert kwargs["generation_config"]["temperature"] == 0.2
    assert kwargs["generation_config"]["max_output_tokens"] == 64
    assert kwargs["response_format"] == {
        "type": "text", "mime_type": "application/json"}
    assert gemini._ONE_SHOT_SYSTEM in kwargs["system_instruction"]
    assert "Be terse." in kwargs["system_instruction"]
    assert fake_client.closed


def test_explicit_thinking_level_is_honoured(fake_client):
    gemini._process_call("think", {"thinking_level": "xhigh"}, 30_000, "test-key")
    assert fake_client.interactions.kwargs["generation_config"]["thinking_level"] == "xhigh"


@pytest.mark.parametrize("budget,level", [(0, "low"), (512, "low"),
                                          (2048, "medium"), (-1, "high")])
def test_thinking_budget_maps_to_supported_levels(fake_client, budget, level):
    config = gtypes.GenerateContentConfig(
        thinking_config=gtypes.ThinkingConfig(thinking_budget=budget))
    gemini._process_call("think", config, 30_000, "test-key")
    assert fake_client.interactions.kwargs["generation_config"]["thinking_level"] == level


def test_short_deadline_skips_processing(monkeypatch, fake_pool):
    called = []
    monkeypatch.setattr(gemini, "_process_call", lambda *a, **k: called.append(1))
    monkeypatch.setattr(gemini, "_live_call", lambda *a, **k: gemini._Reply("live"))
    reply = gemini.call("look", tier=gemini.SMART, timeout_ms=8_000)
    assert reply.text == "live"
    assert called == []


def test_long_deadline_uses_processing(monkeypatch, fake_pool):
    monkeypatch.setattr(gemini, "_process_call",
                        lambda *a, **k: gemini._Reply("hydrogen"))
    reply = gemini.call("think", tier=gemini.SMART, timeout_ms=20_000)
    assert reply.text == "hydrogen"


def test_explicit_hydrogen_tier_uses_processing(monkeypatch, fake_pool):
    monkeypatch.setattr(gemini, "_process_call",
                        lambda *a, **k: gemini._Reply("hydrogen"))
    reply = gemini.call("think", tier=gemini.PROCESS_MODEL, timeout_ms=20_000)
    assert reply.text == "hydrogen"


def test_processing_failure_falls_back_without_touching_live(monkeypatch, fake_pool):
    def broken(*args, **kwargs):
        raise RuntimeError("hydrogen is down")

    monkeypatch.setattr(gemini, "_process_call", broken)
    monkeypatch.setattr(gemini, "_live_call", lambda *a, **k: gemini._Reply("live"))
    reply = gemini.call("think", tier=gemini.SMART, timeout_ms=20_000)
    assert reply.text == "live"
