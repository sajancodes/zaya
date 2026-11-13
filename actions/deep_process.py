"""Deep processing on Zaya's reasoning model.

The realtime conversation stays on gemini-3.8-live. This action is how Zaya
chooses, mid-conversation, to hand one genuinely hard request to
gemini-4-hydrogen and get the answer back. It is a text bridge only: the live
session, its audio and its barge-in path are untouched.
Created and developed by Sajan Rai for Zaya.
"""
from __future__ import annotations

import time

from google.genai import types

from core import gemini
from core.execution_policy import require_owner
from core.tool_result import ToolResult

# depth -> (thinking budget, deadline). core.gemini maps a budget to one of
# hydrogen's supported levels: <=512 low, <=2048 medium, anything higher high.
# 'minimal' is rejected by the model, so 'low' is the floor. Deadlines stay at
# or below 90s: that is already proven in the live session (file processing)
# and a tool call must not hold the conversation open longer than that.
_DEPTHS = {
    "quick": (256, 45_000),
    "standard": (1024, 75_000),
    "deep": (8192, 90_000),
}

_SYSTEM = (
    "You are the deep-processing specialist behind Zaya, a voice assistant. "
    "The realtime voice model has delegated one request to you because it needs "
    "more reasoning than a spoken turn should spend. Answer it fully and "
    "independently: reason carefully, check your own work, and return a "
    "self-contained result. Lead with the conclusion, keep prose tight, and use "
    "fenced code blocks for code. Never claim to have run a tool, read a file or "
    "seen a screen unless the request already contains that evidence."
)


def deep_process(parameters: dict, **_kwargs) -> ToolResult:
    """Run one hard request on the processing model and return its answer."""
    require_owner()

    request = str(parameters.get("request") or "").strip()
    if not request:
        return ToolResult(
            "failed",
            "Nothing was delegated: 'request' must carry the full task and its context.",
        )

    depth = str(parameters.get("depth") or "standard").strip().lower()
    budget, timeout_ms = _DEPTHS.get(depth, _DEPTHS["standard"])

    started = time.monotonic()
    try:
        reply = gemini.call(
            request,
            tier=gemini.SMART,
            config=types.GenerateContentConfig(
                system_instruction=_SYSTEM,
                thinking_config=types.ThinkingConfig(thinking_budget=budget),
            ),
            timeout_ms=timeout_ms,
        )
    except Exception as error:
        return ToolResult(
            "failed",
            f"Deep processing could not run: {type(error).__name__}: {error}",
            data={"model": gemini.PROCESS_MODEL, "depth": depth},
            retryable=True,
        )

    elapsed_ms = int((time.monotonic() - started) * 1000)
    answer = str(getattr(reply, "text", "") or "").strip()
    answered_by = str(getattr(reply, "model", "") or "")
    if not answer:
        return ToolResult(
            "failed",
            "The processing model returned no answer. Retry, or handle the request on the live model.",
            data={"model": gemini.PROCESS_MODEL, "depth": depth,
                  "elapsed_ms": elapsed_ms},
            retryable=True,
        )

    return ToolResult(
        "success",
        answer,
        data={
            "model": gemini.PROCESS_MODEL,
            "answered_by": answered_by,
            "used_fallback": bool(
                answered_by and not answered_by.endswith(gemini.PROCESS_MODEL)),
            "depth": depth,
            "elapsed_ms": elapsed_ms,
        },
    )


TOOL = {
    "name": "deep_process",
    "description": (
        "Delegate one hard request to Zaya's deep reasoning model (Gemini 4 "
        "Hydrogen) when a spoken-conversation answer is not enough: multi-step "
        "analysis, architecture or debugging, code review and rewrites, maths, "
        "long-document reasoning, or trade-off decisions. The request must be "
        "self-contained — include every fact, constraint, file excerpt or code "
        "snippet the model needs, because it cannot see this conversation. "
        "Returns the answer text for you to relay or summarise. Do not use it "
        "for simple questions, chit-chat, or anything the live model can answer "
        "directly."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "request": {
                "type": "STRING",
                "description": (
                    "The complete task with all context, constraints, code or "
                    "data needed to answer it, written as an instruction to "
                    "the reasoning model."
                ),
            },
            "depth": {
                "type": "STRING",
                "enum": ["quick", "standard", "deep"],
                "description": (
                    "Reasoning effort: quick for a focused check, standard by "
                    "default, deep for architecture or debugging. Deep can "
                    "take up to about ninety seconds."
                ),
            },
        },
        "required": ["request"],
    },
    "handler": deep_process,
}
