"""Tests for Autonomous Memory Consolidation & Dream Cycle Engine (Cycle 76).
Created and developed by Sajan Rai for Zaya.
"""
from __future__ import annotations

import json
from unittest.mock import patch
import pytest

from core.personal_memory import PersonalMemoryBrain, MemoryItem
from core.memory_consolidation import MemoryConsolidationEngine
from actions.memory_consolidation_action import handle_memory_consolidation


class TestMemoryConsolidation:
    def test_prunes_ephemeral_facts(self, tmp_path):
        brain = PersonalMemoryBrain(
            storage_path=tmp_path / "mem.json",
            knowledge_path=tmp_path / "know.json",
        )
        brain.remember("Owner's car", "Model S", "fact", explicit_consent=True)
        brain.remember("Temporary reminder", "Need to buy milk for now", "fact", explicit_consent=True)
        brain.remember("Meeting", "Right now it is raining", "fact", explicit_consent=True)

        engine = MemoryConsolidationEngine(brain=brain)
        report = engine.consolidate(dry_run=False)

        assert report.total_memories_before == 3
        assert report.ephemeral_memories_pruned == 2
        assert report.total_memories_after == 1
        active_keys = [m.key for m in brain.get_all_memories()]
        assert "Owner's car" in active_keys
        assert "Temporary reminder" not in active_keys

    def test_resolves_contradictory_preferences(self, tmp_path):
        brain = PersonalMemoryBrain(
            storage_path=tmp_path / "mem.json",
            knowledge_path=tmp_path / "know.json",
        )
        # Old preference: Light mode
        res1 = brain.remember("Theme preference", "Owner prefers Light mode theme", "preference", explicit_consent=True)
        # Newer preference: Dark mode
        res2 = brain.remember("Theme setting", "Owner switched theme to Dark mode", "preference", explicit_consent=True)

        engine = MemoryConsolidationEngine(brain=brain)
        report = engine.consolidate(dry_run=False)

        assert report.contradictions_resolved == 1
        active_memories = brain.get_all_memories()
        # Newer memory should be kept
        theme_mem = [m for m in active_memories if "theme" in m.key.lower() or "theme" in m.value.lower()]
        assert len(theme_mem) == 1
        assert "Dark mode" in theme_mem[0].value

    def test_dry_run_does_not_modify_storage(self, tmp_path):
        brain = PersonalMemoryBrain(
            storage_path=tmp_path / "mem.json",
            knowledge_path=tmp_path / "know.json",
        )
        brain.remember("Temp", "Temporary note for now", "fact", explicit_consent=True)

        engine = MemoryConsolidationEngine(brain=brain)
        report = engine.consolidate(dry_run=True)

        assert report.ephemeral_memories_pruned == 1
        # In dry-run, brain still contains the unpruned memory
        assert len(brain.get_all_memories()) == 1


class TestMemoryConsolidationAction:
    def test_action_consolidate_and_last_report(self):
        res = handle_memory_consolidation(action="consolidate", dry_run=True)
        data = json.loads(res)
        assert data["status"] == "success"
        assert "report" in data

        res2 = handle_memory_consolidation(action="last_report")
        data2 = json.loads(res2)
        assert data2["status"] == "success"
