import threading
import time
from .perception_state import PerceptionState


class ScreenPerception:
    def __init__(self):
        self.state = PerceptionState()
        self.lock = threading.RLock()
        self.stop_event = threading.Event()
        self.worker = None
        self.error = ''

    def snapshot(self):
        with self.lock:
            return self.state

    def start(self):
        with self.lock:
            if self.worker and self.worker.is_alive():
                return
            self.stop_event.clear()
            self.error = ''
            self.worker = threading.Thread(target=self._run, name='ZayaPerception', daemon=True)
            self.worker.start()

    def stop(self):
        self.stop_event.set()
        if self.worker:
            self.worker.join(3)
        with self.lock:
            self.state = PerceptionState(revision=self.state.revision, activity='off')

    def _run(self):
        try:
            # Reuse the existing screen module's optional mss dependency.
            from actions.screen_processor import mss
            import numpy as np
            from .frame_diff import FrameDiff
            from .roi_tracker import foreground, cursor_region
            diff, static = FrameDiff(), 0
            with mss.mss() as capture:
                monitor = capture.monitors[1]
                while not self.stop_event.is_set():
                    start = time.monotonic()
                    frame = np.asarray(capture.grab(monitor))
                    regions = diff.update(frame, (monitor['left'], monitor['top']))
                    app, title, _, dialog = foreground()
                    static = 0 if regions else static + 1
                    with self.lock:
                        old = self.state
                        changed = bool(regions) or title != old.foreground_title
                        self.state = PerceptionState(app, title, 'dialog' if dialog else 'active' if regions else 'static',
                            old.visible_text, old.errors, regions, cursor_region(), old.revision + int(changed), time.time())
                    delay = .083 if static < 24 else .4
                    self.stop_event.wait(max(0, delay - (time.monotonic() - start)))
        except Exception as error:
            self.error = f'{type(error).__name__}: {error}'[:300]
            with self.lock:
                self.state = PerceptionState(activity='error', revision=self.state.revision)


perception = ScreenPerception()
