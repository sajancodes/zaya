import threading
from .gesture_state import InteractionMode
from .gesture_engine import GestureEngine
from .virtual_keyboard import VirtualKeyboard
from .hand_tracker import HandTracker


class HandController:
    def __init__(self):
        self.lock = threading.RLock()
        self.mode = InteractionMode.DISABLED
        self.engine = GestureEngine()
        self.keyboard = VirtualKeyboard(self._inject)
        self.tracker = HandTracker(self.on_hands)
        self.modifiers = set()
        from .spatial_controller import SpatialController
        self.spatial = SpatialController()
        self.last_start=None

    def _inject(self, key):
        if self.mode != InteractionMode.KEYBOARD:
            return False
        import os,ctypes
        if os.name=='nt':
            from ctypes import wintypes
            user=ctypes.windll.user32;user.GetForegroundWindow.restype=wintypes.HWND
            user.GetWindowThreadProcessId.argtypes=(wintypes.HWND,ctypes.POINTER(wintypes.DWORD))
            pid=wintypes.DWORD();user.GetWindowThreadProcessId(user.GetForegroundWindow(),ctypes.byref(pid))
            if pid.value in (0,os.getpid()):return False
        from actions.ghost_keyboard import inject_text, send_hotkey
        if key.modifier:
            if key.output.lower() in self.modifiers:
                self.modifiers.remove(key.output.lower())
            else:
                self.modifiers.add(key.output.lower())
            return 'latched'
        output = key.output.lower()
        if self.modifiers:
            result = send_hotkey('+'.join(sorted(self.modifiers))+'+'+output)
            self.modifiers.clear()
            return result
        return inject_text(key.output.lower(),0) if len(output)==1 else send_hotkey(output)

    def on_hands(self, hands):
        from core.ghost_overlay import update_passive_overlay
        with self.lock:
            if not hands:
                self.modifiers.clear()
            events=self.engine.update(hands,hands[0].timestamp if hands else 0)
            hand = hands[0] if hands else None
            if self.mode == InteractionMode.KEYBOARD:
                sent = self.keyboard.update(hand)
                update_passive_overlay({'mode':'virtual_keyboard','visible':True,
                    'state':self.keyboard.state,'key':self.keyboard.key.id if self.keyboard.key else '',
                    'sent':sent or '', 'error':self.keyboard.error, 'modifiers':sorted(self.modifiers)})
            else:
                self.keyboard.reset()
                if self.mode in (InteractionMode.SPATIAL,InteractionMode.SELECTION):
                    self.spatial.update(hands,events,self.engine,self.mode==InteractionMode.SELECTION)

    def stop(self):
        # Revoke injection before joining the camera; no output can race stop.
        with self.lock:
            self.mode = InteractionMode.DISABLED
            self.modifiers.clear()
            self.keyboard.reset()
            self.engine.states.clear();self.engine.pokes.clear();self.engine.previous.clear()
            self.engine.rotations.clear();self.engine.two=None
        self.tracker.stop()
        from core.ghost_overlay import update_passive_overlay
        update_passive_overlay({'visible':False,'mode':'virtual_keyboard'})

    def start(self, model_path, mode, device=0, fps=24, mirror=True,confidence=.65,sensitivity=1.):
        requested = InteractionMode(mode)
        if requested not in (InteractionMode.NAVIGATION,InteractionMode.KEYBOARD,InteractionMode.SPATIAL,InteractionMode.SELECTION):
            raise ValueError('Choose a supported interaction mode.')
        self.stop()
        with self.lock:
            self.mode = requested
            from .calibration import Calibration
            self.keyboard.config=Calibration(press=.2/sensitivity,release=.07/sensitivity,min_velocity=.8/sensitivity)
            try:
                self.tracker.start(model_path,device,fps,mirror,confidence)
                self.last_start=(model_path,mode,device,fps,mirror,confidence,sensitivity)
            except Exception:
                self.mode = InteractionMode.DISABLED
                raise

    def pause(self):
        self.stop();self.tracker.state='PAUSED'

    def resume(self):
        if self.tracker.state!='PAUSED' or not self.last_start:
            raise ValueError('No paused hand session to resume.')
        from .settings import load
        settings=load()
        self.start(self.last_start[0],self.last_start[1],settings.device,settings.fps,settings.mirror,settings.confidence,settings.sensitivity)

    def status(self):
        return {'mode':self.mode.value,'camera':self.tracker.state,'error':self.tracker.error,
                'keyboard':self.keyboard.state,'injection_error':self.keyboard.error}


hands = HandController()
