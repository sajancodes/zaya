"""Fast semantic reflex router for zero-latency local execution.

Executes high-frequency utility commands (media control, screenshots, time/date)
in < 2ms using lightweight pure-NumPy n-gram vector similarity and regex trees.
No heavy models or external API calls required.
"""
from __future__ import annotations

import datetime
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
import numpy as np


@dataclass
class FastReflexResult:
    matched: bool
    intent: str = ""
    ack: str = ""
    tool_name: str = ""
    arguments: dict = field(default_factory=dict)
    data: Any = None


# Intent definitions with canonical trigger phrases
REFLEX_INTENTS: Dict[str, Dict[str, Any]] = {
    "MEDIA_PAUSE": {
        "phrases": ["pause", "pause music", "pause video", "stop music", "pause playback", "hold on pause"],
        "media_key": "pause",
        "ack": "Paused, sir.",
    },
    "MEDIA_PLAY": {
        "phrases": ["play", "resume", "resume music", "continue playing", "unpause", "resume playback"],
        "media_key": "play",
        "ack": "Resuming playback, sir.",
    },
    "MEDIA_NEXT": {
        "phrases": ["next", "next track", "next song", "skip", "skip song", "skip track"],
        "media_key": "next",
        "ack": "Next track, sir.",
    },
    "MEDIA_PREV": {
        "phrases": ["previous", "previous track", "previous song", "last track", "last song", "go back a track"],
        "media_key": "previous",
        "ack": "Previous track, sir.",
    },
    "MEDIA_MUTE": {
        "phrases": ["mute", "mute volume", "mute sound", "mute pc", "silence audio", "unmute"],
        "media_key": "mute",
        "ack": "Mute toggled, sir.",
    },
    "VOLUME_UP": {
        "phrases": ["volume up", "turn it up", "louder", "raise volume", "increase volume"],
        "media_key": "volume_up",
        "ack": "Volume up, sir.",
    },
    "VOLUME_DOWN": {
        "phrases": ["volume down", "turn it down", "quieter", "lower volume", "decrease volume"],
        "media_key": "volume_down",
        "ack": "Volume down, sir.",
    },
    "SCREENSHOT": {
        "phrases": ["screenshot", "take screenshot", "take a screenshot", "capture screen", "screen grab"],
        "tool": "computer_control",
        "args": {"action": "screenshot"},
        "ack": "Screenshot captured, sir.",
    },
    "TIME_QUERY": {
        "phrases": ["what time is it", "current time", "what's the time", "tell me the time", "what time"],
        "dynamic": "time",
    },
    "DATE_QUERY": {
        "phrases": ["what date is it", "what's today's date", "today's date", "what is today's date", "what day is today"],
        "dynamic": "date",
    },
}


def _tokenize_3grams(text: str) -> set[str]:
    clean = re.sub(r"[^\w\s]", "", text.lower().strip())
    words = clean.split()
    chars = f" {' '.join(words)} "
    return {chars[i : i + 3] for i in range(len(chars) - 2)}


class FastReflexRouter:
    def __init__(self):
        # Build vocabulary from all phrases
        vocab = set()
        self._intent_vectors: List[Tuple[str, np.ndarray]] = []
        for intent_name, intent_data in REFLEX_INTENTS.items():
            for p in intent_data["phrases"]:
                vocab.update(_tokenize_3grams(p))

        self._vocab_list = sorted(vocab)
        self._vocab_idx = {gram: i for i, gram in enumerate(self._vocab_list)}
        dim = len(self._vocab_list)

        # Precompute normalized intent vectors
        for intent_name, intent_data in REFLEX_INTENTS.items():
            for p in intent_data["phrases"]:
                v = self._vectorize(p, dim)
                norm = np.linalg.norm(v)
                if norm > 0:
                    self._intent_vectors.append((intent_name, v / norm))

    def _vectorize(self, text: str, dim: int) -> np.ndarray:
        vec = np.zeros(dim, dtype=np.float32)
        for gram in _tokenize_3grams(text):
            idx = self._vocab_idx.get(gram)
            if idx is not None:
                vec[idx] += 1.0
        return vec

    def match(self, text: str) -> Tuple[Optional[str], float]:
        """Matches input text against reflex intents. Returns (intent_name, score)."""
        clean = text.lower().strip()
        clean = re.sub(r"^(zaya|jarvis|hey zaya|please|hey)\s+", "", clean).strip()
        clean = re.sub(r"[?!.,]", "", clean).strip()

        if not clean:
            return None, 0.0

        # Exact match check first (sub-millisecond)
        for intent_name, intent_data in REFLEX_INTENTS.items():
            for p in intent_data["phrases"]:
                if clean == p:
                    return intent_name, 1.0

        # Don't evaluate long conversational queries as micro-reflexes
        if len(clean.split()) > 6:
            return None, 0.0

        # Vector cosine similarity
        query_vec = self._vectorize(clean, len(self._vocab_list))
        norm = np.linalg.norm(query_vec)
        if norm == 0:
            return None, 0.0
        query_vec /= norm

        best_intent = None
        best_score = 0.0
        for intent_name, ref_vec in self._intent_vectors:
            score = float(np.dot(query_vec, ref_vec))
            if score > best_score:
                best_score = score
                best_intent = intent_name

        if best_score >= 0.88:
            return best_intent, best_score
        return None, best_score

    def execute_intent(self, intent_name: str) -> FastReflexResult:
        """Executes a matched reflex intent locally and immediately."""
        intent_data = REFLEX_INTENTS.get(intent_name)
        if not intent_data:
            return FastReflexResult(matched=False)

        # Dynamic query intents
        if intent_data.get("dynamic") == "time":
            now_str = datetime.datetime.now().strftime("%I:%M %p").lstrip("0")
            return FastReflexResult(
                matched=True,
                intent=intent_name,
                ack=f"It is {now_str}, sir.",
                data={"time": now_str},
            )

        if intent_data.get("dynamic") == "date":
            today_str = datetime.datetime.now().strftime("%A, %B %d, %Y")
            return FastReflexResult(
                matched=True,
                intent=intent_name,
                ack=f"Today is {today_str}, sir.",
                data={"date": today_str},
            )

        # Media key dispatch
        media_key = intent_data.get("media_key")
        if media_key:
            try:
                from actions.media_controller import dispatch_media_key
                dispatch_media_key(media_key)
            except Exception as e:
                print(f"[FastReflex] Media key error: {e}")
            return FastReflexResult(
                matched=True,
                intent=intent_name,
                ack=intent_data.get("ack", "Done, sir."),
                tool_name="media_controller",
                arguments={"action": media_key},
            )

        # Tool dispatch
        tool = intent_data.get("tool")
        if tool == "computer_control":
            args = intent_data.get("args", {})
            try:
                from actions.computer_control import computer_control
                res = computer_control(args)
            except Exception as e:
                res = str(e)
            return FastReflexResult(
                matched=True,
                intent=intent_name,
                ack=intent_data.get("ack", "Done, sir."),
                tool_name=tool,
                arguments=args,
                data=res,
            )

        return FastReflexResult(matched=True, intent=intent_name, ack=intent_data.get("ack", "Done, sir."))

    def handle(self, text: str) -> Optional[FastReflexResult]:
        """Convenience method: matches and executes if confidence is sufficient."""
        intent_name, score = self.match(text)
        if intent_name and score >= 0.88:
            return self.execute_intent(intent_name)
        return None


# Global singleton instance
fast_reflex = FastReflexRouter()
