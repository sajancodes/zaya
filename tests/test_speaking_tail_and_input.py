import time
import asyncio
import threading
from unittest.mock import MagicMock, AsyncMock
import pytest


def test_set_speaking_idempotent_does_not_extend_tail():
    pytest.importorskip('sounddevice', reason='sounddevice not installed')
    from main import ZayaLive

    # Mock minimal ZayaLive attributes needed for set_speaking
    inst = object.__new__(ZayaLive)
    inst._speaking_lock = threading.Lock()
    inst._is_speaking = False
    inst._loop = None
    inst._audio_ducker = None
    inst._out_latency = 0.20
    inst._tail_until = 0.0
    inst._notification_active = False
    inst._out_level = 0.0
    inst.ui = MagicMock()
    inst.ui.muted = False

    # Initially not speaking
    assert inst._tail_active() is False

    # Start speaking
    inst.set_speaking(True)
    assert inst._is_speaking is True
    assert inst._tail_until == 0.0
    assert inst._tail_active() is False

    # Repeated calls while speaking must be idempotent
    inst.set_speaking(True)
    assert inst._is_speaking is True
    assert inst._tail_until == 0.0

    # Stop speaking
    now = time.monotonic()
    inst.set_speaking(False)
    assert inst._is_speaking is False
    tail_1 = inst._tail_until
    assert tail_1 > now

    # Repeated calls while already stopped (idle loop) must NOT re-extend _tail_until
    time.sleep(0.05)
    inst.set_speaking(False)
    assert inst._tail_until == tail_1  # Unchanged!


def test_interrupt_clears_tail_until():
    pytest.importorskip('sounddevice', reason='sounddevice not installed')
    from main import ZayaLive

    inst = object.__new__(ZayaLive)
    inst._speaking_lock = threading.Lock()
    inst._is_speaking = True
    inst._loop = None
    inst._audio_ducker = None
    inst._out_latency = 0.20
    inst._tail_until = 0.0
    inst._notification_active = False
    inst._out_level = 0.0
    inst.audio_in_queue = None
    inst._local_pipeline = None
    inst._visemes = MagicMock()
    inst._play_cursor = 0.0
    inst._turn_done_event = None
    inst.ui = MagicMock()
    inst.ui.muted = False

    # Interrupt while speaking
    inst.interrupt()
    assert inst._is_speaking is False
    assert inst._tail_until == 0.0
    assert inst._tail_active() is False


def test_ui_send_does_not_double_log():
    from ui import MainWindow

    class DummyWindow:
        _send = MainWindow._send

    win = DummyWindow()
    win._input = MagicMock()
    win._input.text.return_value = "hello world"
    win._log = MagicMock()

    received = []
    win.on_text_command = lambda cmd: received.append(cmd)

    win._send()

    win._input.clear.assert_called_once()
    # append_log should NOT have been called directly because on_text_command handles logging
    win._log.append_log.assert_not_called()
    time.sleep(0.05)
    assert received == ["hello world"]


def test_quota_failure_ignores_client_inactivity():
    from core.gemini_keys import quota_failure, retry_delay

    inactivity_err = Exception("received 1008 (policy violation) Session closed due to client inactivity.")
    assert quota_failure(inactivity_err) is None
    assert retry_delay(inactivity_err) == 0.0

    real_quota_err = Exception("received 1008 (policy violation) User has exceeded their quota.")
    assert quota_failure(real_quota_err) is not None
    assert retry_delay(real_quota_err) == 3600.0


def test_run_tool_batch_catches_tool_exceptions():
    pytest.importorskip('sounddevice', reason='sounddevice not installed')
    from main import ZayaLive
    from google.genai import types

    inst = object.__new__(ZayaLive)
    inst._flush_pending_vision = AsyncMock()
    inst.session = MagicMock()
    inst.session.send_tool_response = AsyncMock()

    # Simulate tool raising an exception
    async def bad_tool(fc, **kwargs):
        raise RuntimeError("Something went wrong in the tool")

    inst._execute_tool = bad_tool

    fc = MagicMock()
    fc.id = "call_abc"
    fc.name = "failing_tool"

    calls = [fc]
    canceled = set()

    async def _runner():
        await inst._run_tool_batch(calls, canceled, "scope_1", "goal_1")

    # Must NOT raise exception
    asyncio.run(_runner())

    # Should have sent a failed response rather than crashing
    inst.session.send_tool_response.assert_called_once()
    sent_responses = inst.session.send_tool_response.call_args.kwargs["function_responses"]
    assert len(sent_responses) == 1
    assert sent_responses[0].name == "failing_tool"
    assert sent_responses[0].response["status"] == "failed"
    assert "Something went wrong" in sent_responses[0].response["error"]
