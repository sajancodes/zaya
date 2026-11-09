"""Tests for Small-Model Efficiency, Tool Budgeting, and Schema Minification.
Created and developed by Sajan Rai for Zaya.
"""
from __future__ import annotations

import pytest

from core.small_model_optimizer import (
    SmallModelOptimizer,
    get_small_model_optimizer,
    get_tool_budget_for_model,
)


class TestSmallModelOptimizer:
    def test_tool_budget_allocation(self):
        assert get_tool_budget_for_model("ollama/llama3.2:1b") == 5
        assert get_tool_budget_for_model("groq/llama-3.1-8b-instant") == 5
        assert get_tool_budget_for_model("groq/llama-3.3-70b-versatile") == 12
        assert get_tool_budget_for_model("gemini-2.5-flash") == 40
        assert get_tool_budget_for_model("openai/gpt-4o") == 40

    def test_minify_tool_schema(self):
        opt = SmallModelOptimizer()
        verbose_schema = {
            "name": "test_tool",
            "description": "  A   tool    with    redundant     spaces   ",
            "$schema": "http://json-schema.org/draft-07/schema#",
            "additionalProperties": False,
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "param1": {
                        "type": "STRING",
                        "description": "  first   param   description  ",
                        "additionalProperties": False,
                    }
                },
                "required": ["param1"],
            },
        }

        minified = opt.minify_tool_schema(verbose_schema)
        assert minified["description"] == "A tool with redundant spaces"
        assert "$schema" not in minified
        assert "additionalProperties" not in minified
        assert minified["parameters"]["properties"]["param1"]["description"] == "first param description"
        assert minified["parameters"]["required"] == ["param1"]

    def test_intent_based_tool_pruning(self):
        opt = SmallModelOptimizer()
        available = [
            {"name": "weather", "description": "Get weather for a city", "parameters": {"properties": {"city": {}}}},
            {"name": "calculator", "description": "Perform math operations", "parameters": {"properties": {"expr": {}}}},
            {"name": "flight_search", "description": "Search commercial airline flights", "parameters": {"properties": {"origin": {}, "dest": {}}}},
            {"name": "spotify_player", "description": "Control music playback", "parameters": {"properties": {"song": {}}}},
            {"name": "send_email", "description": "Send an email message", "parameters": {"properties": {"recipient": {}}}},
            {"name": "screen_peeler", "description": "Extract text from screen region", "parameters": {"properties": {"region": {}}}},
        ]

        # Query about flights
        selected = opt.select_tools_for_query("Can you find flights from New York to London tomorrow?", available, max_tools=2)
        assert len(selected) == 2
        selected_names = [t["name"] for t in selected]
        assert "flight_search" in selected_names

    def test_context_window_compression(self):
        opt = SmallModelOptimizer()
        messages = [
            {"role": "system", "content": "You are Zaya."},
            {"role": "user", "content": "A" * 1000},
            {"role": "assistant", "content": "B" * 1000},
            {"role": "user", "content": "C" * 1000},
            {"role": "assistant", "content": "Recent reply"},
            {"role": "user", "content": "Current question"},
        ]

        compressed = opt.compress_history(messages, max_char_budget=1500)
        # Should retain system message and most recent turns, with omitted notice
        assert compressed[0]["role"] == "system"
        assert "omitted for brevity" in compressed[1]["content"]
        assert compressed[-1]["content"] == "Current question"
