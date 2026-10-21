from .gesture_state import GestureEvent


class GestureEngine:
    def __init__(self, stability=.12, cooldown=.15):
        self.stability, self.cooldown = stability, cooldown
        self.states = {}
        self.pokes = {}
        self.previous = {}

    def update(self, hands, timestamp):
        present = {h.hand_id for h in hands}
        self.states = {k:v for k,v in self.states.items() if k in present}
        self.pokes = {k:v for k,v in self.pokes.items() if k in present}
        self.previous = {k:v for k,v in self.previous.items() if k in present}
        events = []
        for hand in hands:
            _, index, middle, ring, pinky = hand.finger_states
            pose = ('PINCH' if hand.pinch_distance < .25 else 'OPEN_PALM' if all((index,middle,ring,pinky)) else
                    'INDEX_ONLY' if index and not any((middle,ring,pinky)) else 'FIST' if not any((index,middle,ring,pinky)) else 'POINT')
            old = self.states.get(hand.hand_id)
            if old is None or old[0] != pose:
                if old and old[2]:
                    events.append(self._event(hand,old[0],'exit'))
                self.states[hand.hand_id] = (pose,timestamp,False, timestamp+self.cooldown if old and old[2] else timestamp)
                self.pokes.pop(hand.hand_id,None)
                continue
            if timestamp-old[1] >= self.stability and timestamp >= old[3]:
                events.append(self._event(hand,pose,'update' if old[2] else 'enter'))
                self.states[hand.hand_id] = (pose,old[1],True,old[3])
                if pose=='INDEX_ONLY':
                    baseline,palm,locked=self.pokes.setdefault(hand.hand_id,(hand.relative_depth,hand.palm_center,False))
                    previous=self.previous.get(hand.hand_id)
                    dt=hand.timestamp-previous.timestamp if previous else 0
                    speed=(hand.relative_depth-previous.relative_depth)/dt if .001<dt<.2 else 0
                    if hand.palm_center.distance(palm)>.035:
                        self.pokes[hand.hand_id]=(hand.relative_depth,hand.palm_center,False)
                    elif locked and hand.relative_depth-baseline<.07:
                        self.pokes[hand.hand_id]=(baseline,palm,False)
                    elif not locked and hand.relative_depth-baseline>.2 and speed>.8:
                        events.append(self._event(hand,'POKE','enter'))
                        self.pokes[hand.hand_id]=(baseline,palm,True)
                else:
                    self.pokes.pop(hand.hand_id,None)
            self.previous[hand.hand_id]=hand
        return events

    @staticmethod
    def _event(hand,pose,phase):
        tip=hand.landmarks[8]
        return GestureEvent(pose,hand.hand_id,hand.confidence,hand.timestamp,(tip.x,tip.y,tip.z),metadata={'phase':phase})
