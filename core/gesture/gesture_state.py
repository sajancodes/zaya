from dataclasses import dataclass, field
from enum import Enum


class InteractionMode(str, Enum):
    DISABLED = 'DISABLED'
    NAVIGATION = 'NAVIGATION'
    KEYBOARD = 'KEYBOARD'
    SPATIAL = 'SPATIAL'
    SELECTION = 'SELECTION'


@dataclass(frozen=True)
class GestureEvent:
    type: str
    hand_id: str
    confidence: float
    timestamp: float
    position: tuple
    delta: tuple = (0,0,0)
    metadata: dict = field(default_factory=dict)
