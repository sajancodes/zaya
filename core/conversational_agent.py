"""Zaya Conversational Intelligence & Follow-up Resolution Engine.
Resolves context-dependent follow-up queries, prevents assistant feedback loops,
handles audio playback vs task cancellation, and enforces safety gates on ambiguous references.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any

from core import audit


@dataclass
class ConversationTurn:
    speaker: str  # "user" or "zaya"
    text: str
    timestamp: float = field(default_factory=time.time)
    options: list[str] = field(default_factory=list)
    action_pending: dict[str, Any] | None = None


@dataclass
class FollowUpResolution:
    resolved_text: str
    intent: str  # "normal", "clarify", "repeat", "summarize", "select_option", "stop_speech", "cancel_task", "continue"
    selected_option: str | None = None
    requires_confirmation: bool = False
    confirmation_reason: str | None = None
    confidence: float = 1.0


class ConversationalAgent:
    """Manages short-term conversation context, resolves contextual references,
    prevents acoustic feedback loops, and disarms prompt injections.
    """

    MAX_HISTORY_TURNS = 5
    ECHO_WINDOW_SECONDS = 8.0

    def __init__(self) -> None:
        self.history: list[ConversationTurn] = []
        self._recent_zaya_utterances: list[tuple[str, float]] = []

    def sanitize_text(self, text: str) -> str:
        # Redact password phrases like "password is ..." or "password: ..."
        text = re.sub(r'(?i)\b(?:password|pass|pin)\s+(?:is|was)\s+[^\s,;]+', 'password is [REDACTED]', text)
        text = re.sub(r'(?i)\b(?:api[_\s-]?key|token|secret|password|bearer)\s*[:=]\s*[^\s,;]+', '[REDACTED]', text)
        text = re.sub(r'\bAIza[\w-]{15,}\b', '[REDACTED]', text)
        return audit.redact(text)

    def record_user_turn(self, text: str) -> None:
        sanitized = self.sanitize_text(text.strip())
        self.history.append(ConversationTurn(speaker="user", text=sanitized))
        self._prune_history()

    def record_assistant_turn(self, text: str, options: list[str] | None = None, action_pending: dict | None = None) -> None:
        clean = text.strip()
        self.history.append(ConversationTurn(
            speaker="zaya",
            text=clean,
            options=options or [],
            action_pending=action_pending
        ))
        now = time.time()
        self._recent_zaya_utterances.append((clean.lower(), now))
        # Keep only recent utterances within echo window
        self._recent_zaya_utterances = [u for u in self._recent_zaya_utterances if now - u[1] <= self.ECHO_WINDOW_SECONDS * 2]
        self._prune_history()

    def _prune_history(self) -> None:
        if len(self.history) > self.MAX_HISTORY_TURNS:
            self.history = self.history[-self.MAX_HISTORY_TURNS:]

    def is_acoustic_feedback_loop(self, recognized_text: str) -> bool:
        """Detects if incoming speech is an acoustic echo of what Zaya just spoke."""
        clean = recognized_text.strip().lower()
        if not clean or len(clean) < 4:
            return False

        now = time.time()
        for utterance, timestamp in self._recent_zaya_utterances:
            if now - timestamp <= self.ECHO_WINDOW_SECONDS:
                if clean in utterance or utterance in clean:
                    return True
                # Similarity for substrings of 4+ words
                words = clean.split()
                if len(words) >= 4 and " ".join(words[:4]) in utterance:
                    return True
        return False

    def resolve_follow_up(self, user_input: str, is_task_running: bool = False) -> FollowUpResolution:
        """Resolves follow-up queries against conversation context and task state."""
        raw = user_input.strip()
        clean = raw.lower()

        # 1. Acoustic echo guard
        if self.is_acoustic_feedback_loop(raw):
            return FollowUpResolution(
                resolved_text="",
                intent="echo_ignored",
                confidence=0.0
            )

        # 2. Audio Playback Stop / Silence
        if clean in {"stop speaking", "be quiet", "silence", "stop talking", "shut up", "mute"}:
            return FollowUpResolution(
                resolved_text="stop speaking",
                intent="stop_speech",
                confidence=1.0
            )

        # 3. Task Cancellation (distinct from speech stop)
        if clean in {"cancel task", "abort task", "stop the task", "cancel running task", "stop task"}:
            return FollowUpResolution(
                resolved_text="cancel task",
                intent="cancel_task",
                confidence=1.0
            )

        # Single word "cancel" or "stop"
        if clean in {"cancel", "stop", "abort"}:
            if is_task_running:
                return FollowUpResolution(
                    resolved_text="cancel task",
                    intent="cancel_task",
                    confidence=0.9
                )
            return FollowUpResolution(
                resolved_text="stop speaking",
                intent="stop_speech",
                confidence=0.9
            )

        # 4. Memory Operations (Consent, Query, Update, Exclusion, Clear)
        if clean.startswith("remember this preference") or clean.startswith("remember that") or clean.startswith("remember to") or clean.startswith("remember "):
            content = re.sub(r"(?i)^remember\s+(?:this\s+preference[:\s]*|that\s+|to\s+)?", "", raw).strip()
            return FollowUpResolution(
                resolved_text=content,
                intent="remember",
                confidence=0.95
            )

        if clean.startswith("what do you remember") or clean.startswith("tell me what you remember"):
            query = re.sub(r"(?i)^(?:what\s+do\s+you\s+remember|tell\s+me\s+what\s+you\s+remember)\s*(?:about\s+)?", "", raw).strip()
            return FollowUpResolution(
                resolved_text=query,
                intent="query_memory",
                confidence=0.95
            )

        if clean in {"do not remember this", "don't remember this", "do not remember that", "don't remember that", "forget this"}:
            return FollowUpResolution(
                resolved_text="",
                intent="refuse_memory",
                confidence=1.0
            )

        if clean.startswith("stop using this information") or clean.startswith("stop using that") or clean.startswith("stop using "):
            target = re.sub(r"(?i)^stop\s+using\s+(?:this\s+information|that|this)?\s*", "", raw).strip()
            return FollowUpResolution(
                resolved_text=target or "current_topic",
                intent="stop_using_memory",
                confidence=0.95
            )

        if clean in {"clear my saved memories", "clear saved memories", "clear all memories", "wipe my memories"}:
            return FollowUpResolution(
                resolved_text="clear memories",
                intent="clear_memory",
                requires_confirmation=True,
                confirmation_reason="Clearing memories will permanently delete all stored preferences and project notes.",
                confidence=1.0
            )

        if clean.startswith("update that memory") or clean.startswith("update memory"):
            val = re.sub(r"(?i)^update\s+(?:that\s+memory|memory)[:\s]*", "", raw).strip()
            return FollowUpResolution(
                resolved_text=val,
                intent="update_memory",
                confidence=0.95
            )

        # Find the last assistant turn
        last_zaya = next((t for t in reversed(self.history) if t.speaker == "zaya"), None)

        # 4. "Explain that again" / "Say that again"
        if clean in {"explain that again", "explain again", "say that again", "repeat that", "what did you say", "repeat"}:
            if last_zaya:
                return FollowUpResolution(
                    resolved_text=f"Please re-explain: {last_zaya.text}",
                    intent="repeat",
                    confidence=0.95
                )
            return FollowUpResolution(
                resolved_text=user_input,
                intent="normal",
                confidence=0.5
            )

        # 5. "Make it shorter" / "Summarize that"
        if clean in {"make it shorter", "summarize that", "shorter please", "too long", "give me the short version", "tldr"}:
            if last_zaya:
                return FollowUpResolution(
                    resolved_text=f"Summarize this in 1-2 short sentences: {last_zaya.text}",
                    intent="summarize",
                    confidence=0.95
                )
            return FollowUpResolution(
                resolved_text=user_input,
                intent="normal",
                confidence=0.5
            )

        # 6. Option selection: "Do the second option", "Option 1", "Pick the first"
        option_match = re.search(r"(?:do|pick|choose|select|take)?\s*(?:the\s+)?(first|second|third|fourth|fifth|1st|2nd|3rd|4th|5th|option\s+[1-5]|[1-5])(?:\s+option)?", clean)
        if option_match and last_zaya and (last_zaya.options or self._extract_options_from_text(last_zaya.text)):
            available_options = last_zaya.options or self._extract_options_from_text(last_zaya.text)
            ord_str = option_match.group(1).replace("option", "").strip()
            idx = self._ordinal_to_index(ord_str)

            if 0 <= idx < len(available_options):
                chosen = available_options[idx]
                # Check if chosen option is consequential
                consequential = any(w in chosen.lower() for w in {"delete", "purchase", "pay", "send", "transfer", "wipe"})
                return FollowUpResolution(
                    resolved_text=chosen,
                    intent="select_option",
                    selected_option=chosen,
                    requires_confirmation=consequential,
                    confirmation_reason=f"Option '{chosen}' involves permanent changes or side effects." if consequential else None,
                    confidence=0.95
                )

        # 7. Ambiguous "Continue" / "Go ahead"
        if clean in {"continue", "go ahead", "proceed", "yes continue"}:
            if last_zaya and last_zaya.action_pending:
                # If there is a pending consequential action, continue CANNOT bypass confirmation!
                is_consequential = last_zaya.action_pending.get('consequential', False)
                return FollowUpResolution(
                    resolved_text="continue",
                    intent="continue",
                    requires_confirmation=is_consequential,
                    confirmation_reason="Please explicitly confirm the specific action before proceeding." if is_consequential else None,
                    confidence=0.9
                )
            return FollowUpResolution(
                resolved_text="continue",
                intent="continue",
                confidence=0.8
            )

        # Default: normal conversation turn
        return FollowUpResolution(
            resolved_text=user_input,
            intent="normal",
            confidence=1.0
        )

    def _ordinal_to_index(self, s: str) -> int:
        s = s.strip().lower()
        mapping = {
            "first": 0, "1st": 0, "1": 0,
            "second": 1, "2nd": 1, "2": 1,
            "third": 2, "3rd": 2, "3": 2,
            "fourth": 3, "4th": 3, "4": 3,
            "fifth": 4, "5th": 4, "5": 4,
        }
        return mapping.get(s, -1)

    def _extract_options_from_text(self, text: str) -> list[str]:
        """Extracts numbered or bulleted options from assistant response text."""
        options = []
        for line in text.splitlines():
            line = line.strip()
            # 1. Option / - Option / • Option
            m = re.match(r"^(?:[0-9]+[.)]|[-*•])\s+(.+)$", line)
            if m:
                options.append(m.group(1).strip())
        return options

    def assemble_prompt_context(self, user_query: str, max_chars: int = 1200) -> str:
        """Assembles bounded memory and knowledge context for the current user turn."""
        from core.personal_memory import get_memory_brain
        brain = get_memory_brain()
        mem_context = brain.assemble_context(user_query, max_chars=max_chars)
        know_context = brain.format_knowledge_for_context(user_query, max_chars=max_chars)
        parts = [p for p in (mem_context, know_context) if p]
        return "\n".join(parts)

