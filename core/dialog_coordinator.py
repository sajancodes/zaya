"""Multi-Modal Natural Dialog State Machine & Mixed-Initiative Context Coordinator for Zaya.
Created and developed by Sajan Rai.

Coordinates conversational state transitions, contextual pronoun resolution,
slot filling, and nested side-query resumption for Jarvis-grade fluid dialogue.
"""
from __future__ import annotations

import logging
import re
import threading
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class DialogState(str, Enum):
    IDLE = "idle"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    AWAITING_DISAMBIGUATION = "awaiting_disambiguation"
    AWAITING_SLOT_FILL = "awaiting_slot_fill"
    SUSPENDED_SIDE_QUERY = "suspended_side_query"


@dataclass
class DialogContext:
    state: str = DialogState.IDLE.value
    active_entity: Optional[str] = None  # e.g. "server.py", "tests", "light.desk_lamp"
    active_intent: Optional[str] = None
    pending_action: Optional[dict[str, Any]] = None
    expected_slots: list[str] = field(default_factory=list)
    filled_slots: dict[str, Any] = field(default_factory=dict)
    options: list[str] = field(default_factory=list)
    suspended_context: Optional[dict[str, Any]] = None
    updated_at: float = field(default_factory=time.time)


@dataclass
class DialogResolution:
    resolved_text: str
    state: str
    intent: str
    active_entity: Optional[str] = None
    ready_to_execute: bool = False
    action_payload: Optional[dict[str, Any]] = None
    clarification_prompt: Optional[str] = None


class DialogCoordinator:
    """Coordinates conversational context, reference resolution, and mixed-initiative states."""

    PRONOUNS_RE = re.compile(r"\b(it|that|this|the file|the server|the project)\b", re.IGNORECASE)
    AFFIRMATIVE_RE = re.compile(r"^(yes|yep|yeah|sure|confirm|proceed|do it|go ahead|ok|okay)\b", re.IGNORECASE)
    NEGATIVE_RE = re.compile(r"^(no|nope|don't|cancel|abort|stop|nevermind|forget it)\b", re.IGNORECASE)
    SIDE_QUERY_RE = re.compile(r"^(wait|hold on|by the way|quick question|what time is it|what's the weather)\b", re.IGNORECASE)

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._context = DialogContext()

    def get_context(self) -> DialogContext:
        with self._lock:
            return self._context

    def reset(self) -> None:
        with self._lock:
            self._context = DialogContext()

    def set_active_entity(self, entity: str) -> None:
        with self._lock:
            self._context.active_entity = entity.strip()
            self._context.updated_at = time.time()

    def request_confirmation(self, action_name: str, parameters: dict[str, Any], prompt: str) -> None:
        """Enter AWAITING_CONFIRMATION state before high-impact or destructive operations."""
        with self._lock:
            self._context.state = DialogState.AWAITING_CONFIRMATION.value
            self._context.pending_action = {"action": action_name, "parameters": parameters, "prompt": prompt}
            self._context.updated_at = time.time()

    def request_slot_fill(self, intent: str, entity: str, required_slot: str, prompt: str) -> None:
        """Enter AWAITING_SLOT_FILL when an argument is missing."""
        with self._lock:
            self._context.state = DialogState.AWAITING_SLOT_FILL.value
            self._context.active_intent = intent
            self._context.active_entity = entity
            self._context.expected_slots = [required_slot]
            self._context.updated_at = time.time()

    def process_turn(self, user_text: str) -> DialogResolution:
        """Process incoming speech/text and update dialog state."""
        raw = user_text.strip()
        clean = raw.lower()

        with self._lock:
            # Check timeout on pending state (expire after 120 seconds of silence)
            if self._context.state != DialogState.IDLE.value:
                if time.time() - self._context.updated_at > 120.0:
                    self._context = DialogContext()

            cur_state = self._context.state

            # 1. State: AWAITING_CONFIRMATION
            if cur_state == DialogState.AWAITING_CONFIRMATION.value:
                if self.AFFIRMATIVE_RE.search(clean):
                    action_data = self._context.pending_action
                    self._context = DialogContext(active_entity=self._context.active_entity)
                    return DialogResolution(
                        resolved_text=raw,
                        state=DialogState.IDLE.value,
                        intent="confirmed",
                        active_entity=self._context.active_entity,
                        ready_to_execute=True,
                        action_payload=action_data,
                    )
                elif self.NEGATIVE_RE.search(clean):
                    self._context = DialogContext(active_entity=self._context.active_entity)
                    return DialogResolution(
                        resolved_text=raw,
                        state=DialogState.IDLE.value,
                        intent="cancelled",
                        active_entity=self._context.active_entity,
                        ready_to_execute=False,
                    )

            # 2. State: AWAITING_SLOT_FILL
            if cur_state == DialogState.AWAITING_SLOT_FILL.value:
                # User is providing the requested slot value
                slot_name = self._context.expected_slots[0] if self._context.expected_slots else "value"
                self._context.filled_slots[slot_name] = raw
                intent = self._context.active_intent or "action"
                entity = self._context.active_entity
                self._context.state = DialogState.IDLE.value
                resolved = f"{intent} {entity} with {slot_name} {raw}".strip()
                return DialogResolution(
                    resolved_text=resolved,
                    state=DialogState.IDLE.value,
                    intent=intent,
                    active_entity=entity,
                    ready_to_execute=True,
                    action_payload={"intent": intent, "entity": entity, "slots": self._context.filled_slots},
                )

            # 3. Handle Side Query during flow
            if self.SIDE_QUERY_RE.search(clean) and self._context.active_entity:
                # Suspend current context and enter SUSPENDED_SIDE_QUERY
                self._context.suspended_context = {
                    "active_entity": self._context.active_entity,
                    "active_intent": self._context.active_intent,
                }
                self._context.state = DialogState.SUSPENDED_SIDE_QUERY.value
                return DialogResolution(
                    resolved_text=raw,
                    state=DialogState.SUSPENDED_SIDE_QUERY.value,
                    intent="side_query",
                    active_entity=self._context.active_entity,
                )

            # 4. Resume after Side Query
            if cur_state == DialogState.SUSPENDED_SIDE_QUERY.value and self._context.suspended_context:
                prev = self._context.suspended_context
                self._context.active_entity = prev.get("active_entity")
                self._context.active_intent = prev.get("active_intent")
                self._context.suspended_context = None
                self._context.state = DialogState.IDLE.value

            # 5. Pronoun & Reference Resolution in Normal Queries
            resolved_text = raw
            if self._context.active_entity and self.PRONOUNS_RE.search(clean):
                # Replace pronouns like "it", "that" with active entity
                resolved_text = self.PRONOUNS_RE.sub(self._context.active_entity, raw)

            # Update active entity if a distinct entity was mentioned
            extracted_entity = self._extract_entity_heuristic(raw)
            if extracted_entity:
                self._context.active_entity = extracted_entity

            self._context.updated_at = time.time()
            return DialogResolution(
                resolved_text=resolved_text,
                state=self._context.state,
                intent="normal",
                active_entity=self._context.active_entity,
            )

    def _extract_entity_heuristic(self, text: str) -> Optional[str]:
        """Detect referenced file, port, or module name in utterance."""
        # File pattern e.g. foo.py, app.ts, styles.css
        file_m = re.search(r"\b([A-Za-z0-9_\-]+\.(?:py|kt|ts|js|json|html|css|rs|go|xml))\b", text, re.IGNORECASE)
        if file_m:
            return file_m.group(1)
        # Port pattern e.g. port 8000
        port_m = re.search(r"\bport\s+(\d{2,5})\b", text, re.IGNORECASE)
        if port_m:
            return f"port {port_m.group(1)}"
        return None


_dialog_coord: Optional[DialogCoordinator] = None
_coord_lock = threading.Lock()


def get_dialog_coordinator() -> DialogCoordinator:
    global _dialog_coord
    with _coord_lock:
        if _dialog_coord is None:
            _dialog_coord = DialogCoordinator()
        return _dialog_coord
