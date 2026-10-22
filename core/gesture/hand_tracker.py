import threading
import time
import os
import json
import subprocess
import base64
import uuid
from pathlib import Path
from .hand_model import normalize
from .smoothing import LandmarkSmoother

DEFAULT_MODEL=Path(__file__).resolve().parents[2]/'models'/'hand_landmarker.task'


class HandTracker:
    """Optional MediaPipe worker. Camera/model owned and closed on this thread."""
    def __init__(self, callback):
        self.callback = callback
        self.state, self.error = 'OFF', ''
        self.stop_event = threading.Event()
        self.active_event = threading.Event()
        self.worker = None
        self.child = None
        self.device=0
        self.latest_frame=None
        self.frame_lock=threading.Lock()
        self.frame_event=threading.Event()
        self.pending_frame=''
        self.frame_result=None

    def start(self, model_path, device=0, fps=24, mirror=True,confidence=.65):
        if self.worker and self.worker.is_alive():
            raise RuntimeError('Stop the current camera before starting another.')
        if not Path(model_path).is_file():
            raise ValueError('Install the MediaPipe Hand Landmarker .task model and supply its local path.')
        if Path(model_path).stat().st_size>20_000_000 or not 0<=int(device)<=31:
            raise ValueError('Hand model or camera device exceeds limits.')
        self.stop_event.clear()
        self.active_event.clear()
        self.device=int(device)
        self.state, self.error = 'STARTING', ''
        self.worker = threading.Thread(target=self._run, args=(model_path,int(device),max(10,min(30,int(fps))),bool(mirror),float(confidence)),daemon=True,name='ZayaHands')
        self.worker.start()

    def wait_active(self, timeout=8.0):
        if self.state in ('ACTIVE', 'ERROR'):
            return self.state == 'ACTIVE'
        ok = self.active_event.wait(timeout)
        if not ok and self.state == 'STARTING':
            self.error = f'Camera startup timed out after {timeout}s.'
            self.state = 'ERROR'
            self.active_event.set()
            return False
        return self.state == 'ACTIVE'

    def stop(self):
        self.stop_event.set()
        self.active_event.set()
        if self.child and self.child.poll() is None:
            try:
                self.child.stdin.write('stop\n');self.child.stdin.flush()
            except (OSError,ValueError):
                pass
        if self.worker:
            self.worker.join(3)
            if self.worker.is_alive() and self.child and self.child.poll() is None:
                self.child.terminate();self.worker.join(1)
        if not self.worker or not self.worker.is_alive():
            self.state = 'OFF'

    def _run(self, model_path, device, fps, mirror,confidence=.65):
        from core.runtime_paths import find_hand_worker
        runtime = find_hand_worker()
        if runtime and runtime.is_file() and os.environ.get('ZAYA_HAND_CHILD')!='1':
            return self._run_isolated(runtime,model_path,device,fps,mirror,confidence)
        camera = None
        try:
            import cv2
            import mediapipe as mp
            from mediapipe.tasks import python
            from mediapipe.tasks.python import vision
            options = vision.HandLandmarkerOptions(base_options=python.BaseOptions(model_asset_path=model_path),
                running_mode=vision.RunningMode.VIDEO,num_hands=2,min_hand_detection_confidence=confidence,
                min_hand_presence_confidence=confidence,min_tracking_confidence=confidence)
            with vision.HandLandmarker.create_from_options(options) as detector:
                camera = cv2.VideoCapture(device)
                camera.set(cv2.CAP_PROP_BUFFERSIZE,1)
                camera.set(cv2.CAP_PROP_FRAME_WIDTH,640);camera.set(cv2.CAP_PROP_FRAME_HEIGHT,480)
                camera.set(cv2.CAP_PROP_FPS,fps)
                if not camera.isOpened():
                    raise RuntimeError('Camera is unavailable or in use.')
                smooth, previous = {}, {}
                self.state = 'ACTIVE'
                self.active_event.set()
                self.callback(())
                while not self.stop_event.is_set():
                    at = time.monotonic()
                    ok, frame = camera.read()
                    if not ok:
                        raise RuntimeError('Camera stopped returning frames.')
                    self.latest_frame=frame
                    if mirror:
                        frame = cv2.flip(frame,1)
                    rgb = cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)
                    result = detector.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB,data=rgb),int(at*1000))
                    hands = []
                    for i, landmarks in enumerate(result.hand_landmarks):
                        category = result.handedness[i][0]
                        identity = category.category_name
                        if category.score < confidence or identity in {h.hand_id for h in hands}:
                            continue
                        filtered = smooth.setdefault(identity,LandmarkSmoother()).update(landmarks,at)
                        try:
                            hand = normalize(identity,filtered,result.hand_world_landmarks[i],category.score,at,previous.get(identity))
                        except ValueError:
                            continue
                        hands.append(hand)
                    present = {h.hand_id for h in hands}
                    smooth = {k:v for k,v in smooth.items() if k in present}
                    previous = {h.hand_id:h for h in hands}
                    self.callback(tuple(hands))
                    self.stop_event.wait(max(0,1/fps-(time.monotonic()-at)))
        except Exception as error:
            self.state, self.error = 'ERROR', f'{type(error).__name__}: {error}'[:300]
        finally:
            if camera is not None:
                camera.release()
            self.latest_frame=None
            self.callback(())
            if self.state != 'ERROR':
                self.state = 'OFF'

    def _run_isolated(self,runtime,model_path,device,fps,mirror,confidence):
        previous={}
        try:
            flags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
            if runtime.name.lower().endswith('.exe') and 'python' not in runtime.stem.lower():
                cmd = [str(runtime), str(Path(model_path).resolve()), str(device), str(fps), '1' if mirror else '0', str(confidence)]
            else:
                cmd = [str(runtime), '-u', '-m', 'core.gesture.worker', str(Path(model_path).resolve()), str(device), str(fps), '1' if mirror else '0', str(confidence)]
            self.child=subprocess.Popen(cmd, cwd=str(Path(__file__).resolve().parents[2]),
                stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8',creationflags=flags)
            while not self.stop_event.is_set():
                line=self.child.stdout.readline(1_500_001)
                if not line:
                    err = ''
                    if self.child and self.child.stderr:
                        try:
                            err = self.child.stderr.read().strip()
                        except Exception:
                            pass
                    if not self.stop_event.is_set():
                        msg = f'Hand worker exited before tracking completed. {err}'.strip() if err else 'Hand worker exited before tracking completed.'
                        raise RuntimeError(msg)
                    break
                if len(line)>1_500_000:
                    raise RuntimeError('Hand worker message exceeds limits.')
                data=json.loads(line)
                if data.get('kind')=='frame':
                    if data.get('id')==self.pending_frame:
                        encoded=data.get('jpeg','')
                        self.frame_result=base64.b64decode(encoded,validate=True) if encoded else None
                        self.frame_event.set()
                    continue
                if len(line)>65536:
                    raise RuntimeError('Hand landmark message exceeds limits.')
                if data.get('state')=='ERROR':
                    raise RuntimeError(data.get('error','Hand worker failed.'))
                self.state=data.get('state','STARTING')
                if self.state in ('ACTIVE','ERROR'):
                    self.active_event.set()
                from .hand_model import Point
                hands=[]
                for item in data.get('hands',[])[:2]:
                    hand=normalize(item['id'],[Point(*p) for p in item['landmarks']],
                        [Point(*p) for p in item['world']],item['confidence'],item['timestamp'],previous.get(item['id']))
                    hands.append(hand)
                previous={h.hand_id:h for h in hands}
                self.callback(tuple(hands))
        except Exception as error:
            self.state,self.error='ERROR',f'{type(error).__name__}: {error}'[:300]
            self.active_event.set()
        finally:
            self.active_event.set()
            if self.child:
                if self.child.poll() is None:
                    self.child.terminate()
                self.child.wait(timeout=5)
                for stream in (self.child.stdin,self.child.stdout,self.child.stderr):
                    if stream:
                        try:
                            stream.close()
                        except Exception:
                            pass
            self.callback(())
            if self.state!='ERROR':
                self.state='OFF'

    def jpeg_snapshot(self):
        """Explicit one-shot only; no image leaves the worker by default."""
        frame=self.latest_frame
        if frame is None:
            return None
        import cv2
        height,width=frame.shape[:2]
        scale=min(1.,1280/width,720/height)
        if scale<1:
            frame=cv2.resize(frame,(int(width*scale),int(height*scale)))
        ok,encoded=cv2.imencode('.jpg',frame,[cv2.IMWRITE_JPEG_QUALITY,82])
        return encoded.tobytes() if ok and len(encoded)<1_000_000 else None

    def capture_frame(self,timeout=2):
        if self.state!='ACTIVE':
            return None
        if not self.child:
            return self.jpeg_snapshot()
        with self.frame_lock:
            self.pending_frame=uuid.uuid4().hex;self.frame_result=None;self.frame_event.clear()
            try:
                self.child.stdin.write('capture '+self.pending_frame+'\n');self.child.stdin.flush()
                self.frame_event.wait(timeout)
                return self.frame_result
            except (OSError,ValueError):
                return None
            finally:
                self.pending_frame='';self.frame_result=None
