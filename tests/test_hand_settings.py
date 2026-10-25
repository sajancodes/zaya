import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import pytest
from core.gesture import settings


def test_settings_are_bounded_persisted_and_never_enable_camera(tmp_path,monkeypatch):
    monkeypatch.setattr(settings,'PATH',tmp_path/'hands.json')
    assert settings.load()==settings.HandSettings()
    value=settings.HandSettings(device=1,fps=20,mirror=False,sensitivity=1.2)
    settings.save(value);assert settings.load()==value
    assert 'enabled' not in settings.PATH.read_text()
    with pytest.raises(ValueError):settings.HandSettings(fps=1000)
    with pytest.raises(ValueError):settings.HandSettings(confidence='bad')
    with pytest.raises(ValueError):settings.HandSettings(sensitivity=float('nan'))


def test_settings_panel_opens_without_starting_camera():
    from PyQt6.QtWidgets import QApplication
    from core.gesture.settings_panel import HandSettingsPanel
    from core.gesture.controller import hands
    app=QApplication.instance() or QApplication([])
    panel=HandSettingsPanel();panel.show();app.processEvents()
    assert panel.mode.count()==4 and panel.start_button.isEnabled()
    assert hands.mode.value=='DISABLED' and hands.tracker.worker is None
    panel.close()


def test_hand_typing_refuses_zayas_own_foreground_window():
    import ctypes
    from unittest.mock import MagicMock,patch
    from core.gesture.controller import HandController
    from core.gesture.gesture_state import InteractionMode
    from core.gesture.virtual_keyboard import keyboard_layout
    if os.name!='nt':pytest.skip('Windows input focus guard')
    controller=HandController();controller.mode=InteractionMode.KEYBOARD
    user=MagicMock();user.GetForegroundWindow.return_value=1
    user.GetWindowThreadProcessId.side_effect=lambda hwnd,pointer:setattr(pointer._obj,'value',os.getpid())
    with patch.object(ctypes.windll,'user32',user),patch('actions.ghost_keyboard.inject_text') as inject:
        assert controller._inject(keyboard_layout()[0]) is False
        inject.assert_not_called()


def test_stop_still_works_with_corrupted_settings(tmp_path,monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import patch
    from actions.hand_controls import hand_controls
    monkeypatch.setattr(settings,'PATH',tmp_path/'bad.json');settings.PATH.write_text('[]')
    stopped=[];fake=SimpleNamespace(stop=lambda:stopped.append(True),status=lambda:{'camera':'OFF','error':''})
    with patch('core.gesture.controller.hands',fake):
        result=hand_controls({'action':'stop'})
    assert stopped==[True] and result.status=='success' and result.data['settings_error']
