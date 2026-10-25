from core.gesture.gesture_engine import GestureEngine
from core.gesture.spatial_controller import SpatialController
from core.spatial.spatial_session import SpatialSession
from core.spatial.procedural_geometry import generate
from test_virtual_keyboard import hand
from unittest.mock import patch
import pytest


def test_spatial_poke_requires_stability_and_locks_until_retraction():
    engine=GestureEngine();events=[]
    for time,depth in ((1,0),(1.15,0),(1.2,.3),(1.25,.31),(1.3,.32)):
        events.extend(engine.update((hand(time,depth=depth),),time))
    assert len([event for event in events if event.type=='POKE'])==1
    engine.update((),1.4)
    assert engine.update((hand(1.5,depth=.3),),1.5)==[]


def test_local_hand_frame_never_calls_model_and_selection_mode_is_explicit():
    session=SpatialSession();session.renderer_connected=True;packets=[];session.listeners.add(packets.append)
    controller=SpatialController();engine=GestureEngine();sample=hand(1)
    engine.update((sample,),1)
    with patch('core.spatial.spatial_session.session',session):
        controller.update((sample,),[],engine,selection_only=True)
    assert packets[-1]['type']=='interaction.frame'
    assert packets[-1]['payload']['selection_only'] is True
    assert packets[-1]['payload']['hands'][0]['pose']=='NONE'  # Not stable yet.


def test_manipulation_commits_one_undoable_transaction_with_strict_target():
    session=SpatialSession();session.replace(generate('inline_engine').model_dump());session.select(['piston_1'])
    before=len(session.undo_stack)
    payload={'part_id':'piston_1','position':[1,2,3],'rotation':[0,0,1],'revision':session.scene.revision}
    session.manipulate(payload)
    assert len(session.undo_stack)==before+1
    assert next(p for p in session.scene.parts if p.id=='piston_1').transform.position==(1.,2.,3.)
    session.history()
    assert next(p for p in session.scene.parts if p.id=='piston_1').transform.position!=(1.,2.,3.)
    payload['part_id']='piston_2';payload['revision']=session.scene.revision
    with pytest.raises(ValueError):session.manipulate(payload)
