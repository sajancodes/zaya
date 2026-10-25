"""Frozen installs keep mutable diagnostics outside root-owned binaries."""
import importlib
import sys


def test_frozen_runtime_files_use_user_data(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    monkeypatch.setenv('ZAYA_USER_DATA_DIR', str(tmp_path / 'userdata'))
    from core import audit, desktop_lifecycle, runtime_logging
    for module in (audit, desktop_lifecycle, runtime_logging):
        importlib.reload(module)
    try:
        audit.write({'event': 'release-path-check'})
        desktop_lifecycle.record_desktop()
        runtime_logging.log_line('release-path-check', path=runtime_logging.LOG_PATH)
        assert (tmp_path / 'userdata/logs/runtime/events.jsonl').is_file()
        assert (tmp_path / 'userdata/logs/desktop-process.json').is_file()
        assert (tmp_path / 'userdata/logs/runtime/zaya.log').is_file()
    finally:
        for logger in runtime_logging._loggers.values():
            for handler in logger.handlers:
                handler.close()
        monkeypatch.undo()
        for module in (audit, desktop_lifecycle, runtime_logging):
            importlib.reload(module)


def test_linux_state_paths_leave_bundled_resources_read_only(tmp_path, monkeypatch):
    from core import runtime_paths
    resources = tmp_path / 'install' / '_internal'
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    monkeypatch.setattr(sys, 'platform', 'linux')
    monkeypatch.setattr(sys, '_MEIPASS', str(resources), raising=False)
    monkeypatch.setattr(sys, 'executable', str(tmp_path / 'install' / 'Zaya'))
    monkeypatch.setenv('ZAYA_USER_DATA_DIR', str(tmp_path / 'userdata'))
    for kind in ('memory', 'config', 'logs', 'models'):
        target = runtime_paths.mutable_path(resources / kind / 'state')
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('test-only')
        assert target == tmp_path / 'userdata' / kind / 'state'
    assert not resources.exists()
    asset = resources / 'assets' / 'standby.png'
    assert runtime_paths.mutable_path(asset) == asset
    monkeypatch.setattr(sys, 'platform', 'win32')
    legacy = resources / 'memory' / 'conversation.db'
    assert runtime_paths.mutable_path(legacy) == legacy
