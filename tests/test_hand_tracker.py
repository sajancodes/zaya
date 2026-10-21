from core.gesture.hand_tracker import HandTracker
import pytest


def test_missing_model_does_not_start_camera():
    tracker=HandTracker(lambda hands:None)
    with pytest.raises(ValueError):
        tracker.start('missing-zaya-model.task')
    assert tracker.worker is None and tracker.state=='OFF'


def test_missing_mediapipe_isolated(tmp_path,monkeypatch):
    monkeypatch.setenv('ZAYA_HAND_CHILD','1')
    import builtins
    original=builtins.__import__
    def optional(name,*args,**kwargs):
        if name=='mediapipe':
            raise ImportError('optional package missing')
        return original(name,*args,**kwargs)
    monkeypatch.setattr(builtins,'__import__',optional)
    model=tmp_path/'hand.task';model.write_bytes(b'fixture')
    received=[];tracker=HandTracker(received.append);tracker.start(str(model));tracker.worker.join(3)
    assert tracker.state=='ERROR' and 'ImportError' in tracker.error
    assert received==[()]
