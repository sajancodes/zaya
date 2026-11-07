"""Dynamic conversational cue and custom trigger manager.

Enables Jarvis-grade conditional reflexes:
- Arms dynamic triggers from conversational setups (e.g. "when I say anything", "when I hum", "on my mark").
- Intercepts subsequent user speech, humming, or phrases and executes the bound action instantly.
- Eliminates cloud LLM hesitation and rigid refusals on conditional tasks.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple


@dataclass
class Cue:
    id: str
    trigger_type: str  # 'any_input', 'phrase', 'sound'
    tool_name: str     # e.g. 'video_player'
    parameters: dict   # e.g. {'action': 'play', 'source': 'Parvati', 'target': 'display'}
    trigger_phrase: str = ""
    single_shot: bool = True
    created_at: float = field(default_factory=time.monotonic)
    timeout_seconds: float = 300.0
    ack_phrase: str = "Ready on your mark, sir."
    status: str = "armed"  # 'armed', 'fired', 'expired', 'canceled'

    def is_expired(self, now: float) -> bool:
        return (now - self.created_at) > self.timeout_seconds


class CueManager:
    def __init__(self):
        self._cues: List[Cue] = []
        self._last_source: str = ""
        self.on_state_changed: Optional[Callable[[bool], None]] = None

    def arm_cue(
        self,
        trigger_type: str,
        tool_name: str,
        parameters: dict,
        trigger_phrase: str = "",
        single_shot: bool = True,
        ack_phrase: str = "Standing by, sir. Ready on your mark.",
        timeout_seconds: float = 300.0,
    ) -> Cue:
        """Arms a new dynamic cue, disarming older single-shot cues."""
        self._purge_expired()
        if single_shot:
            # Cancel prior active single shot cues
            for c in self._cues:
                if c.status == "armed" and c.single_shot:
                    c.status = "canceled"

        src = parameters.get("source") or parameters.get("query") or ""
        if src:
            self._last_source = src

        cue_id = f"cue_{int(time.monotonic() * 1000)}"
        cue = Cue(
            id=cue_id,
            trigger_type=trigger_type,
            tool_name=tool_name,
            parameters=dict(parameters),
            trigger_phrase=trigger_phrase.strip().lower(),
            single_shot=single_shot,
            created_at=time.monotonic(),
            timeout_seconds=timeout_seconds,
            ack_phrase=ack_phrase,
            status="armed",
        )
        self._cues.append(cue)
        self._notify_state()
        return cue

    def cancel_cues(self) -> int:
        """Cancel all armed cues."""
        count = 0
        for c in self._cues:
            if c.status == "armed":
                c.status = "canceled"
                count += 1
        self._notify_state()
        return count

    def has_armed_cue(self) -> bool:
        """True if at least one armed cue is currently active and unexpired."""
        self._purge_expired()
        return any(c.status == "armed" for c in self._cues)

    def get_armed_cues(self) -> List[Cue]:
        self._purge_expired()
        return [c for c in self._cues if c.status == "armed"]

    def _purge_expired(self):
        now = time.monotonic()
        for c in self._cues:
            if c.status == "armed" and c.is_expired(now):
                c.status = "expired"

    def _notify_state(self):
        if self.on_state_changed:
            try:
                self.on_state_changed(self.has_armed_cue())
            except Exception:
                pass

    def evaluate(
        self, text: str = "", is_sound: bool = False, now: Optional[float] = None
    ) -> Tuple[Optional[Cue], Optional[dict]]:
        """Evaluate input against armed cues. Returns (matched_cue, parameters) or (None, None)."""
        self._purge_expired()
        clean_text = (text or "").strip().lower()

        # Check for explicit cancellation first
        if clean_text in {"cancel", "stop", "abort", "nevermind", "forget it"}:
            self.cancel_cues()
            return None, None

        for cue in self._cues:
            if cue.status != "armed":
                continue

            matched = False
            if cue.trigger_type == "any_input":
                # Any non-empty user text or sound event triggers it
                if clean_text or is_sound:
                    matched = True

            elif cue.trigger_type == "sound":
                if is_sound or clean_text:
                    matched = True

            elif cue.trigger_type == "phrase":
                if cue.trigger_phrase and cue.trigger_phrase in clean_text:
                    matched = True
                elif cue.trigger_phrase:
                    # Token overlap check
                    cue_tokens = set(re.findall(r"\w+", cue.trigger_phrase))
                    inp_tokens = set(re.findall(r"\w+", clean_text))
                    if cue_tokens and len(cue_tokens & inp_tokens) / len(cue_tokens) >= 0.7:
                        matched = True

            if matched:
                cue.status = "fired"
                if cue.single_shot:
                    self._notify_state()
                return cue, dict(cue.parameters)

        return None, None

    def detect_cue_intent(self, text: str) -> Optional[Dict[str, Any]]:
        """Detects if the user is asking to set up a conditional trigger/cue.

        Matches setups like:
        - 'when I say anything just play Parvati on the display'
        - 'ill just hum a song randomly called ... you just play parvati song on the display'
        - 'on my mark play parvati'
        - 'when I hum play the song Parvati'
        """
        raw = text.strip()
        t = raw.lower()

        # Common trigger indicators
        has_when = bool(re.search(r"\b(when|if|whenever|on my mark|while i|as soon as)\b", t))
        has_play = bool(re.search(r"\b(play|put|open|start|show|run)\b", t))
        has_hum_or_say = bool(re.search(r"\b(hum|humming|say|sing|sound|mark|words|lines|anything)\b", t))

        if not (has_play and (has_when or has_hum_or_say or "on my mark" in t)):
            return None

        # Check for wildcard trigger types: 'anything', 'hum', 'lines', 'mark'
        is_wildcard = bool(re.search(r"\b(anything|hum|humming|lines|randomly|mark|say anything)\b", t))
        trigger_type = "any_input" if is_wildcard else "phrase"

        # Extract target song / media
        source = ""
        # 1. Look for 'play (song called |the song |the video |video |song )?<source>'
        m_play = re.search(
            r"\b(?:play|put|open|start)\s+(?:the\s+)?(?:song\s+(?:called\s+)?|video\s+(?:called\s+)?|track\s+(?:called\s+)?|music\s+(?:called\s+)?)([\w\s\'-]+?)(?:\s+(?:on|in|using)\s+(?:my\s+|the\s+)?(?:display|screen|window|browser|youtube)|$|\.|\,)",
            t,
        )
        if m_play:
            source = m_play.group(1).strip()

        if not source:
            # 2. Look for 'called <source>'
            m_called = re.search(r"\bcalled\s+([\w\s\'-]+?)(?:\s+(?:you|and|when|on|just)|$|\.|\,)", t)
            if m_called:
                source = m_called.group(1).strip()

        if not source:
            # 3. Look for 'play <source> on (the/my) display'
            m_display = re.search(r"\b(?:play|put)\s+([\w\s\'-]+?)\s+on\s+(?:the|my)\s+(?:display|screen)", t)
            if m_display:
                source = m_display.group(1).strip()

        if not source:
            # 4. Check for 'play it' / reuse previous source
            if re.search(r"\bplay\s+it\b", t) and self._last_source:
                source = self._last_source

        # Clean source
        source = re.sub(r"^(song|video|track)\s+", "", source).strip()
        source = re.sub(r"\s+(song|video|track)$", "", source).strip()

        if not source and self._last_source:
            source = self._last_source

        if not source:
            return None

        # Clean trailing fluff
        source = re.sub(r"\b(when|if|on|display|screen|just|now)\b.*$", "", source).strip()
        if not source:
            return None

        # Determine target
        target = "display"
        if "browser" in t or "brave" in t or "chrome" in t:
            target = "browser"

        ack = f"Understood, sir. Standing by on your mark for '{source}'."
        return {
            "trigger_type": trigger_type,
            "tool_name": "video_player",
            "parameters": {
                "action": "play",
                "source": source,
                "target": target,
            },
            "ack_phrase": ack,
        }


# Global singleton instance
cue_manager = CueManager()
