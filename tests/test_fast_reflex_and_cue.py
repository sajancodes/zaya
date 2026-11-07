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
