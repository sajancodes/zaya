"""Separate the model's written answer from the copy sent to a voice."""

from __future__ import annotations

import re

_CODE_FENCE = re.compile(r"```[^\n]*\n?(.*?)```", re.DOTALL)
_INLINE_CODE = re.compile(r"`([^`]+)`")
_MARKDOWN_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_URL = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
_HTML = re.compile(r"<[^>]{1,120}>")
_MARKDOWN_MARKS = re.compile(r"(?:^|\s)[*_#>~-]{1,3}(?=\S)")
_EMOJI_SHORTCODE = re.compile(r":[a-z0-9_+\-]{2,32}:", re.IGNORECASE)
_EMOJI = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF\u200d\ufe0f]+"
)
_SPACE = re.compile(r"[ \t]+")


def display_text(value: str) -> str:
    """The original answer, preserved for the transcript and History."""
    return str(value or "")


def speakable_text(value: str, *, read_urls: bool = False) -> str:
    """Convert display text into something a voice should actually pronounce.

    This function has no storage side effect: the UI and History keep the
    original answer.
    """
    text = str(value or "")
    text = _CODE_FENCE.sub(lambda match: match.group(1), text)
    text = _INLINE_CODE.sub(lambda match: match.group(1), text)
    text = _MARKDOWN_LINK.sub(lambda match: match.group(1), text)
    if not read_urls:
        text = _URL.sub("the link", text)
    text = _HTML.sub(" ", text)
    text = _MARKDOWN_MARKS.sub(" ", text)
    text = _EMOJI_SHORTCODE.sub(" ", text)
    text = _EMOJI.sub(" ", text)
    text = text.replace("**", "").replace("__", "").replace("~~", "")
    text = text.replace("|", ", ")
    text = _SPACE.sub(" ", text)
    lines = [line.strip(" -•\t") for line in text.splitlines() if line.strip()]
    return " ".join(lines).strip()
