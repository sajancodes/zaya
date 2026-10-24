"""Behavioral checks for consent-only, idempotent website reports."""
import copy
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError
from web import site_analytics as site


@pytest.fixture(params=['sqlite', 'firebase'])
def backend(request, monkeypatch, tmp_path):
    monkeypatch.delenv('VERCEL', raising=False)
    monkeypatch.setenv('ZAYA_DATABASE_BACKEND', request.param)
    monkeypatch.setenv('ZAYA_DB_PATH', str(tmp_path / 'analytics.db'))
    if request.param == 'firebase':
        from google.cloud import firestore
        from web import firebase_store
        documents = {}
        class Snapshot:
            def __init__(self, path):
                self.id = path.split('/')[-1]
                self.data = copy.deepcopy(documents.get(path))
                self.exists = self.data is not None
            def to_dict(self): return self.data
        class Reference:
            def __init__(self, path): self.path = path
            def get(self, transaction=None): return Snapshot(self.path)
        class Query:
            def __init__(self, name, filters=(), order=None, limit=None):
                self.name, self.filters, self.order, self.maximum = name, filters, order, limit
            def document(self, key): return Reference(self.name + '/' + key)
            def where(self, *, filter): return Query(self.name, (*self.filters, filter), self.order, self.maximum)
            def order_by(self, order): return Query(self.name, self.filters, order, self.maximum)
            def limit(self, maximum): return Query(self.name, self.filters, self.order, maximum)
            def stream(self):
                values = [Snapshot(key) for key in documents if key.startswith(self.name + '/')]
                for condition in self.filters:
                    assert condition.op_string == '>='
                    values = [row for row in values if row.data.get(condition.field_path) >= condition.value]
                if self.order: values.sort(key=lambda row: row.data[self.order])
                return values[:self.maximum] if self.maximum else values
            def count(self): return SimpleNamespace(get=lambda: [[SimpleNamespace(value=len(self.stream()))]])
        class Transaction:
            def set(self, ref, data): documents[ref.path] = copy.deepcopy(data)
        monkeypatch.setattr(firestore, 'transactional', lambda fn: fn)
        monkeypatch.setattr(firebase_store, 'client', lambda: SimpleNamespace(transaction=Transaction))
        monkeypatch.setattr(firebase_store, 'collection', Query)
    return request.param


def event(visitor=None, session=None, **values):
    return site.sanitize(site.SiteEvent(consent=True, event_id=uuid4(), visitor_id=visitor or uuid4(),
        session_id=session or uuid4(), path='/', **values), 'Chrome/100 Android Mobile secret-user-agent')


def test_counts_deduplicate_across_visits_and_periods(backend, monkeypatch):
    clock = [1800000000]
    monkeypatch.setattr(site.time, 'time', lambda: clock[0])
    visitor, session = uuid4(), uuid4()
    first = event(visitor, session)
    assert site.record_event(first)
    assert not site.record_event(first)
    second = event(visitor, session); second['path'] = '/features'
    site.record_event(second)
    site.record_event(event(visitor, session, kind='download', platform='linux'))
    clock[0] += 86400
    site.record_event(event(visitor, uuid4()))
    site.record_event(event())
    data = site.report(30)
    assert data['totals'] == {'visits':3, 'pageviews':4, 'visitor_ids':2, 'download_clicks':1}
    assert data['period']['unique_browsers'] == 2
    assert data['period']['returning_visits'] == 1
    assert len(data['daily']) == 2  # No invented zero history before collection.
    assert data['breakdowns']['platforms'] == [{'label':'linux', 'count':1}]
    assert data['breakdowns']['device'] == [{'label':'Mobile', 'count':3}]
    assert str(visitor) not in json.dumps(data)
    assert 'secret-user-agent' not in json.dumps(data)
    clock[0] += 8*86400
    assert site.report(7)['period']['visits'] == 0
    assert site.report(7)['period']['unique_browsers'] == 0
    assert site.report(7)['totals']['visits'] == 3


def test_empty_reports_and_private_payloads(backend):
    data = site.report()
    assert data['started_at'] is None and data['daily'] == []
    assert all(value == 0 for value in data['period'].values())
    base = dict(consent=True, event_id=uuid4(), visitor_id=uuid4(), session_id=uuid4(), path='/')
    for change in ({'consent':False}, {'visitor_id':'user@example.com'}, {'extra':'private chat'}):
        with pytest.raises(ValidationError): site.SiteEvent(**{**base, **change})
    for path in ('/admin', '/api/admin/metrics', '/?token=private', '/unknown-private-path'):
        with pytest.raises(ValueError): site.sanitize(site.SiteEvent(**{**base, 'path':path}))


def test_api_requires_admin_and_limits_public_payloads(monkeypatch, tmp_path):
    monkeypatch.delenv('VERCEL', raising=False)
    monkeypatch.setenv('ZAYA_DATABASE_BACKEND', 'sqlite')
    monkeypatch.setenv('ZAYA_DB_PATH', str(tmp_path / 'analytics.db'))
    from fastapi.testclient import TestClient
    from web import server
    monkeypatch.setattr(server, 'is_admin_enabled', lambda: True)
    monkeypatch.setattr(server, 'validate_session', lambda token: token == 'test-owner-session')
    monkeypatch.setattr(site, 'is_rate_limited', lambda address: False)
    client = TestClient(server.app)
    assert client.get('/api/admin/site-analytics').status_code == 401
    assert client.get('/api/admin/metrics').status_code == 401
    assert client.get('/api/admin/site-analytics?days=30', headers={'Authorization':'Bearer test-owner-session'}).status_code == 200
    assert client.get('/api/admin/site-analytics?days=1000', headers={'Authorization':'Bearer test-owner-session'}).status_code == 422
    payload = site.SiteEvent(consent=True,event_id=uuid4(),visitor_id=uuid4(),session_id=uuid4(),path='/').model_dump(mode='json')
    assert client.post('/api/site-events',json=payload,headers={'Origin':'https://external.example'}).status_code == 403
    assert client.post('/api/site-events',content='x'*2049).status_code == 413
    assert client.post('/api/site-events',json=payload,headers={'DNT':'1'}).status_code == 204
    assert site.report()['totals']['pageviews'] == 0
    assert client.post('/api/site-events',json=payload).status_code == 204
    assert client.post('/api/site-events',json=payload).status_code == 204
    assert site.report()['totals']['pageviews'] == 1
    monkeypatch.setattr(site, 'is_rate_limited', lambda address: True)
    assert client.post('/api/site-events',json=payload).status_code == 429
