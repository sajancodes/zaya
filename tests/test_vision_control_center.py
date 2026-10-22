import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import pytest
from unittest.mock import MagicMock, patch
from core.gesture.gesture_state import InteractionMode
from core.gesture.controller import HandController
from core.gesture.hand_tracker import HandTracker
from core.gesture.hand_model import Point, HandState
from core.execution_policy import with_trust, TRUST_LOCAL_OWNER


def test_normal_startup_camera_off():
    controller = HandController()
    assert controller.tracker.state == 'OFF'
    assert controller.mode == InteractionMode.DISABLED
    assert controller.tracker.worker is None


def test_tracker_wait_active_timeout_prevents_indefinite_starting(tmp_path):
    model = tmp_path / 'hand.task'
    model.write_bytes(b'test_model_bytes')
    tracker = HandTracker(lambda hands: None)

    with patch.object(tracker, '_run', lambda *args, **kwargs: None):
        tracker.start(str(model), device=0)
        assert tracker.state == 'STARTING'
        # Calling wait_active with tiny timeout when worker never signals ACTIVE
        result = tracker.wait_active(timeout=0.1)
        assert result is False
        assert tracker.state == 'ERROR'
        assert 'timed out' in tracker.error
    tracker.stop()


def test_mode_switching_keeps_camera_alive():
    controller = HandController()
    controller.tracker.state = 'ACTIVE'
    controller.last_start = ('dummy_model', 'NAVIGATION', 0, 24, True, 0.65, 1.0)
    controller.mode = InteractionMode.NAVIGATION

    # Switching to KEYBOARD should NOT stop or start the tracker
    with patch.object(controller.tracker, 'stop') as mock_stop, \
         patch.object(controller.tracker, 'start') as mock_start:
        controller.set_mode('KEYBOARD')
        assert controller.mode == InteractionMode.KEYBOARD
        mock_stop.assert_not_called()
        mock_start.assert_not_called()

        # Calling controller.start with same device should reuse active camera
        controller.start('dummy_model', 'SPATIAL', device=0)
        assert controller.mode == InteractionMode.SPATIAL
        mock_stop.assert_not_called()
        mock_start.assert_not_called()


def test_leaving_keyboard_revokes_typing_and_clears_modifiers():
    controller = HandController()
    controller.mode = InteractionMode.KEYBOARD
    controller.modifiers.add('shift')
    controller.keyboard.state = 'armed'

    controller.set_mode('NAVIGATION')
    assert controller.mode == InteractionMode.NAVIGATION
    assert len(controller.modifiers) == 0
    assert controller.keyboard.state == 'idle'


def test_hand_controls_action_routing(monkeypatch, tmp_path):
    from actions.hand_controls import hand_controls
    monkeypatch.setattr('core.gesture.settings.PATH', tmp_path / 'hand_controls.json')
    controller = HandController()
    controller.tracker.state = 'ACTIVE'
    controller.last_start = ('dummy_model', 'NAVIGATION', 0, 24, True, 0.65, 1.0)
    controller.mode = InteractionMode.NAVIGATION

    monkeypatch.setattr('core.gesture.controller.hands', controller)
    monkeypatch.setattr('core.ghost_overlay.passive_overlay_available', lambda: True)
    monkeypatch.setattr('core.ghost_overlay.show_vision_control_center', lambda mode=None: True)

    with with_trust(TRUST_LOCAL_OWNER):
        # 1. Switch to virtual keyboard
        res = hand_controls({'action': 'start', 'mode': 'KEYBOARD'})
        assert res.status == 'success'
        assert controller.mode == InteractionMode.KEYBOARD
        assert controller.tracker.state == 'ACTIVE'

        # 2. Hide virtual keyboard via set_mode
        res = hand_controls({'action': 'set_mode', 'mode': 'NAVIGATION'})
        assert res.status == 'success'
        assert controller.mode == InteractionMode.NAVIGATION
        assert controller.tracker.state == 'ACTIVE'

        # 3. Stop keyboard only
        controller.set_mode('KEYBOARD')
        res = hand_controls({'action': 'stop', 'target': 'keyboard'})
        assert res.status == 'success'
        assert controller.mode == InteractionMode.NAVIGATION
        assert controller.tracker.state == 'ACTIVE'

        # 4. Stop camera completely
        res = hand_controls({'action': 'stop'})
        assert res.status == 'success'
        assert controller.mode == InteractionMode.DISABLED
        assert controller.tracker.state == 'OFF'


def test_vision_control_center_ui():
    from PyQt6.QtWidgets import QApplication
    from core.gesture.settings_panel import HandSettingsPanel
    app = QApplication.instance() or QApplication([])

    panel = HandSettingsPanel()
    panel.show()
    app.processEvents()

    # Window title check
    assert panel.windowTitle() == 'ZAYA · VIRTUAL KEYBOARD'

    # Mode buttons exist
    assert len(panel.mode_buttons) == 4
    assert 'NAVIGATION' in panel.mode_buttons
    assert 'KEYBOARD' in panel.mode_buttons

    # Keyboard canvas hidden by default in NAVIGATION
    assert not panel.keyboard_canvas.isVisible()

    # Switch to KEYBOARD mode -> keyboard canvas becomes visible
    panel.switch_mode('KEYBOARD')
    app.processEvents()
    assert panel.keyboard_canvas.isVisible()

    # Switch back to NAVIGATION -> keyboard canvas hidden
    panel.switch_mode('NAVIGATION')
    app.processEvents()
    assert not panel.keyboard_canvas.isVisible()

    # Preview canvas has landmarks toggle
    assert panel.cb_landmarks.isChecked()
    panel.cb_landmarks.setChecked(False)
    assert not panel.preview.show_landmarks

    # Test rendering landmarks with mock hand
    dummy_points = tuple(Point(float(i)/21.0, float(i)/21.0, 0.0) for i in range(21))
    hand = HandState(
        hand_id='Right', handedness='Right', landmarks=dummy_points, world_landmarks=dummy_points,
        palm_center=Point(0.5, 0.5, 0.0), palm_normal=Point(0, 0, 1),
        finger_states=(True, True, False, False, False), velocity=Point(0, 0, 0),
        confidence=0.92, timestamp=1.0, relative_depth=0.1, pinch_distance=0.5
    )
    panel.preview.set_telemetry('ACTIVE', (hand,), 'INDEX_ONLY', 0.92)
    panel.preview.show_landmarks = True
    panel.preview.repaint()
    app.processEvents()

    panel.close()
    app.processEvents()


def test_scenario_a_to_e_journey(monkeypatch):
    """Verifies end-to-end flow across Scenarios A through E."""
    from actions.hand_controls import hand_controls
    controller = HandController()
    opened_windows = []

    monkeypatch.setattr('core.gesture.controller.hands', controller)
    monkeypatch.setattr('core.ghost_overlay.passive_overlay_available', lambda: True)
    monkeypatch.setattr('core.ghost_overlay.show_vision_control_center', lambda mode=None: opened_windows.append(mode) or True)

    with patch.object(controller.tracker, 'start', lambda *a, **k: setattr(controller.tracker, 'state', 'ACTIVE')), \
         with_trust(TRUST_LOCAL_OWNER):

        # Scenario A: "start webcam"
        res_a = hand_controls({'action': 'start', 'mode': 'NAVIGATION'})
        assert res_a.status == 'success'
        assert controller.mode == InteractionMode.NAVIGATION
        assert controller.tracker.state == 'ACTIVE'
        assert 'NAVIGATION' in opened_windows

        # Scenario B: "open virtual keyboard" (camera reused!)
        with patch.object(controller.tracker, 'stop') as mock_stop_b, \
             patch.object(controller.tracker, 'start') as mock_start_b:
            res_b = hand_controls({'action': 'start', 'mode': 'KEYBOARD'})
            assert res_b.status == 'success'
            assert controller.mode == InteractionMode.KEYBOARD
            assert controller.tracker.state == 'ACTIVE'
            mock_stop_b.assert_not_called()
            mock_start_b.assert_not_called()

        # Scenario C: "hide virtual keyboard"
        controller.modifiers.add('ctrl')
        res_c = hand_controls({'action': 'set_mode', 'mode': 'NAVIGATION'})
        assert res_c.status == 'success'
        assert controller.mode == InteractionMode.NAVIGATION
        assert len(controller.modifiers) == 0
        assert controller.tracker.state == 'ACTIVE'

        # Scenario D: "start spatial controls" (camera reused!)
        res_d = hand_controls({'action': 'set_mode', 'mode': 'SPATIAL'})
        assert res_d.status == 'success'
        assert controller.mode == InteractionMode.SPATIAL
        assert controller.tracker.state == 'ACTIVE'

        # Scenario E: "stop webcam"
        res_e = hand_controls({'action': 'stop'})
        assert res_e.status == 'success'
        assert controller.mode == InteractionMode.DISABLED
        assert controller.tracker.state == 'OFF'


def test_preview_and_keyboard_canvas_paint():
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtGui import QImage, QPixmap
    from PyQt6.QtCore import QByteArray, QBuffer, QIODevice
    from core.gesture.settings_panel import PreviewCanvas, VirtualKeyboardCanvas
    app = QApplication.instance() or QApplication([])

    # 1. PreviewCanvas rendering with and without frame
    canvas = PreviewCanvas()
    canvas.set_telemetry('OFF', (), 'NONE', 0.0)
    canvas.repaint()

    # Create dummy JPEG bytes
    img = QImage(320, 240, QImage.Format.Format_RGB32)
    img.fill(0xff3344)
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    img.save(buf, 'JPG')
    jpeg_bytes = bytes(ba)

    canvas.set_telemetry('ACTIVE', (), 'NONE', 0.0)
    canvas.update_frame(jpeg_bytes)
    assert canvas.pixmap is not None
    canvas.repaint()

    # 2. VirtualKeyboardCanvas rendering states (armed, locked, latched modifier)
    kb = VirtualKeyboardCanvas()
    kb.set_packet({'state': 'armed', 'key': 'H', 'modifiers': ['shift']})
    kb.repaint()

    kb.set_packet({'state': 'locked', 'key': 'H', 'sent': 'H', 'modifiers': []})
    kb.repaint()


def test_preview_thread_restarts_after_window_reopen():
    from PyQt6.QtWidgets import QApplication
    from core.gesture.settings_panel import HandSettingsPanel
    app = QApplication.instance() or QApplication([])

    panel = HandSettingsPanel()
    panel.show()
    app.processEvents()
    first = panel.preview_thread
    assert first is not None and first.isRunning()

    panel.close()
    app.processEvents()
    assert panel.preview_thread is None

    panel.show()
    app.processEvents()
    second = panel.preview_thread
    assert second is not None and second.isRunning()
    assert second is not first

    panel.close()
    app.processEvents()


def test_active_worker_capture_reaches_preview_signal(monkeypatch):
    import time
    from types import SimpleNamespace
    from PyQt6.QtWidgets import QApplication
    from core.gesture.settings_panel import PreviewThread
    app = QApplication.instance() or QApplication([])

    tracker = SimpleNamespace(state='ACTIVE', capture_frame=lambda timeout=2: b'fake-jpeg-frame')
    monkeypatch.setattr('core.gesture.controller.hands.tracker', tracker)

    thread = PreviewThread()
    received = []
    thread.frame_ready.connect(received.append)
    thread.start()
    try:
        deadline = time.monotonic() + 2
        while not received and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(0.01)
    finally:
        thread.stop()
    assert received and received[0] == b'fake-jpeg-frame'


def test_missing_model_reports_explicit_message(tmp_path):
    tracker = HandTracker(lambda hands: None)
    with pytest.raises(ValueError, match='Hand Landmarker model not found'):
        tracker.start(str(tmp_path / 'missing.task'))
    assert tracker.state == 'OFF'


def test_closing_vision_window_revokes_keyboard_injection(monkeypatch):
    from PyQt6.QtWidgets import QApplication
    from core.gesture.settings_panel import HandSettingsPanel
    from core.gesture.controller import hands

    app = QApplication.instance() or QApplication([])
    calls = []
    monkeypatch.setattr(hands.tracker, 'state', 'ACTIVE')
    monkeypatch.setattr(hands, 'set_mode', lambda mode, sensitivity=None: calls.append(mode))

    panel = HandSettingsPanel()
    panel.show()
    app.processEvents()
    panel.close()
    app.processEvents()

    assert calls == ['NAVIGATION']
    assert panel.preview_thread is None

