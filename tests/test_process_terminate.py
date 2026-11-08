from unittest.mock import MagicMock, patch
import pytest

from actions.process_terminate import _terminate_windows, _PROTECTED


def test_protected_stems_include_system_processes():
    assert "system" in _PROTECTED
    assert "csrss.exe" in _PROTECTED
    assert "services.exe" in _PROTECTED


def test_terminate_windows_success():
    proc = MagicMock()
    proc.pid = 1234
    proc.ppid.return_value = 1

    with patch("actions.process_terminate._root_matches", return_value=[proc]), \
         patch("subprocess.run") as mock_run, \
         patch("psutil.pid_exists", return_value=False):
        mock_run.return_value = MagicMock(returncode=0)
        errors = _terminate_windows([proc])
        assert errors == []
        mock_run.assert_called_once()


def test_terminate_windows_fallback_to_psutil_on_taskkill_failure():
    proc = MagicMock()
    proc.pid = 5678
    proc.ppid.return_value = 1

    child = MagicMock()
    child.pid = 5679
    proc.children.return_value = [child]

    with patch("actions.process_terminate._root_matches", return_value=[proc]), \
         patch("subprocess.run") as mock_run, \
         patch("psutil.pid_exists", return_value=True):
        # taskkill fails
        mock_run.return_value = MagicMock(returncode=1, stderr="Access is denied")
        errors = _terminate_windows([proc])
        assert "Access is denied" in errors
        # child and parent kill must be called as fallback
        child.kill.assert_called_once()
        proc.kill.assert_called_once()
