"""Autonomous Memory Consolidation & Dream Cycle Engine.
Created and developed by Sajan Rai for Zaya.

Executes autonomous background consolidation of episodic facts, task logs, and user preferences:
prunes transient noise, resolves historical contradictions, and synthesizes durable macro-insights.
"""
from __future__ import annotations

import logging
import re
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.personal_memory import PersonalMemoryBrain, MemoryItem, _current_time_iso
from core.runtime_paths import mutable_path

logger = logging.getLogger(__name__)


@dataclass
class ConsolidationReport:
    timestamp: float
    total_memories_before: int
    total_memories_after: int
    contradictions_resolved: int
    ephemeral_memories_pruned: int
    macro_insights_formed: int
    details: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "total_memories_before": self.total_memories_before,
            "total_memories_after": self.total_memories_after,
            "contradictions_resolved": self.contradictions_resolved,
            "ephemeral_memories_pruned": self.ephemeral_memories_pruned,
            "macro_insights_formed": self.macro_insights_formed,
            "details": self.details,
        }


class MemoryConsolidationEngine:
    """Consolidates personal memory facts, prunes noise, and resolves contradictory preferences."""

    def __init__(self, brain: Optional[PersonalMemoryBrain] = None) -> None:
        self.brain = brain or PersonalMemoryBrain()
        self._lock = threading.RLock()
        self._history: List[ConsolidationReport] = []

    def consolidate(self, dry_run: bool = False) -> ConsolidationReport:
        """Execute a memory consolidation dream pass."""
        with self._lock:
            memories = self.brain.get_all_memories()
            before_count = len(memories)

            contradictions_count = 0
            pruned_count = 0
            macro_count = 0
            details: List[str] = []

            # 1. Ephemeral Fact Pruning (remove transient facts or expired context)
            retained_memories: Dict[str, MemoryItem] = {}

            for item in memories:
                val = item.value.lower()
                key = item.key.lower()

                # Flag ephemeral patterns
                is_ephemeral = any(
                    w in val or w in key
                    for w in ("for now", "temporarily", "temp code", "verification code", "transient", "right now it is")
                ) or item.retention_policy == "session"

                if is_ephemeral:
                    pruned_count += 1
                    details.append(f"Pruned ephemeral memory '{item.key}': {item.value[:50]}")
                    continue

                retained_memories[item.id] = item

            # 2. Contradiction Resolution
            # Group by semantic topic or attribute
            topic_groups: Dict[str, List[MemoryItem]] = {}
            for item in retained_memories.values():
                val = item.value.lower()
                key = item.key.lower()
                topic = None
                if any(w in val or w in key for w in ("theme", "dark mode", "light mode")):
                    topic = "theme"
                elif any(w in val or w in key for w in ("browser", "brave", "chrome", "firefox", "edge")):
                    topic = "browser"
                elif any(w in val or w in key for w in ("ide", "editor", "vscode", "pycharm")):
                    topic = "editor"

                if topic:
                    topic_groups.setdefault(topic, []).append(item)

            for topic, items in topic_groups.items():
                if len(items) > 1:
                    # Sort by updated_at descending (most recent wins)
                    items.sort(key=lambda x: x.updated_at or x.created_at, reverse=True)
                    winner = items[0]

                    # Prune the older contradictory facts
                    for loser in items[1:]:
                        if loser.id in retained_memories:
                            del retained_memories[loser.id]
                            contradictions_count += 1
                            details.append(
                                f"Resolved contradiction on topic '{topic}': kept newer '{winner.key}', pruned older '{loser.key}'."
                            )

            # 3. Macro Insight Synthesis
            all_content = " ".join(f"{m.key} {m.value}".lower() for m in retained_memories.values())
            has_dev_context = any(w in all_content for w in ("python", "code", "git", "repo", "terminal", "powershell"))

            if has_dev_context:
                existing_macro = any(m.key == "profile:primary_domain" for m in retained_memories.values())
                if not existing_macro:
                    new_item = MemoryItem(
                        id=str(uuid.uuid4()),
                        key="profile:primary_domain",
                        value="Owner actively develops software and engineering projects locally.",
                        category="profile",
                        importance=0.9,
                        confidence=0.95,
                        source="memory_consolidation_dream_cycle",
                        created_at=_current_time_iso(),
                        updated_at=_current_time_iso(),
                    )
                    retained_memories[new_item.id] = new_item
                    macro_count += 1
                    details.append("Synthesized macro insight: Owner is an active software developer.")

            after_count = len(retained_memories)

            report = ConsolidationReport(
                timestamp=time.time(),
                total_memories_before=before_count,
                total_memories_after=after_count,
                contradictions_resolved=contradictions_count,
                ephemeral_memories_pruned=pruned_count,
                macro_insights_formed=macro_count,
                details=details,
            )

            if not dry_run:
                self.brain.replace_all_memories(list(retained_memories.values()))
                self._history.append(report)
                logger.info(
                    "[MemoryConsolidation] Pass completed: before=%d, after=%d, contradictions=%d, pruned=%d",
                    before_count,
                    after_count,
                    contradictions_count,
                    pruned_count,
                )

            return report

    def get_last_report(self) -> Optional[ConsolidationReport]:
        with self._lock:
            return self._history[-1] if self._history else None


# ── Global Singleton ─────────────────────────────────────────────────────────

_consolidation: Optional[MemoryConsolidationEngine] = None


def get_memory_consolidation_engine() -> MemoryConsolidationEngine:
    global _consolidation
    if _consolidation is None:
        _consolidation = MemoryConsolidationEngine()
    return _consolidation
