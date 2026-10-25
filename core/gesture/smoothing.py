import math
from .hand_model import Point


class LandmarkSmoother:
    """Time-based EMA. Clear on loss to avoid interpolating across different hands."""
    def __init__(self, tau=.025):
        self.tau, self.previous, self.at = tau, None, 0

    def update(self, points, timestamp):
        if self.previous is None or timestamp-self.at > .25:
            self.previous = tuple(Point(p.x,p.y,p.z) for p in points)
        else:
            alpha = 1-math.exp(-max(.001,timestamp-self.at)/self.tau)
            self.previous = tuple(Point(*(getattr(a,k)+alpha*(getattr(b,k)-getattr(a,k)) for k in ('x','y','z')))
                                  for a,b in zip(self.previous,points))
        self.at = timestamp
        return self.previous
