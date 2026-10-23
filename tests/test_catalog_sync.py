import io
import json

import pytest

from web import database


def fixture_release(platform='windows'):
    return {'draft':False, 'prerelease':False, 'published_at':'2026-10-23T00:00:00Z', 'body':'Release notes',
            'assets':[{'name':'desktop-update.json', 'browser_download_url':'https://github.com/sajancodes/zaya-companion-releases/releases/download/v0.5.0/desktop-update.json'},
                      {'name':'ZayaSetup.exe', 'browser_download_url':'https://github.com/sajancodes/zaya-companion-releases/releases/download/v0.5.0/ZayaSetup.exe',
                       'size':2048, 'digest':'sha256:' + 'a'*64}]}


def test_targeted_sync_checks_asset_integrity_and_retains_build(monkeypatch):
    release = fixture_release()
    manifest = {'version':'0.5.0', 'filename':'ZayaSetup.exe', 'sha256':'a'*64, 'size':2048, 'build':10007}
    def read(request, **kwargs):
        return io.BytesIO(json.dumps(release if '/tags/' in request.full_url else manifest).encode())
    monkeypatch.setattr('urllib.request.urlopen', read)
    stored = []
    monkeypatch.setattr(database, 'upsert_release', lambda **data: stored.append(data))
    result = database.sync_releases_from_github(strict=True, tag='v0.5.0')
    assert result['releases'] == [{'platform':'windows', 'version':'0.5.0', 'channel':'stable'}]
    assert stored[0]['build'] == 10007
    stored.clear()
    release['assets'][1]['digest'] = 'sha256:' + 'b'*64
    with pytest.raises(RuntimeError):
        database.sync_releases_from_github(strict=True, tag='v0.5.0')
    assert stored == []


def test_missing_manifest_fails_catalog_promotion(monkeypatch):
    monkeypatch.setattr('urllib.request.urlopen', lambda *args, **kwargs: io.BytesIO(b'{"assets":[]}'))
    with pytest.raises(RuntimeError):
        database.sync_releases_from_github(strict=True, tag='v0.5.0')


def test_sync_endpoint_never_accepts_an_admin_cookie_as_release_identity(monkeypatch):
    from fastapi.testclient import TestClient
    from web.server import app
    response = TestClient(app).post('/api/internal/releases/sync', json={'tag':'v0.5.0'},
                                    cookies={'zaya_admin_session':'a'*64})
    assert response.status_code == 401
