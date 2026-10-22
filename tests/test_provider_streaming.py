import json

import pytest

from core.llm.adapters.ollama import OllamaAdapter
from core.llm.adapters.openai_base import OpenAIBaseAdapter
from core.llm.registry import ProviderConfig
from core.llm.types import InvalidRequestError, LLMMessage, ToolCall


class _Response:
    status_code = 200
    headers = {}
    text = ""

    def __init__(self, lines):
        self._lines = lines

    def iter_lines(self, decode_unicode=True):
        for line in self._lines:
            yield line


def _adapter():
    return OpenAIBaseAdapter(ProviderConfig(
        "lmstudio", provider_type="lmstudio",
        base_url="http://127.0.0.1:1234/v1", model="local-model",
        local=True, requires_key=False,
    ))


def _sse(payload):
    return "data: " + json.dumps(payload)


def _tool_delta(arguments, *, name=None, call_id=None, finish=None):
    function = {"arguments": arguments}
    if name is not None:
        function["name"] = name
    part = {"index": 0, "function": function}
    if call_id is not None:
        part["id"] = call_id
    return _sse({"choices": [{"delta": {"tool_calls": [part]}, "finish_reason": finish}]})


def test_openai_compatible_stream_assembles_tool_call_across_deltas(monkeypatch):
    lines = [
        _sse({"choices": [{"delta": {"content": "Checking "}, "finish_reason": None}]}),
        _sse({"choices": [{"delta": {"content": "now."}, "finish_reason": None}]}),
        _tool_delta('{"x":', name="runtime_status", call_id="call_1"),
        _tool_delta("1}", finish="tool_calls"),
        "data: [DONE]",
    ]
    monkeypatch.setattr("core.llm.adapters.openai_base.requests.post",
                        lambda *args, **kwargs: _Response(lines))
    chunks = list(_adapter().stream_chat([LLMMessage.user("status")]))
    text = "".join(chunk.delta_text for chunk in chunks)
    calls = [call for chunk in chunks for call in chunk.tool_calls]
    assert text == "Checking now."
    assert len(calls) == 1
    assert calls[0].name == "runtime_status"
    assert calls[0].arguments == {"x": 1}
    assert calls[0].id == "call_1"


def test_ollama_native_messages_keep_assistant_tool_calls_and_tool_name():
    adapter = OllamaAdapter(ProviderConfig(
        "ollama", provider_type="ollama",
        base_url="http://127.0.0.1:11434", model="local-model",
        local=True, requires_key=False,
    ))
    messages = [
        LLMMessage.user("status"),
        LLMMessage.assistant(
            "", tool_calls=[ToolCall("runtime_status", {}, id="call_1")]),
        LLMMessage.tool_result(
            "call_1", '{"status":"success"}', name="runtime_status"),
    ]
    formatted = adapter.format_native_messages(messages)
    assert formatted[1]["tool_calls"][0]["function"]["name"] == "runtime_status"
    assert formatted[2]["role"] == "tool"
    assert formatted[2]["tool_name"] == "runtime_status"


def test_openai_compatible_stream_rejects_incomplete_tool_json(monkeypatch):
    lines = [
        _tool_delta('{"x":', name="runtime_status", call_id="call_1", finish="tool_calls"),
        "data: [DONE]",
    ]
    monkeypatch.setattr("core.llm.adapters.openai_base.requests.post",
                        lambda *args, **kwargs: _Response(lines))
    with pytest.raises(InvalidRequestError):
        list(_adapter().stream_chat([LLMMessage.user("status")]))
