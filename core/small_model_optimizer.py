"""Small-Model Efficiency and Context Budget Optimizer for Zaya.
Created and developed by Sajan Rai for Zaya.

Optimizes tool definitions, context windows, and prompts so smaller local models
(7B/8B parameters, Ollama, Groq Llama 3.1 8B) operate reliably without context exhaustion
or function calling hallucinations.
"""
from __future__ import annotations

import copy
import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Model family tool budgets (max tool schemas sent in single request)
TOOL_BUDGETS: Dict[str, int] = {
    "local_slm": 5,      # 1B - 8B local models (Ollama llama3.2, qwen2.5-coder 7b)
    "medium_llm": 12,    # 14B - 70B models (Llama 3.3 70B, Qwen 32B)
    "frontier_cloud": 40, # Gemini 2.5 Flash, Pro, GPT-4o
}


def get_tool_budget_for_model(model_id: str) -> int:
    """Return safe maximum tool schema count based on model architecture/tier."""
    mid = model_id.lower()
    if any(k in mid for k in ["gemini", "gpt-4", "claude-3", "pro"]):
        return TOOL_BUDGETS["frontier_cloud"]
    if any(k in mid for k in ["70b", "32b", "33b"]):
        return TOOL_BUDGETS["medium_llm"]
    return TOOL_BUDGETS["local_slm"]


class SmallModelOptimizer:
    """Prunes tools, minifies schemas, and compresses context for small models."""

    def __init__(self) -> None:
        pass

    # ── Schema Minification ─────────────────────────────────────────────────

    def minify_tool_schema(self, tool_def: dict[str, Any]) -> dict[str, Any]:
        """Strip boilerplate whitespace and verbose fluff while preserving exact types and fields."""
        schema = copy.deepcopy(tool_def)

        # Minify description
        if "description" in schema and isinstance(schema["description"], str):
            schema["description"] = re.sub(r"\s+", " ", schema["description"]).strip()

        # Remove unnecessary JSON schema metadata that confuses smaller LLMs
        for meta_key in ["$schema", "$id", "title", "additionalProperties", "default"]:
            schema.pop(meta_key, None)

        params = schema.get("parameters")
        if isinstance(params, dict):
            params.pop("additionalProperties", None)
            props = params.get("properties")
            if isinstance(props, dict):
                for p_name, p_val in props.items():
                    if isinstance(p_val, dict):
                        p_val.pop("additionalProperties", None)
                        if "description" in p_val and isinstance(p_val["description"], str):
                            p_val["description"] = re.sub(r"\s+", " ", p_val["description"]).strip()

        return schema

    # ── Intent-Based Dynamic Tool Pruning ───────────────────────────────────

    def select_tools_for_query(
        self,
        query: str,
        available_tools: List[dict[str, Any]],
        max_tools: Optional[int] = None,
    ) -> List[dict[str, Any]]:
        """Select only the most relevant tools for a user query.

        Prevents small models from hallucinating when given 50+ tool schemas.
        """
        if not available_tools:
            return []

        limit = max_tools or 6
        if len(available_tools) <= limit:
            return [self.minify_tool_schema(t) for t in available_tools]

        tokens = set(re.findall(r"\b[a-zA-Z]{3,}\b", query.lower()))
        scored_tools: List[Tuple[float, dict[str, Any]]] = []

        # Core tools that should always be present if loaded
        always_include = {"recall_memory", "system_status", "screen_peeler"}

        for tool in available_tools:
            name = tool.get("name", "").lower()
            desc = tool.get("description", "").lower()
            params = tool.get("parameters", {}).get("properties", {})
            param_names = " ".join(params.keys()).lower()

            score = 0.0
            if name in always_include:
                score += 1.5

            for token in tokens:
                if token in name:
                    score += 5.0
                if token in desc:
                    score += 2.0
                if token in param_names:
                    score += 1.0

            scored_tools.append((score, tool))

        # Sort descending by score
        scored_tools.sort(key=lambda x: x[0], reverse=True)
        selected = [self.minify_tool_schema(t) for score, t in scored_tools[:limit]]
        return selected

    # ── Context Window Compression ──────────────────────────────────────────

    def compress_history(
        self,
        messages: List[dict[str, str]],
        max_char_budget: int = 4000,
    ) -> List[dict[str, str]]:
        """Keep system instructions and recent conversation within a small model's budget."""
        if not messages:
            return []

        system_msg = next((m for m in messages if m.get("role") == "system"), None)
        other_msgs = [m for m in messages if m.get("role") != "system"]

        total_chars = sum(len(m.get("content", "")) for m in other_msgs)
        if total_chars <= max_char_budget:
            return messages

        # Retain latest turns and trim older turns with a summary placeholder
        compressed: List[dict[str, str]] = []
        current_len = 0
        for msg in reversed(other_msgs):
            content_len = len(msg.get("content", ""))
            if current_len + content_len <= max_char_budget:
                compressed.insert(0, msg)
                current_len += content_len
            else:
                break

        if len(compressed) < len(other_msgs):
            summary_notice = {
                "role": "user",
                "content": f"[Earlier conversation of {len(other_msgs) - len(compressed)} turns omitted for brevity]",
            }
            compressed.insert(0, summary_notice)

        if system_msg:
            compressed.insert(0, system_msg)

        return compressed


# ── Global Singleton ─────────────────────────────────────────────────────────

_optimizer: Optional[SmallModelOptimizer] = None


def get_small_model_optimizer() -> SmallModelOptimizer:
    global _optimizer
    if _optimizer is None:
        _optimizer = SmallModelOptimizer()
    return _optimizer
