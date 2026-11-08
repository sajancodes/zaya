"""Proactive Contextual Foresight & Cognitive Routine Anticipator for Zaya.
Created and developed by Sajan Rai.

Analyzes workspace rhythm, resource depletion trajectories, uncommitted code drift,
and service closures to proactively surface intelligent developer suggestions
and Jarvis-grade executive briefings.
"""
from __future__ import annotations

import logging
import subprocess
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, List, Optional

from core.project_awareness import get_project_awareness
from core.runtime_paths import mutable_path

logger = logging.getLogger(__name__)


@dataclass
class ForesightItem:
    id: str
    category: str  # developer_flow, battery_trajectory, uncommitted_drift, service_crash, executive_briefing
    priority: str  # low, medium, high, critical
    title: str
    suggestion: str
    action_tool: Optional[str] = None
    action_params: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)


class ProactiveForesightEngine:
    """Anticipates developer needs, environmental shifts, and system risks."""

    def __init__(self, repo_root: Optional[Path] = None) -> None:
        self.repo_root = repo_root or Path(__file__).resolve().parent.parent

    def predict_battery_runway(
        self,
        current_pct: float,
        is_charging: bool,
        discharge_rate_pct_per_min: float = 0.8,
    ) -> Optional[ForesightItem]:
        """Project remaining battery runtime and suggest power saving before critical drop."""
        if is_charging or current_pct > 25.0:
            return None

        if discharge_rate_pct_per_min <= 0.05:
            discharge_rate_pct_per_min = 0.5  # reasonable floor

        remaining_minutes = max(1.0, current_pct / discharge_rate_pct_per_min)
        priority = "critical" if remaining_minutes < 15.0 or current_pct <= 10.0 else "high"

        return ForesightItem(
            id=f"battery_runway_{int(time.time() // 300)}",
            category="battery_trajectory",
            priority=priority,
            title="Battery Runway Warning",
            suggestion=(
                f"Battery is at {current_pct:.0f}% with an estimated runway of {remaining_minutes:.0f} minutes "
                f"at current discharge rate ({discharge_rate_pct_per_min:.1f}%/min). "
                f"Connect AC adapter or engage Power Saver."
            ),
            action_tool="computer_settings",
            action_params={"setting": "power_mode", "value": "efficiency"},
        )

    def check_uncommitted_drift(
        self,
        modified_count: int,
        untracked_count: int,
        active_branch: str = "main",
        active_project: str = "",
    ) -> Optional[ForesightItem]:
        """Detect accumulated uncommitted changes and prompt for checkpoint commits."""
        total_drift = modified_count + untracked_count
        if total_drift < 6:
            return None

        priority = "medium" if total_drift < 12 else "high"
        proj_str = f" in '{active_project}'" if active_project else ""

        return ForesightItem(
            id=f"uncommitted_drift_{int(time.time() // 600)}",
            category="uncommitted_drift",
            priority=priority,
            title="Uncommitted Changes Accumulation",
            suggestion=(
                f"You have {total_drift} uncommitted files ({modified_count} modified, {untracked_count} untracked) "
                f"on branch '{active_branch}'{proj_str}. Recommend staging a coherent checkpoint commit."
            ),
            action_tool="repo_sentinel",
            action_params={"action": "status"},
        )

    def check_flow_duration(
        self,
        session_duration_minutes: float,
        break_threshold_minutes: float = 90.0,
    ) -> Optional[ForesightItem]:
        """Detect extended deep-focus sessions and suggest micro-breaks."""
        if session_duration_minutes < break_threshold_minutes:
            return None

        return ForesightItem(
            id=f"flow_duration_{int(time.time() // 1800)}",
            category="developer_flow",
            priority="low",
            title="Deep Focus Rhythm Notice",
            suggestion=(
                f"You have been in continuous focus for {session_duration_minutes:.0f} minutes. "
                "Consider a 2-minute pause, eye rest, or hydration break to maintain peak cognitive agility."
            ),
            action_tool="reminder",
            action_params={"action": "create", "message": "Quick stretch and hydration break"},
        )

    def generate_executive_briefing(self) -> dict[str, Any]:
        """Generate a complete Jarvis-grade situational briefing."""
        awareness = get_project_awareness()
        snapshot = awareness.snapshot()
        active_proj = snapshot.get("active_project", "")
        last_known = snapshot.get("last_known_project", "")
        active_task = snapshot.get("active_task")

        # Git status summary of workspace
        modified_count = 0
        untracked_count = 0
        current_branch = "unknown"
        try:
            res = subprocess.run(
                ["git", "status", "--porcelain", "-b"],
                cwd=str(self.repo_root),
                capture_output=True,
                text=True,
                timeout=3.0,
            )
            if res.returncode == 0:
                lines = res.stdout.strip().splitlines()
                if lines and lines[0].startswith("##"):
                    current_branch = lines[0].replace("##", "").split("...")[0].strip()
                for line in lines[1:]:
                    if line.startswith("??"):
                        untracked_count += 1
                    else:
                        modified_count += 1
        except Exception:
            pass

        # Synthesize foresight items
        foresights: List[ForesightItem] = []
        drift_item = self.check_uncommitted_drift(
            modified_count=modified_count,
            untracked_count=untracked_count,
            active_branch=current_branch,
            active_project=active_proj or last_known,
        )
        if drift_item:
            foresights.append(drift_item)

        # Briefing summary text
        proj_name = active_proj or last_known or "Zaya"
        greeting = "Good evening" if time.localtime().tm_hour >= 18 else "Good day"
        briefing_lines = [
            f"{greeting}, Sajan. Executive briefing for project '{proj_name}':",
            f"- Workspace branch: '{current_branch}', with {modified_count} modified and {untracked_count} untracked files.",
        ]
        if active_task:
            briefing_lines.append(f"- Active background goal: '{active_task.get('goal')}' [{active_task.get('state')}].")
        else:
            briefing_lines.append("- All background execution pipelines are idle and nominal.")

        if foresights:
            briefing_lines.append(f"- Cognitive foresight: {foresights[0].suggestion}")

        full_briefing = "\n".join(briefing_lines)

        return {
            "summary": full_briefing,
            "project": proj_name,
            "branch": current_branch,
            "modified_files": modified_count,
            "untracked_files": untracked_count,
            "active_task": active_task,
            "foresight_items": [asdict(f) for f in foresights],
        }


_foresight: Optional[ProactiveForesightEngine] = None


def get_foresight_engine() -> ProactiveForesightEngine:
    global _foresight
    if _foresight is None:
        _foresight = ProactiveForesightEngine()
    return _foresight
