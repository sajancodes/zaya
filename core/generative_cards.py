"""Interactive Generative Dashboard Cards.
Created and developed by Sajan Rai for Zaya.

Declarative visual cards with metrics, tables, progress indicators, and interactive action buttons.
Dispatches real-time UI events to the Desktop HUD and Remote Companion Dashboard.
"""
from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class CardAction:
    label: str
    action_type: str  # tool_call, url, dismiss, prompt
    payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "label": self.label,
            "action_type": self.action_type,
            "payload": self.payload,
        }


@dataclass
class GenerativeCard:
    card_id: str
    title: str
    subtitle: str = ""
    card_type: str = "metric"  # metric, table, progress, checklist, alert, flight
    badge: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)
    actions: List[CardAction] = field(default_factory=list)
    created_at: float = field(default_factory=time.monotonic)
    ttl_seconds: Optional[float] = None
    is_dismissed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "card_id": self.card_id,
            "title": self.title,
            "subtitle": self.subtitle,
            "card_type": self.card_type,
            "badge": self.badge,
            "data": self.data,
            "actions": [a.to_dict() for a in self.actions],
            "created_at": self.created_at,
            "is_dismissed": self.is_dismissed,
        }


class GenerativeCardDeck:
    """Manages active interactive cards displayed on HUD and Companion."""

    def __init__(self, max_cards: int = 50) -> None:
        self._cards: Dict[str, GenerativeCard] = {}
        self._lock = threading.RLock()
        self._max_cards = max_cards

    def create_card(
        self,
        title: str,
        subtitle: str = "",
        card_type: str = "metric",
        badge: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        actions: Optional[List[Dict[str, Any]]] = None,
        ttl_seconds: Optional[float] = None,
    ) -> GenerativeCard:
        card_id = f"card_{uuid.uuid4().hex[:8]}"
        action_objs = [
            CardAction(
                label=a.get("label", "Action"),
                action_type=a.get("action_type", "tool_call"),
                payload=a.get("payload", {}),
            )
            for a in (actions or [])
        ]

        card = GenerativeCard(
            card_id=card_id,
            title=title,
            subtitle=subtitle,
            card_type=card_type,
            badge=badge,
            data=data or {},
            actions=action_objs,
            ttl_seconds=ttl_seconds,
        )

        with self._lock:
            # Evict oldest if exceeding max_cards
            if len(self._cards) >= self._max_cards:
                oldest_id = min(self._cards.keys(), key=lambda k: self._cards[k].created_at)
                del self._cards[oldest_id]
            self._cards[card_id] = card

        # Publish event
        try:
            from core.event_bus import bus
            bus.publish("ui.card_created", card=card.to_dict())
        except Exception:
            pass

        return card

    def get_card(self, card_id: str) -> Optional[GenerativeCard]:
        with self._lock:
            card = self._cards.get(card_id)
            if card and not card.is_dismissed:
                return card
            return None

    def list_active_cards(self) -> List[Dict[str, Any]]:
        with self._lock:
            cards = [c for c in self._cards.values() if not c.is_dismissed]
        cards.sort(key=lambda c: c.created_at, reverse=True)
        return [c.to_dict() for c in cards]

    def dismiss_card(self, card_id: str) -> bool:
        with self._lock:
            card = self._cards.get(card_id)
            if not card or card.is_dismissed:
                return False
            card.is_dismissed = True

        try:
            from core.event_bus import bus
            bus.publish("ui.card_dismissed", card_id=card_id)
        except Exception:
            pass

        return True

    def clear(self) -> None:
        with self._lock:
            self._cards.clear()


# ── Global Singleton ─────────────────────────────────────────────────────────

_deck: Optional[GenerativeCardDeck] = None


def get_card_deck() -> GenerativeCardDeck:
    global _deck
    if _deck is None:
        _deck = GenerativeCardDeck()
    return _deck
