import base64
from types import SimpleNamespace
from unittest.mock import patch


def test_windows_ocr_uses_stdin_not_screenshot_files(monkeypatch):
    from actions.screen_peeler import _ocr_via_powershell
    monkeypatch.setattr('actions.screen_peeler.sys.platform','win32')
    with patch('actions.screen_peeler.subprocess.run',return_value=SimpleNamespace(returncode=0,stdout='Error sample')) as run:
        assert _ocr_via_powershell(b'png fixture')=='Error sample'
    args,kwargs=run.call_args
    assert base64.b64decode(kwargs['input'])==b'png fixture'
    assert 'InMemoryRandomAccessStream' in args[0][-1]
    assert 'GetFileFromPathAsync' not in args[0][-1]
