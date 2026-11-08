from pathlib import Path
from unittest.mock import MagicMock, patch

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
    store = tmp_path / "alerts.json"
    sentinel = BackgroundSentinel(store_path=store)
    conflict_file = tmp_path / "app.py"
    conflict_file.write_text("def hello():\n<<<<<<< HEAD\n    return 1\n=======\n    return 2\n>>>>>>> branch\n", encoding="utf-8")

    alerts = sentinel.check_git_conflicts(workspace_root=tmp_path, force=True)
    assert len(alerts) == 1
    assert "Merge conflict" in alerts[0].summary


def test_conflict_alert_stable_id_across_scans(tmp_path):
    store = tmp_path / "alerts.json"
    sentinel = BackgroundSentinel(store_path=store)
    conflict_file = tmp_path / "app.py"
    conflict_file.write_text("code\n<<<<<<< HEAD\n1\n=======\n2\n>>>>>>> branch\n", encoding="utf-8")

    alerts1 = sentinel.check_git_conflicts(workspace_root=tmp_path, force=True)
    assert len(alerts1) == 1
    id1 = alerts1[0].id

    alerts2 = sentinel.check_git_conflicts(workspace_root=tmp_path, force=True)
    assert len(alerts2) == 1
    id2 = alerts2[0].id

    assert id1 == id2
    assert id1.startswith("conflict:")


def test_conflict_alert_new_id_on_content_change(tmp_path):
    store = tmp_path / "alerts.json"
    sentinel = BackgroundSentinel(store_path=store)
    conflict_file = tmp_path / "service.py"
    conflict_file.write_text("code\n<<<<<<< HEAD\nAAA\n=======\nBBB\n>>>>>>> branch\n", encoding="utf-8")

    alerts1 = sentinel.check_git_conflicts(workspace_root=tmp_path, force=True)
    id1 = alerts1[0].id

    # Change content
    conflict_file.write_text("code\n<<<<<<< HEAD\nCCC\n=======\nDDD\n>>>>>>> branch\n", encoding="utf-8")
    alerts2 = sentinel.check_git_conflicts(workspace_root=tmp_path, force=True)
    id2 = alerts2[0].id

    assert id1 != id2


def test_conflict_alert_persisted_delivery(tmp_path):
    store = tmp_path / "alerts.json"
    sentinel1 = BackgroundSentinel(store_path=store)
    conflict_file = tmp_path / "worker.py"
    conflict_file.write_text("<<<<<<< HEAD\nX\n=======\nY\n>>>>>>> B\n", encoding="utf-8")

    alerts = sentinel1.check_git_conflicts(workspace_root=tmp_path, force=True)
    assert len(alerts) == 1
    item = sentinel1.next_alert()
    assert item is not None
    assert item["id"] == alerts[0].id

    # Deliver it
    sentinel1.delivered(item)
    assert sentinel1.next_alert() is None

    # Restart sentinel with same persisted store
    sentinel2 = BackgroundSentinel(store_path=store)
    sentinel2.check_git_conflicts(workspace_root=tmp_path, force=True)
    assert sentinel2.next_alert() is None


def test_conflict_scan_reports_all_files(tmp_path):
    store = tmp_path / "alerts.json"
    sentinel = BackgroundSentinel(store_path=store)
    (tmp_path / "a.py").write_text("<<<<<<< HEAD\n1\n=======\n2\n>>>>>>> B\n", encoding="utf-8")
    (tmp_path / "b.kt").write_text("<<<<<<< HEAD\n3\n=======\n4\n>>>>>>> B\n", encoding="utf-8")
    (tmp_path / "c.xml").write_text("<<<<<<< HEAD\n5\n=======\n6\n>>>>>>> B\n", encoding="utf-8")

    # Put a non-conflicting file
    (tmp_path / "clean.py").write_text("print('clean')\n", encoding="utf-8")

    # Put a file in .venv which should be ignored
    venv_dir = tmp_path / ".venv" / "lib"
    venv_dir.mkdir(parents=True)
    (venv_dir / "ignored.py").write_text("<<<<<<< HEAD\nERR\n=======\nERR\n>>>>>>> B\n", encoding="utf-8")

    alerts = sentinel.check_git_conflicts(workspace_root=tmp_path, force=True)
    assert len(alerts) == 3
    filenames = {Path(a.details["file"]).name for a in alerts}
    assert filenames == {"a.py", "b.kt", "c.xml"}
