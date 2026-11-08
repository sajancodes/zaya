"""Tests for Proactive Foresight Engine and Action.
Created and developed by Sajan Rai for Zaya.
"""
from __future__ import annotations

import tempfile
from pathlib import Path
import pytest

from core.execution_policy import TRUST_EXTERNAL_MESSAGE, with_trust
from core.proactive_foresight import ProactiveForesightEngine
from actions.proactive_foresight_action import proactive_foresight


@pytest.fixture
def foresight_engine():
    with tempfile.TemporaryDirectory() as td:
        engine = ProactiveForesightEngine(repo_root=Path(td))
        yield engine


def test_battery_runway_prediction(foresight_engine):
    engine = foresight_engine

    # Suppressed if charging or full battery
    assert engine.predict_battery_runway(current_pct=85.0, is_charging=False) is None
    assert engine.predict_battery_runway(current_pct=15.0, is_charging=True) is None

    # High priority warning at 20%
    item_high = engine.predict_battery_runway(current_pct=20.0, is_charging=False, discharge_rate_pct_per_min=0.5)
    assert item_high is not None
    assert item_high.priority == "high"
    assert "estimated runway of 40 minutes" in item_high.suggestion

    # Critical priority warning at 9%
    item_crit = engine.predict_battery_runway(current_pct=9.0, is_charging=False, discharge_rate_pct_per_min=1.0)
    assert item_crit is not None
    assert item_crit.priority == "critical"


def test_uncommitted_drift_detection(foresight_engine):
    engine = foresight_engine

    # Below drift threshold
    assert engine.check_uncommitted_drift(modified_count=2, untracked_count=2) is None

    # Medium drift
    item_med = engine.check_uncommitted_drift(modified_count=4, untracked_count=3, active_branch="dev", active_project="Zaya")
    assert item_med is not None
    assert item_med.priority == "medium"
    assert "7 uncommitted files" in item_med.suggestion

    # High drift
    item_high = engine.check_uncommitted_drift(modified_count=10, untracked_count=5, active_branch="main")
    assert item_high is not None
    assert item_high.priority == "high"


def test_flow_duration_rhythm(foresight_engine):
    engine = foresight_engine

    # Normal focus session (<90 min)
    assert engine.check_flow_duration(session_duration_minutes=45.0) is None

    # Extended session (>=90 min)
    item_flow = engine.check_flow_duration(session_duration_minutes=110.0)
    assert item_flow is not None
    assert "continuous focus for 110 minutes" in item_flow.suggestion


def test_executive_briefing(foresight_engine):
    engine = foresight_engine
    briefing = engine.generate_executive_briefing()
    assert "summary" in briefing
    assert "project" in briefing
    assert "branch" in briefing
    assert "foresight_items" in briefing


def test_proactive_foresight_action_handler():
    # Briefing action
    briefing_res = proactive_foresight({"action": "briefing"})
    assert briefing_res.status == "success"
    assert "summary" in briefing_res.data

    # Anticipate action
    ant_res = proactive_foresight({
        "action": "anticipate",
        "battery_pct": 12.0,
        "is_charging": False,
        "focus_minutes": 100.0,
    })
    assert ant_res.status == "success"
    assert len(ant_res.data["items"]) == 2

    # Unauthorized access check
    with with_trust(TRUST_EXTERNAL_MESSAGE):
        with pytest.raises(PermissionError):
            proactive_foresight({"action": "briefing"})
