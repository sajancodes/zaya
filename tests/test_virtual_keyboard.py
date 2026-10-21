from dataclasses import replace
from core.gesture.hand_model import HandState, Point, normalize
from core.gesture.virtual_keyboard import VirtualKeyboard


def hand(t,x=.611,y=.5,depth=0,palm_z=0,index=True):
    points=tuple(Point(x,y,-depth*.2+palm_z) for _ in range(21))
    return HandState('Right','Right',points,(),Point(.5,.6,palm_z),Point(0,0,-1),
                     (False,True,not index,not index,not index),Point(0,0,0),1.,t,depth,.5)


def test_deliberate_press_lock_retract_and_next_key():
    sent=[]
    keyboard=VirtualKeyboard(lambda key: sent.append(key.id) is None)
    for i in range(6):
        keyboard.update(hand(i*.05,x=.05+i*.1,y=.3,index=False))
    assert sent==[]
    for t in (1.,1.1,1.15):
        keyboard.update(hand(t))
    assert sent==[] and keyboard.state=='armed'
    assert keyboard.update(hand(1.2,depth=.25))=='H'
    for t,x,d in ((1.3,.611,.25),(1.4,.722,.3),(1.5,.722,.19),(1.6,.722,.21)):
        keyboard.update(hand(t,x=x,depth=d))
    assert sent==['H']
    keyboard.update(hand(1.8,x=.722,depth=0))
    for t in (1.9,2.05):
        keyboard.update(hand(t,x=.722))
    keyboard.update(hand(2.1,x=.722,depth=.25))
    assert sent==['H','J']


def test_palm_motion_pose_loss_and_failed_output_are_safe():
    sent=[];keyboard=VirtualKeyboard(lambda k:sent.append(k.id) is None)
    for t,z in ((1.,0),(1.15,0),(1.2,-.1)):
        keyboard.update(hand(t,palm_z=z,depth=.3 if z else 0))
    assert sent==[]
    keyboard.update(None)
    for t in (2.,2.15,2.2):
        keyboard.update(hand(t,depth=.3))
    assert sent==[]  # Reacquisition never inherits an old neutral depth.
    keyboard=VirtualKeyboard(lambda k:False)
    for t,d in ((3.,0),(3.15,0),(3.2,.3),(3.3,.4)):
        keyboard.update(hand(t,depth=d))
    assert keyboard.state=='locked' and keyboard.error


def test_palm_relative_depth_is_translation_invariant():
    points=[Point(.5,.8,0) for _ in range(21)]
    points[5]=Point(.35,.6,0);points[17]=Point(.65,.6,0);points[9]=Point(.5,.55,0)
    points[8]=Point(.4,.3,-.08)
    a=normalize('Right',points,timestamp=1)
    translated=[replace(p,z=p.z-.25) for p in points]
    b=normalize('Right',translated,timestamp=1.03,previous=a)
    assert abs(a.relative_depth-b.relative_depth)<1e-6


def test_hand_switch_does_not_inherit_armed_pose():
    sent=[];keyboard=VirtualKeyboard(lambda k:sent.append(k.id) is None)
    keyboard.update(hand(1.));keyboard.update(hand(1.15))
    keyboard.update(replace(hand(1.2,depth=.3),hand_id='Left'))
    assert sent==[]


def test_reacquired_forward_finger_can_retract_and_type_normally():
    sent=[];keyboard=VirtualKeyboard(lambda key:sent.append(key.id) is None)
    for t in (1,1.15,1.2):keyboard.update(hand(t,depth=.3))
    assert not sent
    keyboard.update(hand(1.3,depth=0))
    keyboard.update(hand(1.45,depth=0))
    keyboard.update(hand(1.5,depth=.25))
    assert sent==['H']
