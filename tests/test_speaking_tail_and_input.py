import time
import threading
from unittest.mock import MagicMock
import pytest


def test_set_speaking_idempotent_does_not_extend_tail():
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
