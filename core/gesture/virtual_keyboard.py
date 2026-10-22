from dataclasses import dataclass
from .calibration import Calibration


@dataclass(frozen=True)
class VirtualKey:
    id: str
    label: str
    output: str
    bounds: tuple
    row: int
    modifier: bool = False


def keyboard_layout():
    rows = ['1 2 3 4 5 6 7 8 9 0','Q W E R T Y U I O P','A S D F G H J K L','Shift Z X C V B N M Backspace',
            'Ctrl Alt Tab Space Enter Esc Left Up Down Right']
    return tuple(VirtualKey(label,label,label,(i/len(row.split()),r/5,1/len(row.split()),1/5),r,label in ('Ctrl','Alt','Shift'))
                 for r,row in enumerate(rows) for i,label in enumerate(row.split()))


class VirtualKeyboard:
    def __init__(self, emit, calibration=None):
        self.emit, self.config = emit, calibration or Calibration()
        self.keys = keyboard_layout()
        self.reset()

    def reset(self):
        self.state, self.key, self.since = 'idle', None, 0
        self.baseline, self.palm, self.normal, self.previous = 0, None, None, None
        self.hand_id, self.last_press = '', -1e9
        self.error = ''

    def update(self, hand, rel_pos=None):
        if hand is None or hand.confidence < .65:
            self.reset()
            return None
        if self.hand_id and self.hand_id != hand.hand_id:
            self.reset()
        self.hand_id = hand.hand_id
        now, tip = hand.timestamp, hand.landmarks[8]
        pos_x = rel_pos[0] if rel_pos is not None else tip.x
        pos_y = rel_pos[1] if rel_pos is not None else tip.y
        target = next((k for k in self.keys if k.bounds[0]<=pos_x<k.bounds[0]+k.bounds[2] and k.bounds[1]<=pos_y<k.bounds[1]+k.bounds[3]),None)
        index_only = hand.finger_states[1] and not any(hand.finger_states[2:])
        if self.state == 'locked':
            if hand.relative_depth-self.baseline < self.config.release and now-self.last_press > self.config.debounce:
                self.state, self.key, self.since = 'hover', None, now
            self.previous = hand
            return None
        if not index_only or target is None:
            self.state, self.key, self.since = 'hover', target, now
            self.previous = hand
            return None
        if self.key != target or self.palm is None or self.state in ('idle','hover'):
            self.key, self.since, self.state = target, now, 'candidate'
            self.baseline, self.palm, self.normal = hand.relative_depth, hand.palm_center, hand.palm_normal
        stable_palm = hand.palm_center.distance(self.palm) < self.config.max_palm_drift
        stable_normal = sum(getattr(hand.palm_normal,k)*getattr(self.normal,k) for k in ('x','y','z')) > .96
        if not stable_palm or not stable_normal:
            self.state, self.key = 'hover', None
        elif hand.relative_depth < self.baseline-.05:
            # Reacquiring an already-forward finger must not permanently move
            # its neutral press plane forward. Deliberate retraction re-arms.
            self.baseline,self.since=hand.relative_depth,now
            self.state='candidate'
        elif now-self.since >= self.config.stability:
            self.state = 'armed'
            previous = self.previous
            dt = now-previous.timestamp if previous else 0
            speed = (hand.relative_depth-previous.relative_depth)/dt if .001<dt<.2 else 0
            if hand.relative_depth-self.baseline >= self.config.press and speed >= self.config.min_velocity and now-self.last_press > self.config.debounce:
                # Lock before invoking the output callback; injection failure
                # must not turn one attempted press into repeated OS actions.
                self.state, self.last_press = 'locked', now
                try:
                    result = self.emit(target)
                    if result == 'latched':
                        self.error = ''
                        return None  # A modifier was armed, not injected yet.
                    if result is not True:
                        self.error = 'OS key injection was not confirmed.'
                        return None
                    self.error = ''
                    return target.id
                except Exception as error:
                    self.error = type(error).__name__
        self.previous = hand
        return None

    def strike(self, target_key=None):
        """Directly strikes the targeted or currently hovered key."""
        key = target_key or self.key
        if key is None:
            return None
        self.state = 'locked'
        import time
        self.last_press = time.monotonic()
        try:
            result = self.emit(key)
            if result == 'latched':
                self.error = ''
                return None
            if result is not True:
                self.error = 'OS key injection was not confirmed.'
                return None
            self.error = ''
            return key.id
        except Exception as error:
            self.error = type(error).__name__
            return None
