import pytest
pytest.importorskip('cv2', reason='cv2 not installed')
from types import SimpleNamespace
from unittest.mock import patch


def test_explicit_camera_capture_reuses_hand_worker_without_opening_camera():
    from core.perception.screen_processor import _capture_camera
    tracker=SimpleNamespace(state='ACTIVE',device=0,capture_frame=lambda:b'jpeg fixture')
    with patch('core.gesture.controller.hands.tracker',tracker),patch('core.perception.screen_processor._load_config',return_value={}),patch('core.perception.screen_processor.cv2.VideoCapture') as camera:
        assert _capture_camera()==(b'jpeg fixture','image/jpeg')
        camera.assert_not_called()


def test_frame_cache_cleared_on_stopped_tracker_and_no_background_frame_requests():
    from core.gesture.hand_tracker import HandTracker
    tracker=HandTracker(lambda hands:None)
    assert tracker.capture_frame() is None and tracker.latest_frame is None
