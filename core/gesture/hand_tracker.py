import threading
import time
import os
import json
import subprocess
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
        self.worker = None
        self.child = None

    def start(self, model_path, device=0, fps=24, mirror=True):
        if self.worker and self.worker.is_alive():
            raise RuntimeError('Stop the current camera before starting another.')
        if not Path(model_path).is_file():
            raise ValueError('Install the MediaPipe Hand Landmarker .task model and supply its local path.')
        self.stop_event.clear()
        self.state, self.error = 'STARTING', ''
        self.worker = threading.Thread(target=self._run, args=(model_path,int(device),max(10,min(30,int(fps))),bool(mirror)),daemon=True,name='ZayaHands')
        self.worker.start()

    def stop(self):
        self.stop_event.set()
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

    def _run(self, model_path, device, fps, mirror):
        runtime=Path(__file__).resolve().parents[2]/'.venv-hands'/'Scripts'/'python.exe'
        if runtime.is_file() and os.environ.get('ZAYA_HAND_CHILD')!='1':
            return self._run_isolated(runtime,model_path,device,fps,mirror)
        camera = None
        try:
            import cv2
            import mediapipe as mp
            from mediapipe.tasks import python
            from mediapipe.tasks.python import vision
            options = vision.HandLandmarkerOptions(base_options=python.BaseOptions(model_asset_path=model_path),
                running_mode=vision.RunningMode.VIDEO,num_hands=2,min_hand_detection_confidence=.65,
                min_hand_presence_confidence=.65,min_tracking_confidence=.65)
            with vision.HandLandmarker.create_from_options(options) as detector:
                camera = cv2.VideoCapture(device)
                camera.set(cv2.CAP_PROP_BUFFERSIZE,1)
                if not camera.isOpened():
                    raise RuntimeError('Camera is unavailable or in use.')
                smooth, previous = {}, {}
                self.state = 'ACTIVE'
                while not self.stop_event.is_set():
                    at = time.monotonic()
                    ok, frame = camera.read()
                    if not ok:
                        raise RuntimeError('Camera stopped returning frames.')
                    if mirror:
                        frame = cv2.flip(frame,1)
                    rgb = cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)
                    result = detector.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB,data=rgb),int(at*1000))
                    hands = []
                    for i, landmarks in enumerate(result.hand_landmarks):
                        category = result.handedness[i][0]
                        identity = category.category_name
                        if category.score < .65 or identity in {h.hand_id for h in hands}:
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
            self.callback(())
            if self.state != 'ERROR':
                self.state = 'OFF'

    def _run_isolated(self,runtime,model_path,device,fps,mirror):
        previous={}
        try:
            flags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
            self.child=subprocess.Popen([str(runtime),'-u','-m','core.gesture.worker',str(Path(model_path).resolve()),
                str(device),str(fps),'1' if mirror else '0'],cwd=str(Path(__file__).resolve().parents[2]),
                stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,encoding='utf-8',creationflags=flags)
            while not self.stop_event.is_set():
                line=self.child.stdout.readline(65537)
                if not line:
                    if not self.stop_event.is_set():
                        raise RuntimeError('Hand worker exited before tracking completed.')
                    break
                if len(line)>65536:
                    raise RuntimeError('Hand worker message exceeds limits.')
                data=json.loads(line)
                if data.get('state')=='ERROR':
                    raise RuntimeError(data.get('error','Hand worker failed.'))
                self.state=data.get('state','STARTING')
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
        finally:
            if self.child:
                if self.child.poll() is None:
                    self.child.terminate()
                self.child.wait(timeout=5)
                for stream in (self.child.stdin,self.child.stdout):
                    if stream:
                        stream.close()
            self.callback(())
            if self.state!='ERROR':
                self.state='OFF'
