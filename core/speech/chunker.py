"""Natural speech boundaries without breaking numbers, versions or URLs."""

from __future__ import annotations

import re

_SENTENCE = set(".!?。！？؟۔။")
_CLAUSE = set(",;:，；：、")
_ABBREVIATIONS = {
    "mr", "mrs", "ms", "dr", "prof", "sr", "jr", "st", "vs", "etc", "e.g", "i.e",
    "no", "fig", "approx", "dept", "est", "inc", "ltd", "co", "corp", "u.s", "u.k",
}


class SemanticChunker:
    """Accumulates streamed tokens and releases speakable clauses/sentences."""

    def __init__(self, max_chars: int = 220, clause_chars: int = 150,
                 min_chars: int = 12):
        self.max_chars = max(40, int(max_chars))
        self.clause_chars = max(40, min(self.max_chars, int(clause_chars)))
        self.min_chars = max(1, int(min_chars))
        self._buffer = ""

    def feed(self, text: str) -> list[str]:
        if text:
            self._buffer += str(text)
        chunks: list[str] = []
        while self._buffer:
            boundary = self._sentence_boundary(self._buffer)
            if boundary is not None:
                size, consume = boundary
                chunks.append(self._buffer[:size].strip())
                self._buffer = self._buffer[consume:]
                continue
            if len(self._buffer) >= self.clause_chars:
                boundary = self._clause_boundary(self._buffer)
                if boundary is not None:
                    size, consume = boundary
                    chunks.append(self._buffer[:size].strip())
                    self._buffer = self._buffer[consume:]
                    continue
            if len(self._buffer) > self.max_chars:
                boundary = self._hard_boundary(self._buffer)
                size, consume = boundary
                chunks.append(self._buffer[:size].strip())
                self._buffer = self._buffer[consume:]
                continue
            break
        return [chunk for chunk in chunks if chunk]

    def flush(self) -> list[str]:
        text = self._buffer.strip()
        self._buffer = ""
        return [text] if text else []

    @staticmethod
    def _inside_url(text: str, index: int) -> bool:
        start = max(text.rfind(" ", 0, index), text.rfind("\n", 0, index))
        token = text[start + 1:index + 1]
        if "://" in token or token.lower().startswith("www."):
            # A URL ends at whitespace, not at its dots.
            return not any(ch.isspace() for ch in text[index + 1:index + 2])
        return False

    @classmethod
    def _sentence_boundary(cls, text: str):
        for index, char in enumerate(text):
            if char not in _SENTENCE:
                continue
            if char == ".":
                if index + 1 < len(text) and text[index + 1].isdigit():
                    continue
                if index > 0 and text[index - 1].isdigit() and index + 1 < len(text) and text[index + 1].isdigit():
                    continue
                if cls._inside_url(text, index):
                    continue
                prefix = text[:index].strip()
                word = re.split(r"[\s(]", prefix)[-1].strip().lower()
                if word in _ABBREVIATIONS:
                    continue
            if index + 1 < len(text) and not text[index + 1].isspace() and char in ".!?":
                # "3.14", "v1.2", "example.com" stay intact unless followed by
                # whitespace or end of the current buffer.
                continue
            if index + 1 >= len(text):
                return (index + 1, index + 1)
            consume = index + 1
            while consume < len(text) and text[consume].isspace():
                consume += 1
            return (index + 1, consume)
        return None

    def _clause_boundary(self, text: str):
        best = None
        for index, char in enumerate(text):
            if char in _CLAUSE:
                if char == "." and self._inside_url(text, index):
                    continue
                best = index
                if index >= self.clause_chars:
                    break
        if best is None or best < self.min_chars:
            return None
        consume = best + 1
        while consume < len(text) and text[consume].isspace():
            consume += 1
        return (best + 1, consume)

    def _hard_boundary(self, text: str):
        limit = min(self.max_chars, len(text))
        cut = max(text.rfind(" ", 0, limit), text.rfind("\n", 0, limit))
        if cut < self.min_chars:
            cut = limit
        return (cut, cut)
