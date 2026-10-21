from dataclasses import dataclass


@dataclass(frozen=True)
class Calibration:
    press: float = .20
    release: float = .07
    min_velocity: float = .8
    max_palm_drift: float = .035
    stability: float = .13
    debounce: float = .18

    def __post_init__(self):
        if not (0 < self.release < self.press < 2 and .1 <= self.stability <= .5 and .05 <= self.debounce <= 1):
            raise ValueError('Invalid gesture calibration.')
