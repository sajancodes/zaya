"""Branding changes preserve extension compatibility and safe launcher creation."""
from pathlib import Path
from types import SimpleNamespace
from PIL import Image
import ui
from core.live_tools import INLINE_TOOL_DECLARATIONS


def test_public_ui_keeps_legacy_extension_import():
    assert ui.JarvisUI is ui.ZayaUI
    assert ui.ZayaUI.__name__ == 'ZayaUI'
    names = [tool['name'] for tool in INLINE_TOOL_DECLARATIONS]
    assert 'shutdown_zaya' in names
    assert 'shutdown_jarvis' not in names


def test_portrait_icon_and_windows_shortcut(tmp_path, monkeypatch):
    icon = tmp_path / 'portrait.ico'
    assert ui.MainWindow._build_zaya_icon(icon)
    with Image.open(icon) as picture:
        assert picture.format == 'ICO'
        assert picture.size == (128, 128)
    calls, messages = [], []
    monkeypatch.setattr(ui.platform, 'system', lambda: 'Windows')
    window = SimpleNamespace(_get_desktop_dir=lambda: tmp_path,
        _create_lnk_windows=lambda *args: calls.append(args),
        _log=SimpleNamespace(append_log=messages.append))
    ui.MainWindow._create_desktop_shortcut(window)
    assert len(calls) == 1
    assert Path(calls[0][0]).name == 'Zaya.lnk'
    assert Path(calls[0][4]).name == 'zaya.ico'
    assert messages == ['SYS: Desktop shortcut created.']
