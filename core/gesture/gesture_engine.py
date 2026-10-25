from .gesture_state import GestureEvent


class GestureEngine:
    def __init__(self, stability=.12, cooldown=.15):
        self.stability, self.cooldown = stability, cooldown
        self.states = {}
        self.pokes = {}
        self.previous = {}
        self.two = None
        self.rotations = {}

    def update(self, hands, timestamp):
        hands=tuple(hand for hand in hands if hand.confidence>=.65)
        present = {h.hand_id for h in hands}
        events=[]
        for hand_id,old in self.states.items():
            previous=self.previous.get(hand_id)
            if hand_id not in present and old[2] and previous:
                event=self._event(previous,old[0],'exit')
                events.append(event)
        self.states = {k:v for k,v in self.states.items() if k in present}
        self.pokes = {k:v for k,v in self.pokes.items() if k in present}
        self.previous = {k:v for k,v in self.previous.items() if k in present}
        self.rotations={k:v for k,v in self.rotations.items() if k in present}
        for hand in hands:
            thumb, index, middle, ring, pinky = hand.finger_states
            thumb_up = False
            if thumb and not any((index, middle, ring, pinky)):
                if len(hand.landmarks) > 4 and hand.landmarks[4].y < hand.landmarks[2].y:
                    thumb_up = True
            pinch = hand.pinch_distance < .25
            two_finger = index and middle and not ring and not pinky and not pinch
            index_only = index and not any((middle, ring, pinky)) and not thumb_up
            fist = not any((index, middle, ring, pinky)) and not thumb_up
            open_palm = all((index, middle, ring, pinky))

            if thumb_up:
                pose = 'THUMBS_UP'
            elif pinch:
                pose = 'PINCH'
            elif two_finger:
                pose = 'TWO_FINGER'
            elif index_only:
                pose = 'INDEX_ONLY'
            elif fist:
                pose = 'FIST'
            elif open_palm:
                pose = 'OPEN_PALM'
            else:
                pose = 'POINT'
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
                    elif not locked and hand.relative_depth<baseline-.05:
                        self.pokes[hand.hand_id]=(hand.relative_depth,palm,False)
                    elif locked and hand.relative_depth-baseline<.07:
                        self.pokes[hand.hand_id]=(baseline,palm,False)
                    elif not locked and hand.relative_depth-baseline>.2 and speed>.8:
                        events.append(self._event(hand,'POKE','enter'))
                        self.pokes[hand.hand_id]=(baseline,palm,True)
                else:
                    self.pokes.pop(hand.hand_id,None)
                import math
                wrist,knuckle=hand.landmarks[0],hand.landmarks[5]
                angle=math.atan2(knuckle.y-wrist.y,knuckle.x-wrist.x)
                baseline,candidate=self.rotations.setdefault(hand.hand_id,(angle,None))
                delta=math.atan2(math.sin(angle-baseline),math.cos(angle-baseline))
                if abs(delta)>.2:
                    if candidate is None:self.rotations[hand.hand_id]=(baseline,timestamp)
                    elif timestamp-candidate>=self.stability:
                        events.append(GestureEvent('WRIST_ROTATE',hand.hand_id,hand.confidence,timestamp,
                            (hand.palm_center.x,hand.palm_center.y,hand.palm_center.z),(0,0,delta),{'phase':'enter'}))
                        self.rotations[hand.hand_id]=(angle,None)
                else:self.rotations[hand.hand_id]=(baseline,None)
            self.previous[hand.hand_id]=hand
        self._two_hands(hands,timestamp,events)
        return events

    def _two_hands(self,hands,timestamp,events):
        if len(hands)!=2 or not all(self.states.get(h.hand_id,(None,None,False))[2] for h in hands):
            self.two=None;return
        identity=tuple(sorted(h.hand_id for h in hands))
        distance=hands[0].palm_center.distance(hands[1].palm_center)
        poses=[self.states[h.hand_id][0] for h in hands]
        if self.two is None or self.two['identity']!=identity:
            self.two={'identity':identity,'distance':distance,'candidate':'','since':timestamp,'active':False}
        delta=distance-self.two['distance']
        pulling=all(p in ('PINCH','GRAB','FIST') for p in poses)
        name=('TWO_HAND_PULL' if delta>.15 else '') if pulling else ('TWO_HAND_SPREAD' if delta>.08 else 'TWO_HAND_CLOSE' if delta<-.08 else '') if all(p=='OPEN_PALM' for p in poses) else ''
        if name!=self.two['candidate']:
            if self.two['active']:
                events.append(GestureEvent(self.two['candidate'],'both',min(h.confidence for h in hands),timestamp,(0,0,0),(delta,0,0),{'phase':'exit'}))
                self.two['distance']=distance
            self.two.update(candidate=name,since=timestamp,active=False)
        elif name and timestamp-self.two['since']>=self.stability:
            events.append(GestureEvent(name,'both',min(h.confidence for h in hands),timestamp,(0,0,0),(delta,0,0),{'phase':'update' if self.two['active'] else 'enter','distance':distance}))
            self.two['active']=True

    @staticmethod
    def _event(hand,pose,phase):
        tip=hand.landmarks[8]
        return GestureEvent(pose,hand.hand_id,hand.confidence,hand.timestamp,(tip.x,tip.y,tip.z),metadata={'phase':phase})
