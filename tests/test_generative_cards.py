"""Tests for Interactive Generative Dashboard Cards (Cycle 73).
Created and developed by Sajan Rai for Zaya.
"""
from __future__ import annotations

import json
from unittest.mock import patch
import pytest

from core.generative_cards import GenerativeCardDeck, GenerativeCard
from actions.generative_cards_action import handle_generative_cards


class TestGenerativeCards:
    def test_create_and_list_cards(self):
        deck = GenerativeCardDeck()
        card = deck.create_card(
            title="CPU Pressure",
            subtitle="Diagnostic Alert",
            card_type="metric",
            badge="HIGH",
            data={"usage": "92%", "cores": 16},
            actions=[{"label": "Kill Hot Process", "action_type": "tool_call"}],
        )

        assert card.card_id.startswith("card_")
        assert card.title == "CPU Pressure"
        assert card.badge == "HIGH"
        assert len(card.actions) == 1

        active = deck.list_active_cards()
        assert len(active) == 1
        assert active[0]["title"] == "CPU Pressure"

    def test_dismiss_and_clear_cards(self):
        deck = GenerativeCardDeck()
        c1 = deck.create_card("Card 1")
        c2 = deck.create_card("Card 2")
        assert len(deck.list_active_cards()) == 2

        ok = deck.dismiss_card(c1.card_id)
        assert ok is True
        active = deck.list_active_cards()
        assert len(active) == 1
        assert active[0]["card_id"] == c2.card_id

        deck.clear()
        assert len(deck.list_active_cards()) == 0


class TestGenerativeCardsAction:
    def test_action_create_list_and_dismiss(self):
        create_res = handle_generative_cards(
            action="create",
            title="Flight Kathmandu to Pokhara",
            card_type="flight",
            badge="LOWEST FARE",
            data_json=json.dumps({"airline": "Buddha Air", "price": "$45", "depart": "10:30 AM"}),
            actions_json=json.dumps([{"label": "Select", "action_type": "url", "payload": {"url": "https://example.com"}}]),
        )
        create_data = json.loads(create_res)
        assert create_data["status"] == "success"
        card_id = create_data["card_id"]

        list_res = handle_generative_cards(action="list")
        list_data = json.loads(list_res)
        assert list_data["count"] >= 1

        dismiss_res = handle_generative_cards(action="dismiss", card_id=card_id)
        dismiss_data = json.loads(dismiss_res)
        assert dismiss_data["status"] == "success"
        assert dismiss_data["dismissed"] is True
