from dataclasses import dataclass,asdict
import json
import math
from pathlib import Path

def _default_settings_path():
    from core.runtime_paths import get_config_dir
    return get_config_dir() / 'hand_controls.json'

PATH = _default_settings_path()


@dataclass(frozen=True)
class HandSettings:
    device:int=0
    fps:int=24
    mirror:bool=True
    confidence:float=.65
    sensitivity:float=1.

    def __post_init__(self):
        if type(self.device) is not int or not 0<=self.device<=31 or type(self.fps) is not int or not 10<=self.fps<=30:
            raise ValueError('Camera device must be 0–31 and FPS 10–30.')
        if type(self.mirror) is not bool or type(self.confidence) not in (int,float) or type(self.sensitivity) not in (int,float) or not math.isfinite(self.confidence) or not .65<=self.confidence<=.95 or not math.isfinite(self.sensitivity) or not .5<=self.sensitivity<=2:
            raise ValueError('Invalid hand sensitivity, confidence or mirror setting.')


def load():
    if not PATH.is_file():return HandSettings()
    if PATH.stat().st_size>4096:raise ValueError('Hand settings exceed limits.')
    value=json.loads(PATH.read_text(encoding='utf-8'))
    if not isinstance(value,dict):raise ValueError('Invalid hand settings.')
    return HandSettings(**value)


def save(settings):
    PATH.parent.mkdir(parents=True,exist_ok=True)
    temp=PATH.with_suffix('.tmp');temp.write_text(json.dumps(asdict(settings)),encoding='utf-8');temp.replace(PATH)
