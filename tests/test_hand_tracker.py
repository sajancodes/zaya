from core.gesture.hand_tracker import HandTracker
import pytest
import time


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


def test_isolated_worker_stderr_is_drained(monkeypatch, tmp_path):
    import core.gesture.hand_tracker as ht
    from pathlib import Path

    model = tmp_path / 'hand.task'
    model.write_bytes(b'fixture')
    tracker = HandTracker(lambda hands: None)

    class FakeStdin:
        def write(self, text):
            return len(text)

        def flush(self):
            pass

        def close(self):
            pass

    class FakeStdout:
        def __init__(self):
            self.lines = ['{"state": "ACTIVE", "error": "", "hands": []}\n']

        def readline(self, limit=-1):
            if self.lines:
                line = self.lines.pop(0)
                tracker.stop_event.set()
                return line
            return ''

        def close(self):
            pass

    class FakeStderr:
        def __init__(self):
            self.lines = [f'vendor camera log line {i}\n' for i in range(5000)]
            self.consumed = False

        def __iter__(self):
            self.consumed = True
            return iter(self.lines)

        def close(self):
            pass

    fake_stderr = FakeStderr()

    class FakeChild:
        def __init__(self):
            self.stdin = FakeStdin()
            self.stdout = FakeStdout()
            self.stderr = fake_stderr
            self.returncode = None

        def poll(self):
            return self.returncode

        def wait(self, timeout=None):
            self.returncode = 0
            return 0

        def terminate(self):
            self.returncode = 0

        def kill(self):
            self.returncode = 0

    monkeypatch.setattr(ht.subprocess, 'Popen', lambda *args, **kwargs: FakeChild())
    tracker._run_isolated(Path('python.exe'), str(model), 0, 24, True, 0.65)

    assert tracker.state == 'OFF'
    deadline = time.monotonic() + 2
    while not fake_stderr.consumed and time.monotonic() < deadline:
        time.sleep(0.01)
    assert fake_stderr.consumed, 'worker stderr must be drained in the background'
