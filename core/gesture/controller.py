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

    def _inject(self, key):
        if self.mode != InteractionMode.KEYBOARD:
            return False
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
            self.engine.update(hands,hands[0].timestamp if hands else 0)
            hand = hands[0] if hands else None
            if self.mode == InteractionMode.KEYBOARD:
                sent = self.keyboard.update(hand)
                update_passive_overlay({'mode':'virtual_keyboard','visible':True,
                    'state':self.keyboard.state,'key':self.keyboard.key.id if self.keyboard.key else '',
                    'sent':sent or '', 'error':self.keyboard.error, 'modifiers':sorted(self.modifiers)})
            else:
                self.keyboard.reset()

    def stop(self):
        # Revoke injection before joining the camera; no output can race stop.
        with self.lock:
            self.mode = InteractionMode.DISABLED
            self.modifiers.clear()
            self.keyboard.reset()
        self.tracker.stop()
        from core.ghost_overlay import update_passive_overlay
        update_passive_overlay({'visible':False,'mode':'virtual_keyboard'})

    def start(self, model_path, mode, device=0, fps=24, mirror=True):
        requested = InteractionMode(mode)
        if requested not in (InteractionMode.NAVIGATION,InteractionMode.KEYBOARD):
            raise ValueError('Only NAVIGATION and KEYBOARD are implemented yet.')
        self.stop()
        with self.lock:
            self.mode = requested
            try:
                self.tracker.start(model_path,device,fps,mirror)
            except Exception:
                self.mode = InteractionMode.DISABLED
                raise

    def status(self):
        return {'mode':self.mode.value,'camera':self.tracker.state,'error':self.tracker.error,
                'keyboard':self.keyboard.state,'injection_error':self.keyboard.error}


hands = HandController()
