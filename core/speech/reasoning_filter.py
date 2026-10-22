"""Streaming state machine that keeps private reasoning out of speech/history."""

from __future__ import annotations

import re
from dataclasses import dataclass

_OPEN = re.compile(r"<\s*(think|thinking|reasoning)(?:\s[^>]*)?>", re.IGNORECASE)
_CLOSE = re.compile(r"<\s*/\s*(think|thinking|reasoning)\s*>", re.IGNORECASE)
_TAGS = (
    "<think", "<thinking", "<reasoning",
    "</think", "</thinking", "</reasoning",
)


@dataclass(frozen=True)
class FilterOutput:
    display: str = ""
    speech: str = ""
    reasoning: str = ""
    reasoning_started: bool = False
    reasoning_ended: bool = False

    def __bool__(self) -> bool:
        return bool(self.display or self.speech or self.reasoning)


def _could_be_tag(value: str) -> bool:
    compact = re.sub(r"\s+", "", value.lower())
    if not compact.startswith("<"):
        return False
    if len(compact) > 32:
        return False
    return any(tag.startswith(compact) for tag in _TAGS) or any(
        compact.startswith(tag) and not compact.endswith(">") for tag in _TAGS
    )


class ReasoningFilter:
    """Incremental filter able to split tags across arbitrary chunk boundaries."""

    def __init__(self) -> None:
        self._buffer = ""
        self._reasoning = False
        self._opened = False

    @property
    def in_reasoning(self) -> bool:
        return self._reasoning

    def feed(self, text: str) -> FilterOutput:
        if not text:
            return FilterOutput()
        self._buffer += str(text)
        display: list[str] = []
        reasoning: list[str] = []
        started = False
        ended = False
        while self._buffer:
            if self._reasoning:
                match = _CLOSE.search(self._buffer)
                if match:
                    reasoning.append(self._buffer[:match.start()])
                    self._buffer = self._buffer[match.end():]
                    self._reasoning = False
                    ended = True
                    continue
                index = self._buffer.rfind("<")
                if index < 0:
                    reasoning.append(self._buffer)
                    self._buffer = ""
                    break
                if index > 0:
                    reasoning.append(self._buffer[:index])
                    self._buffer = self._buffer[index:]
                if _could_be_tag(self._buffer):
                    break
                reasoning.append(self._buffer)
                self._buffer = ""
                break

            match = _OPEN.search(self._buffer)
            if match:
                display.append(self._buffer[:match.start()])
                self._buffer = self._buffer[match.end():]
                self._reasoning = True
                started = not self._opened
                self._opened = True
                continue
            index = self._buffer.rfind("<")
            if index < 0:
                display.append(self._buffer)
                self._buffer = ""
                break
            if index > 0:
                display.append(self._buffer[:index])
                self._buffer = self._buffer[index:]
            if _could_be_tag(self._buffer):
                break
            display.append(self._buffer)
            self._buffer = ""
            break

        return FilterOutput(
            display="".join(display),
            speech="".join(display),
            reasoning="".join(reasoning),
            reasoning_started=started,
            reasoning_ended=ended,
        )

    def flush(self) -> FilterOutput:
        """Release normal text at end of stream; never leak unclosed reasoning."""
        if self._reasoning:
            self._buffer = ""
            self._reasoning = False
            return FilterOutput(reasoning_ended=True)
        text, self._buffer = self._buffer, ""
        return FilterOutput(display=text, speech=text)
