import time
from pathlib import Path
from unittest.mock import patch, MagicMock
from core.background_sentinel import BackgroundSentinel, SentinelAlert


def test_sentinel_alert_to_dict():
    alert = SentinelAlert(
        id="test_1",
        category="server",
        summary="Server on port 3000 crashed",
        severity="high",
    )
    d = alert.to_dict()
    assert d["id"] == "test_1"
    assert d["category"] == "server"
    assert d["summary"] == "Server on port 3000 crashed"


def test_sentinel_port_drop_alert():
    sentinel = BackgroundSentinel()
    # Simulate port 3000 was open
    sentinel._open_ports = {3000}

    # In next check, port 3000 is closed
    with patch("socket.socket") as mock_socket:
        mock_inst = MagicMock()
        mock_inst.connect_ex.return_value = 1  # Connection refused
        mock_socket.return_value = mock_inst

        alerts = sentinel.check_ports()
        assert len(alerts) == 1
        assert "port 3000" in alerts[0].summary
        assert sentinel._open_ports == set()

        # Check queue consumption
        next_item = sentinel.next_alert()
        assert next_item is not None
        assert next_item["id"] == alerts[0].id

        sentinel.delivered(next_item)
        assert sentinel.next_alert() is None


def test_sentinel_git_conflict_detection(tmp_path):
    sentinel = BackgroundSentinel()
    conflict_file = tmp_path / "app.py"
    conflict_file.write_text("def hello():\n<<<<<<< HEAD\n    return 1\n=======\n    return 2\n>>>>>>> branch\n", encoding="utf-8")

    alerts = sentinel.check_git_conflicts(workspace_root=tmp_path)
    assert len(alerts) == 1
    assert "Merge conflict" in alerts[0].summary
