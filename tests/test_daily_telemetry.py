import pytest
"""Daily reporting survives restarts, retries, updates and UTC rollover."""
import json
from concurrent.futures import ThreadPoolExecutor
from core import telemetry
from web import database


def test_daily_reporting_consent_retry_restart_and_rollover(tmp_path, monkeypatch):
    monkeypatch.setattr(telemetry, 'get_user_data_dir', lambda: tmp_path)
    now = [1761263990]
    monkeypatch.setattr(telemetry.time, 'time', lambda: now[0])
    calls = []
    success = [False]
    monkeypatch.setattr(telemetry, '_post_json', lambda url, payload: calls.append((url, payload)) or success[0])
    assert not telemetry.report_install_event()
    assert not calls
    telemetry.set_telemetry_enabled(True)
    original = telemetry.get_or_create_installation_info()['installation_id']
    assert not telemetry.report_install_event()
    success[0] = True
    assert telemetry.report_install_event()
    assert len(calls) == 2
    with ThreadPoolExecutor(max_workers=4) as pool:
        assert all(pool.map(lambda _: telemetry.report_heartbeat_event(force=True), range(8)))
    assert len(calls) == 2
    # A new client / updated version uses the same durable receipt and UUID.
    monkeypatch.setattr(telemetry, 'VERSION', '0.5.2')
    assert telemetry.report_install_event()
    assert telemetry.report_heartbeat_event()
    assert len(calls) == 2
    assert telemetry.get_or_create_installation_info()['installation_id'] == original
    now[0] += 86400
    success[0] = False
    assert not telemetry.report_heartbeat_event()
    success[0] = True
    assert telemetry.report_heartbeat_event()
    assert len(calls) == 4
    assert calls[-1][1]['version'] == '0.5.2'
    telemetry.set_telemetry_enabled(False)
    now[0] += 86400
    assert not telemetry.report_heartbeat_event()
    assert len(calls) == 4
    assert json.loads((tmp_path / 'installation.json').read_text())['telemetry_enabled'] is False


def test_sqlite_daily_receipts_do_not_duplicate_installations(tmp_path, monkeypatch):
    monkeypatch.setenv('ZAYA_DATABASE_BACKEND', 'sqlite')
    monkeypatch.setenv('ZAYA_DB_PATH', str(tmp_path / 'analytics.db'))
    database.init_db()
    now = [1761263990]
    monkeypatch.setattr(database.time, 'time', lambda: now[0])
    assert database.record_install('one', 'linux', '0.5.1')
    assert not database.record_heartbeat('one', 'linux', '0.5.2')
    database.record_install('two', 'windows', '0.5.1')
    assert [r['count'] for r in database.get_analytics_metrics()['daily_actives']] == [2]
    now[0] += 86400
    database.record_heartbeat('one', 'linux', '0.5.2')
    metrics = database.get_analytics_metrics()
    assert [r['count'] for r in metrics['daily_actives']] == [2, 1]
    assert metrics['installations']['total'] == 2


def test_beta_downloads_are_counted_and_outages_do_not_block(monkeypatch):
    pytest.importorskip('fastapi', reason='fastapi not installed')
    from fastapi.testclient import TestClient
    from web import server
    calls = []
    monkeypatch.setattr(server, 'record_download', lambda *args: calls.append(args))
    client = TestClient(server.app)
    for platform, package in [('windows', 'exe'), ('linux', 'deb'), ('linux', 'rpm'), ('linux', 'portable')]:
        response = client.get(f'/api/downloads/beta/{platform}/{package}', follow_redirects=False)
        assert response.status_code == 302
        assert response.headers['location'].startswith('https://github.com/sajancodes/zaya-companion-releases/releases/download/')
        assert response.headers['cache-control'] == 'no-store'
    assert len(calls) == 4
    def offline(*args):
        raise RuntimeError('offline')
    monkeypatch.setattr(server, 'record_download', offline)
    assert client.get('/api/downloads/beta/linux/rpm', follow_redirects=False).status_code == 302
    assert client.get('/api/downloads/beta/other/exe').status_code == 404
