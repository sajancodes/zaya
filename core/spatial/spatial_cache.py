import hashlib
import json
from pathlib import Path
from .schema import SpatialScene

ROOT=Path(__file__).resolve().parents[2]/'memory'/'spatial_cache'


def key(generator,parameters):
    raw=json.dumps({'version':1,'generator':generator,'parameters':parameters},sort_keys=True,allow_nan=False)
    return hashlib.sha256(raw.encode()).hexdigest()


def load(generator,parameters):
    path=ROOT/(key(generator,parameters)+'.json')
    try:
        if path.stat().st_size>512_000:
            return None
        return SpatialScene.model_validate_json(path.read_text(encoding='utf-8'))
    except (OSError,ValueError):
        return None


def save(generator,parameters,scene):
    ROOT.mkdir(parents=True,exist_ok=True)
    path=ROOT/(key(generator,parameters)+'.json')
    temporary=path.with_suffix('.tmp');temporary.write_text(scene.model_dump_json(),encoding='utf-8');temporary.replace(path)
    for stale in sorted(ROOT.glob('*.json'),key=lambda p:p.stat().st_mtime,reverse=True)[32:]:
        stale.unlink(missing_ok=True)
