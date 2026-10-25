"""Native packaging must reject Windows binaries and preserve platform boundaries."""
from pathlib import Path
import importlib
import runpy
import sys
from types import SimpleNamespace

import pytest

from core import runtime_paths
from tools.prepare_linux_release import assert_clean_payload


def test_linux_payload_rejects_windows_and_private_data(tmp_path):
    for filename in ('Zaya', 'ZayaHandWorker'):
        (tmp_path / filename).write_bytes(b'\x7fELF' + b'example')
    assert_clean_payload(tmp_path)
    (tmp_path / 'Zaya').write_bytes(b'MZwindows-executable')
    with pytest.raises(ValueError, match='native ELF'):
        assert_clean_payload(tmp_path)
    (tmp_path / 'Zaya').write_bytes(b'\x7fELF' + b'example')
    (tmp_path / 'owner.db').write_bytes(b'private')
    with pytest.raises(ValueError, match='Private runtime data'):
        assert_clean_payload(tmp_path)


def test_linux_worker_resolves_native_filename(tmp_path, monkeypatch):
    monkeypatch.setattr(runtime_paths, 'sys', SimpleNamespace(platform='linux'))
    monkeypatch.setattr(runtime_paths, 'get_app_root', lambda: tmp_path)
    monkeypatch.setattr(runtime_paths, 'get_resource_dir', lambda: tmp_path)
    (tmp_path / 'ZayaHandWorker.exe').write_bytes(b'MZ')
    native = tmp_path / 'ZayaHandWorker'
    native.write_bytes(b'\x7fELF')
    assert runtime_paths.find_hand_worker() == native


def test_packaged_worker_entry_imports_as_package(monkeypatch):
    calls = []
    monkeypatch.setitem(sys.modules, 'core.gesture.worker', SimpleNamespace(main=lambda: calls.append('started')))
    entry = Path(__file__).resolve().parents[1] / 'packaging/hand_worker_entry.py'
    runpy.run_path(str(entry), run_name='__main__')
    assert calls == ['started']


def test_non_windows_updater_never_fetches_exe_manifest(tmp_path, monkeypatch):
    module = importlib.import_module('core.update.desktop_updater')
    monkeypatch.setenv('ZAYA_USER_DATA_DIR', str(tmp_path))
    updater = module.DesktopUpdater()
    monkeypatch.setattr(module, 'os', SimpleNamespace(name='posix'))
    def unexpected(*args, **kwargs):
        raise AssertionError('Linux must not fetch Windows installer metadata')
    monkeypatch.setattr(module.urllib.request, 'urlopen', unexpected)
    assert updater.check(force=True) is None
    assert updater.status == module.UpdateStatus.IDLE
