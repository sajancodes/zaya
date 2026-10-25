import json
from core.llm.types import StreamChunk
from core.spatial.spatial_session import SpatialSession
from core.spatial.scene_planner import stream_scene
from core.spatial.procedural_geometry import generate
import pytest


def part(pid,parent=None):
    return {'part':{'id':pid,'name':pid,'parent_id':parent,'geometry':{'primitive':'box'}}}


def test_first_valid_part_is_visible_before_planner_finishes(tmp_path):
    session=SpatialSession(tmp_path/'scene.json');session.replace(generate('inline_engine').model_dump())
    class Router:
        def stream_route(self,*args,**kwargs):
            yield StreamChunk(delta_text=json.dumps(part('body'))+'\n')
            assert session.build_backup is not None and [p.id for p in session.scene.parts]==['body']
            yield StreamChunk(delta_text=json.dumps(part('detail','body'))+'\n')
            assert len(session.scene.parts)==2
            yield StreamChunk(delta_text=json.dumps({'complete':True,'relationships':[]}))
    scene=stream_scene('A small assembly',session,Router())
    assert [p.id for p in scene.parts]==['body','detail'] and session.build_backup is None
    session.history();assert session.scene.name=='Inline Engine'


def test_invalid_stream_restores_previous_scene_and_never_saves_partial(tmp_path):
    path=tmp_path/'scene.json';session=SpatialSession(path);session.replace(generate('inline_engine').model_dump())
    previous=session.scene.model_dump();saved=path.read_bytes()
    class Router:
        def stream_route(self,*args,**kwargs):
            yield StreamChunk(delta_text=json.dumps(part('body'))+'\n')
            yield StreamChunk(delta_text=json.dumps(part('body'))+'\n')
    with pytest.raises(ValueError):stream_scene('Assembly',session,Router())
    assert session.scene.parts==generate('inline_engine').parts
    assert session.scene.scene_id==previous['scene_id'] and session.build_backup is None
    assert path.read_bytes()==saved
