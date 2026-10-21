import numpy as np
from core.perception.frame_diff import FrameDiff


def test_noise_is_ignored_but_dialog_region_detected():
    compare=FrameDiff();frame=np.zeros((360,640,3),dtype=np.uint8)
    assert compare.update(frame)
    assert not compare.update(frame)
    noise=frame.copy();noise[10:12,10:12]=255
    assert not compare.update(noise)
    dialog=frame.copy();dialog[100:220,200:420]=255
    regions=compare.update(dialog,origin=(-640,0))
    assert regions and regions[0][0]<0


def test_import_has_no_capture_side_effects():
    from core.perception.screen_perception import ScreenPerception
    service=ScreenPerception()
    assert service.worker is None and service.snapshot().activity=='off'
