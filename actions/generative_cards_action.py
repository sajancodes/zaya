"""Interactive Generative Dashboard Cards Action.
Created and developed by Sajan Rai for Zaya.
"""
from __future__ import annotations

import json
from typing import Any, Dict

from core.generative_cards import get_card_deck


def handle_generative_cards(
    action: str = "list",
    card_id: str = "",
    title: str = "",
    subtitle: str = "",
    card_type: str = "metric",
    badge: str = "",
    data_json: str = "",
    actions_json: str = "",
) -> str:
    """Create, list, or dismiss interactive dashboard cards for HUD and companion."""
    deck = get_card_deck()

    if action == "list":
        cards = deck.list_active_cards()
        return json.dumps({"status": "success", "count": len(cards), "cards": cards})

    elif action == "create":
        if not title:
            return "Error: title is required to create a card."

        data = json.loads(data_json) if data_json else {}
        card_actions = json.loads(actions_json) if actions_json else []

        card = deck.create_card(
            title=title,
            subtitle=subtitle,
            card_type=card_type,
            badge=badge or None,
            data=data,
            actions=card_actions,
        )
        return json.dumps({
            "status": "success",
            "card_id": card.card_id,
            "title": card.title,
            "message": f"Interactive card '{title}' presented on display.",
        })

    elif action == "dismiss":
        if not card_id:
            return "Error: card_id is required to dismiss a card."
        ok = deck.dismiss_card(card_id)
        return json.dumps({"status": "success" if ok else "failed", "dismissed": ok})

    elif action == "clear":
        deck.clear()
        return json.dumps({"status": "success", "message": "All cards cleared."})

    return f"Unknown cards action: '{action}'."


TOOL = {
    "name": "dashboard_cards",
    "description": (
        "Create, display, or dismiss interactive cards on the Desktop HUD and Remote Companion. "
        "Supports metrics, comparison tables, progress gauges, and action buttons."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["create", "list", "dismiss", "clear"],
                "description": "Card deck action.",
            },
            "card_id": {
                "type": "STRING",
                "description": "Card identifier for dismissal.",
            },
            "title": {
                "type": "STRING",
                "description": "Primary card title (e.g. 'Flight Itinerary', 'System Health', 'Build Status').",
            },
            "subtitle": {
                "type": "STRING",
                "description": "Secondary detail or category.",
            },
            "card_type": {
                "type": "STRING",
                "enum": ["metric", "table", "progress", "checklist", "alert", "flight"],
                "description": "Card visual layout type.",
            },
            "badge": {
                "type": "STRING",
                "description": "Optional badge label (e.g. 'LIVE', 'CHEAPEST', 'FAILED', 'HIGH').",
            },
            "data_json": {
                "type": "STRING",
                "description": "JSON object with key-value pairs or rows for the card body.",
            },
            "actions_json": {
                "type": "STRING",
                "description": "JSON array of action buttons (e.g. [{'label': 'Book Now', 'action_type': 'url', 'payload': {'url': '...'}}]).",
            },
        },
        "required": ["action"],
    },
    "handler": handle_generative_cards,
}
