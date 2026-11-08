import time
import pytest
from core.cue_manager import CueManager
from core.fast_reflex import FastReflexRouter


def test_fast_reflex_matching():
    router = FastReflexRouter()

    # Exact match
    intent, score = router.match("pause")
    assert intent == "MEDIA_PAUSE"
    assert score == 1.0

    # Prefix removal
    intent, score = router.match("zaya skip song")
    assert intent == "MEDIA_NEXT"
    assert score >= 0.88

    intent, score = router.match("what time is it")
    assert intent == "TIME_QUERY"
    assert score == 1.0

    # Non-reflex query passes through
    intent, score = router.match("can you explain quantum computing in detail?")
    assert intent is None


def test_fast_reflex_execution():
    router = FastReflexRouter()
    res = router.handle("what time is it")
    assert res is not None
    assert res.matched is True
    assert "sir" in res.ack

    res_date = router.handle("today's date")
    assert res_date is not None
    assert res_date.matched is True
    assert "Today is" in res_date.ack


def test_fast_reflex_speed():
    router = FastReflexRouter()
    start = time.perf_counter()
    for _ in range(100):
        router.match("pause music")
    duration = time.perf_counter() - start
    # 100 evaluations should easily take < 0.1s (< 1ms each)
    assert duration < 0.1, f"Expected < 100ms for 100 evals, took {duration*1000:.2f}ms"


def test_fast_reflex_system_and_apps():
    from unittest.mock import patch
    router = FastReflexRouter()

    # Match system controls
    intent, score = router.match("switch to performance mode")
    assert intent == "POWER_PERFORMANCE"
    assert score >= 0.88

    intent, score = router.match("lock my pc")
    assert intent == "SYSTEM_LOCK"
    assert score >= 0.88

    intent, score = router.match("show desktop")
    assert intent == "SHOW_DESKTOP"
    assert score >= 0.88

    intent, score = router.match("open calculator")
    assert intent == "OPEN_CALCULATOR"
    assert score >= 0.88

    intent, score = router.match("launch notepad")
    assert intent == "OPEN_NOTEPAD"
    assert score >= 0.88

    # Test execution with mocked actions
    with patch("actions.computer_settings.computer_settings", return_value="Performance mode active.") as mock_cs:
        res = router.handle("performance mode")
        assert res is not None
        assert res.matched is True
        assert res.tool_name == "computer_settings"
        assert res.arguments == {"action": "performance_mode"}
        assert "Performance mode" in res.ack

    with patch("actions.open_app.open_app", return_value="Opened calc.") as mock_oa:
        res = router.handle("open calculator")
        assert res is not None
        assert res.matched is True
        assert res.tool_name == "open_app"
        assert res.arguments == {"app": "calculator"}
        assert "calculator" in res.ack.lower()


def test_cue_manager_intent_detection():
    cm = CueManager()

    # Scenario 1: humming setup
    setup1 = "ill just hum a song randomly called jab jid pe aagaayi paarvati you just play parvati song on the display when i start humming"
    res1 = cm.detect_cue_intent(setup1)
    assert res1 is not None
    assert res1["trigger_type"] == "any_input"
    assert res1["parameters"]["action"] == "play"
    assert "parvati" in res1["parameters"]["source"].lower() or "jab jid" in res1["parameters"]["source"].lower()
    assert res1["parameters"]["target"] == "display"

    # Scenario 2: say anything setup
    setup2 = "ok when i say anything just play it now ok"
    # Provide previous source to ensure it reuses it
    cm._last_source = "Parvati"
    res2 = cm.detect_cue_intent(setup2)
    assert res2 is not None
    assert res2["trigger_type"] == "any_input"
    assert res2["parameters"]["source"] == "Parvati"

    # Scenario 3: repeated instruction from user
    setup3 = "No, no, no. I'll just say anything, anything I will say and you just play song Parvati on my display. Got it?"
    res3 = cm.detect_cue_intent(setup3)
    assert res3 is not None
    assert res3["trigger_type"] == "any_input"
    assert "parvati" in res3["parameters"]["source"].lower()


def test_cue_arm_and_fire_flow():
    cm = CueManager()

    cue = cm.arm_cue(
        trigger_type="any_input",
        tool_name="video_player",
        parameters={"action": "play", "source": "Parvati", "target": "display"},
        single_shot=True,
    )
    assert cm.has_armed_cue() is True

    # User speaks arbitrary words: "Aaja Se Paro Jab Jeet Pe Aa Gayi Parvati"
    matched_cue, params = cm.evaluate(text="Aaja Se Paro Jab Jeet Pe Aa Gayi Parvati")
    assert matched_cue is not None
    assert matched_cue.id == cue.id
    assert params["source"] == "Parvati"

    # Single-shot cue is disarmed
    assert cm.has_armed_cue() is False

    # Second utterance does not fire it again
    matched_cue2, _ = cm.evaluate(text="Another line")
    assert matched_cue2 is None


def test_cue_explicit_cancel():
    cm = CueManager()
    cm.arm_cue(
        trigger_type="any_input",
        tool_name="video_player",
        parameters={"action": "play", "source": "Parvati"},
    )
    assert cm.has_armed_cue() is True

    # User says cancel
    matched_cue, params = cm.evaluate(text="cancel")
    assert matched_cue is None
    assert cm.has_armed_cue() is False


def test_fast_reflex_battery_and_health():
    from unittest.mock import patch, MagicMock
    router = FastReflexRouter()

    intent, score = router.match("what is my battery")
    assert intent == "BATTERY_QUERY"
    assert score >= 0.88

    intent, score = router.match("check cpu usage")
    assert intent == "SYSTEM_HEALTH_QUERY"
    assert score >= 0.88

    # Test execution
    mock_batt = MagicMock(percent=82, power_plugged=True, secsleft=-2)
    with patch("psutil.sensors_battery", return_value=mock_batt):
        res = router.handle("battery status")
        assert res is not None
        assert res.matched is True
        assert "82%" in res.ack
        assert "charging" in res.ack

    mock_status = {
        "cpu_percent": 24.5,
        "ram_percent": 48.0,
        "ram_used_gb": 7.5,
        "ram_total_gb": 16.0,
        "uptime": "2h 10m",
    }
    with patch("services.system_monitor.get_system_status", return_value=mock_status):
        res = router.handle("system health")
        assert res is not None
        assert res.matched is True
        assert "24.5%" in res.ack
        assert "48.0%" in res.ack


def test_fast_reflex_negation_and_question_rejection():
    router = FastReflexRouter()

    # Negated commands must NEVER trigger action intents
    negated_cases = [
        "Don't empty the recycle bin.",
        "Never delete those files.",
        "Do not mute my microphone.",
        "Don't disable Night Light.",
        "I don't want clipboard history enabled.",
        "Not empty recycle bin.",
        "I don't want to empty recycle bin.",
        "Never empty recycle bin.",
    ]
    for prompt in negated_cases:
        intent, _ = router.match(prompt)
        assert intent is None, f"Prompt '{prompt}' should not trigger an intent, got {intent}"

    # Question and hypothetical statements must route to reasoning engine, not fast actions
    question_cases = [
        "What happens if I empty the recycle bin?",
        "Explain how to disable the firewall.",
        "What would happen if I delete those files?",
        "Explain how to empty recycle bin",
    ]
    for prompt in question_cases:
        intent, _ = router.match(prompt)
        assert intent is None, f"Question '{prompt}' should not trigger an intent, got {intent}"

    # Positive command must still execute
    intent, score = router.match("Empty the recycle bin.")
    assert intent == "RECYCLE_BIN_EMPTY"
    assert score >= 0.88


