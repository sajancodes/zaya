import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from core.execution_policy import with_trust, TRUST_EXTERNAL_MESSAGE
import pytest


def test_passive_keyboard_never_requests_focus_and_coalesces_updates():
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import Qt
    from core.ghost_overlay import install_ghost_overlay,update_passive_overlay
    app=QApplication.instance() or QApplication([])
    bridge=install_ghost_overlay(lambda text:None)
    import threading
    def produce():
        for i in range(100):
            update_passive_overlay({'visible':True,'mode':'virtual_keyboard','key':'H','state':str(i)})
    worker=threading.Thread(target=produce);worker.start();worker.join()
    assert bridge.pending['state']=='99'
    app.processEvents()
    overlay=bridge.passive
    assert overlay.windowFlags() & Qt.WindowType.WindowDoesNotAcceptFocus
    assert overlay.windowFlags() & Qt.WindowType.WindowTransparentForInput
    assert overlay.testAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
    assert overlay.packet['state']=='99'
    update_passive_overlay({'visible':False});app.processEvents()
    assert not overlay.isVisible()


def test_external_text_cannot_enable_camera_or_capture():
    from actions.hand_controls import hand_controls
    from actions.display_perception import display_perception
    with with_trust(TRUST_EXTERNAL_MESSAGE):
        with pytest.raises(PermissionError):
            hand_controls({'action':'start'})
        with pytest.raises(PermissionError):
            display_perception({'action':'start'})
