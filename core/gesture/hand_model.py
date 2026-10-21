from dataclasses import dataclass
import math


@dataclass(frozen=True)
class Point:
    x: float
    y: float
    z: float = 0

    def distance(self, other):
        return math.sqrt((self.x-other.x)**2 + (self.y-other.y)**2 + (self.z-other.z)**2)


@dataclass(frozen=True)
class HandState:
    hand_id: str
    handedness: str
    landmarks: tuple
    world_landmarks: tuple
    palm_center: Point
    palm_normal: Point
    finger_states: tuple
    velocity: Point
    confidence: float
    timestamp: float
    relative_depth: float
    pinch_distance: float


def normalize(hand_id, landmarks, world=(), confidence=1., timestamp=0., previous=None):
    points = tuple(Point(float(p.x), float(p.y), float(p.z)) for p in landmarks)
    if len(points) != 21 or not all(math.isfinite(v) for p in points for v in (p.x,p.y,p.z)):
        raise ValueError('Expected 21 finite landmarks.')
    palm = Point(*(sum(getattr(points[i], a) for i in (0,5,9,17))/4 for a in ('x','y','z')))
    a, b, wrist = points[5], points[17], points[0]
    u, v = (a.x-wrist.x,a.y-wrist.y,a.z-wrist.z), (b.x-wrist.x,b.y-wrist.y,b.z-wrist.z)
    normal = (u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0])
    length = math.sqrt(sum(n*n for n in normal))
    if length < 1e-6:
        raise ValueError('Degenerate palm plane.')
    sign = -1 if normal[2] > 0 else 1
    normal = Point(*(sign*n/length for n in normal))
    scale = max(.01, a.distance(b))
    depth = sum((getattr(points[8],k)-getattr(palm,k))*getattr(normal,k) for k in ('x','y','z'))/scale
    fingers = tuple(points[tip].distance(wrist) > points[pip].distance(wrist)*1.15 for tip,pip in ((4,3),(8,6),(12,10),(16,14),(20,18)))
    dt = timestamp - previous.timestamp if previous else 0
    velocity = Point(*((getattr(palm,k)-getattr(previous.palm_center,k))/dt for k in ('x','y','z'))) if dt > .001 and dt < .25 else Point(0,0,0)
    return HandState(hand_id,hand_id,points,tuple(Point(p.x,p.y,p.z) for p in world),palm,normal,
                     fingers,velocity,confidence,timestamp,depth,points[4].distance(points[8])/scale)
