import hashlib
from unittest.mock import patch

import pytest

from core.version import semver_key
from core.update.desktop_updater import DesktopUpdater, DesktopUpdateManifest
from web.release_validation import validate_release


def test_shared_quota_outage_returns_safe_503(monkeypatch):
    from fastapi.testclient import TestClient
    from web import server
    from web.shared_limits import RateLimitUnavailable
    def unavailable(subject):
        raise RateLimitUnavailable('internal credential detail')
    monkeypatch.setattr(server, 'is_rate_limited', unavailable)
    response = TestClient(server.app).post('/api/telemetry/heartbeat', json={
        'installation_id': '12345678-1234-4123-8123-123456789abc', 'platform': 'windows', 'version': '0.5.0'})
    assert response.status_code == 503
    assert 'internal credential detail' not in response.text


def test_update_health_is_opt_in_and_uses_only_allowed_fields(tmp_path, monkeypatch):
    from core import telemetry
    monkeypatch.setenv('ZAYA_USER_DATA_DIR', str(tmp_path))
    calls = []
    monkeypatch.setattr(telemetry, '_post_json', lambda url, data: calls.append(data) or True)
    assert telemetry.report_update_event('available', '0.5.1') is False
    assert calls == []
    telemetry.set_telemetry_enabled(True)
    assert telemetry.report_update_event('download_verified', '0.5.1') is True
    assert set(calls[0]) == {'installation_id', 'platform', 'version', 'event_id', 'stage', 'target_version'}
    assert telemetry.report_update_event('private exception text', '0.5.1') is False
    assert telemetry.report_update_event('failed', 'private exception text') is False
    assert len(calls) == 1


def test_update_api_rejects_arbitrary_error_content():
    from fastapi.testclient import TestClient
    from web.server import app
    payload = {'installation_id':'12345678-1234-4123-8123-123456789abc', 'event_id':'12345678-1234-4123-8123-123456789abd',
               'platform':'windows', 'version':'0.5.0', 'target_version':'0.5.1', 'stage':'failed', 'error':'private message'}
    response = TestClient(app).post('/api/telemetry/update', json=payload)
    assert response.status_code == 422


def metadata(**changes):
    return dict(schema=1, platform='windows', channel='stable', version='1.0.0', build=10008,
                filename='ZayaSetup.exe', size=2000, sha256='a'*64,
                url='https://github.com/sajancodes/zaya-companion-releases/releases/download/v1.0.0/ZayaSetup.exe', **changes)


def test_semver_order_and_strict_identifiers():
    versions = ['1.0.0-beta.2', '1.0.0-beta.10', '1.0.0', '1.0.1', '2.0.0']
    assert sorted(reversed(versions), key=semver_key) == versions
    with pytest.raises(ValueError):
        semver_key('1.0.0-beta.01')


def test_canonical_installer_and_immutable_official_url():
    assert DesktopUpdateManifest.parse(metadata()).filename == 'ZayaSetup.exe'
    for url in ['https://github.com/other/sajancodes/zaya-companion-releases/releases/download/v1/ZayaSetup.exe',
                'https://github.com/sajancodes/zaya-companion-releases/releases/latest/download/ZayaSetup.exe']:
        data = metadata(); data['url'] = url
        with pytest.raises(ValueError):
            DesktopUpdateManifest.parse(data)
        with pytest.raises(ValueError):
            validate_release(data)


def test_staged_installer_tampering_blocks_execution(tmp_path):
    updater = DesktopUpdater()
    payload = b'MZ' * 1000
    data = metadata(); data['sha256'] = hashlib.sha256(payload).hexdigest()
    updater.available_manifest = DesktopUpdateManifest.parse(data)
    staged = tmp_path / 'ZayaSetup.exe'; staged.write_bytes(b'X' * len(payload))
    updater.ready_installer = staged
    with patch('subprocess.Popen') as launch:
        assert not updater.apply_update(restart=False)
        launch.assert_not_called()


def test_missing_signing_certificate_blocks_public_packaging(tmp_path):
    from tools.prepare_windows_release import prepare_windows_release
    (tmp_path / 'Zaya.exe').write_bytes(b'MZ')
    with pytest.raises(RuntimeError, match='certificate'):
        prepare_windows_release(tmp_path, tmp_path / 'out', '1.0.0', 10008)


def test_vercel_cannot_use_ephemeral_sqlite(monkeypatch):
    from web.database import get_db_path
    monkeypatch.setenv('VERCEL', '1')
    with pytest.raises(RuntimeError, match='Firebase'):
        get_db_path()


def test_signing_failure_does_not_expose_certificate_password():
    import subprocess
    from tools.prepare_windows_release import _run_signing
    command = ['signtool.exe', 'sign', '/p', 'fixture-private-password']
    with patch('subprocess.run', side_effect=subprocess.CalledProcessError(1, command)):
        with pytest.raises(RuntimeError) as caught:
            _run_signing(command)
    assert 'fixture-private-password' not in str(caught.value)
