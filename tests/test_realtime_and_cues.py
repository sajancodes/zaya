import asyncio
from unittest.mock import MagicMock, AsyncMock
import pytest
from actions.conversational_cue import register_cue
from core.cue_manager import cue_manager
from core.fast_reflex import fast_reflex
from core.voice_turns import VoiceTurns


def test_conversational_cue_action_handler():
    # Test action handler directly
    res = register_cue({
        "trigger_type": "any_input",
        "tool_name": "video_player",
        "parameters": {"action": "play", "source": "Parvati", "target": "display"},
        "ack_phrase": "Standing by, sir.",
    })
    assert "status=armed" in res
    assert "video_player" in res
    assert cue_manager.has_armed_cue() is True

    # User says anything -> matches and triggers
    matched, params = cue_manager.evaluate(text="hello Zaya")
    assert matched is not None
    assert params["source"] == "Parvati"
    assert cue_manager.has_armed_cue() is False


def test_concurrent_tool_batch_simulation():
    # Simulate parallel tool batch execution with asyncio.gather
    executed = []

    async def dummy_execute(fc):
        executed.append(f"start_{fc.name}")
        await asyncio.sleep(0.05)
        executed.append(f"end_{fc.name}")
        return MagicMock(id=fc.id, name=fc.name)

    async def run_batch():
        fc1 = MagicMock(id="c1", name="avatar_expression")
        fc2 = MagicMock(id="c2", name="video_player")
        calls = [fc1, fc2]
        canceled = set()

        async def _exec_single(fc):
            if fc.id in canceled:
                return None
            return await dummy_execute(fc)

        results = await asyncio.gather(*(_exec_single(fc) for fc in calls))
        return results

    results = asyncio.run(run_batch())
    assert len(results) == 2
    # Both start before either finishes because of asyncio.gather
    assert executed[0].startswith("start_")
    assert executed[1].startswith("start_")


def test_text_command_routing_logic():
    # Dummy UI and main window structure for testing routing logic
    logs = []

    class DummyUI:
        muted = False

        def write_log(self, msg):
            logs.append(msg)

    ui = DummyUI()

    # 1. Test fast reflex routing
    reflex_res = fast_reflex.handle("what time is it")
    assert reflex_res is not None
    assert reflex_res.matched is True
    ui.write_log(f"Zaya: {reflex_res.ack}")
    assert any("sir" in log for log in logs)

    # 2. Test cue intent detection routing
    setup = cue_manager.detect_cue_intent("when i say anything just play parvati on the display")
    assert setup is not None
    cue_manager.arm_cue(
        trigger_type=setup["trigger_type"],
        tool_name=setup["tool_name"],
        parameters=setup["parameters"],
        ack_phrase=setup["ack_phrase"],
    )
    assert cue_manager.has_armed_cue() is True

    # 3. Test cue triggering on subsequent input
    matched_cue, params = cue_manager.evaluate(text="Aaja Se Paro Jab Jeet Pe Aa Gayi Parvati")
    assert matched_cue is not None
    assert params["source"] == "parvati"
    assert cue_manager.has_armed_cue() is False
