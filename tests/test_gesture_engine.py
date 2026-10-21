from core.gesture.gesture_engine import GestureEngine
from test_virtual_keyboard import hand


def test_pose_needs_stability_and_loss_clears_state():
    engine=GestureEngine()
    assert engine.update((hand(1),),1)==[]
    assert engine.update((hand(1.05),),1.05)==[]
    events=engine.update((hand(1.15),),1.15)
    assert events[0].type=='INDEX_ONLY' and events[0].metadata['phase']=='enter'
    engine.update((),1.2)
    assert engine.update((hand(1.3),),1.3)==[]


def test_two_hand_spread_needs_its_own_stability_period():
    from dataclasses import replace
    from core.gesture.hand_model import Point
    engine=GestureEngine();events=[]
    for t,distance in ((1.,.3),(1.15,.3),(1.2,.5),(1.25,.5),(1.35,.5)):
        left=replace(hand(t,index=False),hand_id='Left',palm_center=Point(.2,.5,0))
        right=replace(hand(t,index=False),palm_center=Point(.2+distance,.5,0))
        batch=engine.update((left,right),t)
        if t<1.35:assert not any(e.type=='TWO_HAND_SPREAD' for e in batch)
        events+=batch
    assert len([e for e in events if e.type=='TWO_HAND_SPREAD' and e.metadata['phase']=='enter'])==1
