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
        self.ocr_enabled=False

    def snapshot(self):
        with self.lock:
            return self.state

    def start(self,ocr=False):
        with self.lock:
            self.ocr_enabled=bool(ocr)
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
        executor=None
        try:
            # Reuse the existing screen module's optional mss dependency.
            from actions.screen_processor import mss
            import numpy as np
            from .frame_diff import FrameDiff
            from .roi_tracker import foreground, cursor_region
            diff, static = FrameDiff(), 0
            from concurrent.futures import ThreadPoolExecutor
            executor=ThreadPoolExecutor(max_workers=1,thread_name_prefix='ZayaLocalOCR')
            future=None;ocr_title='';last_ocr=0
            with mss.mss() as capture:
                monitor = capture.monitors[1]
                while not self.stop_event.is_set():
                    start = time.monotonic()
                    frame = np.asarray(capture.grab(monitor))
                    regions = diff.update(frame, (monitor['left'], monitor['top']))
                    app, title, _, dialog = foreground()
                    text=self.state.visible_text if title==self.state.foreground_title else ''
                    if future and future.done():
                        try:
                            if self.ocr_enabled and title==ocr_title:
                                text=future.result()[:4000]
                        except Exception:
                            pass
                        future=None
                    if self.ocr_enabled and regions and future is None and start-last_ocr>=2:
                        # Encode only the newest largest ROI, entirely in memory.
                        from io import BytesIO
                        from PIL import Image
                        from actions.screen_peeler import _ocr_via_powershell
                        x,y,w,h=regions[0];left=max(0,x-monitor['left']);top=max(0,y-monitor['top'])
                        crop=frame[top:top+min(h,720),left:left+min(w,1280),:3][:,:,::-1]
                        if crop.size:
                            buffer=BytesIO();Image.fromarray(crop).save(buffer,format='PNG')
                            future=executor.submit(_ocr_via_powershell,buffer.getvalue());ocr_title=title;last_ocr=start
                    import re
                    errors=tuple(line[:300] for line in text.splitlines() if re.search(r'\b(error|exception|traceback|failed|failure)\b',line,re.I))[:8]
                    static = 0 if regions else static + 1
                    with self.lock:
                        old = self.state
                        changed = bool(regions) or title != old.foreground_title
                        self.state = PerceptionState(app, title, 'dialog' if dialog else 'active' if regions else 'static',
                            text, errors, regions, cursor_region(), old.revision + int(changed or text!=old.visible_text), time.time())
                    delay = .083 if static < 24 else .4
                    self.stop_event.wait(max(0, delay - (time.monotonic() - start)))
        except Exception as error:
            self.error = f'{type(error).__name__}: {error}'[:300]
            with self.lock:
                self.state = PerceptionState(activity='error', revision=self.state.revision)
        finally:
            if executor:
                executor.shutdown(wait=False,cancel_futures=True)


perception = ScreenPerception()
