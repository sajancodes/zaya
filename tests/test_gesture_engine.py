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
