"""Proof of shared limits, retry-safe counters and concurrent expiry refresh."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from types import SimpleNamespace

import pytest

firestore = pytest.importorskip('google.cloud.firestore')
from web import firebase_store, retention, shared_limits


class Snapshot:
    def __init__(self, reference, data):
        self.reference, self.data = reference, deepcopy(data)
        self.exists = data is not None

    def to_dict(self):
        return deepcopy(self.data)


class Reference:
    def __init__(self, database, name, key):
        self.database, self.name, self.key = database, name, key

    def get(self, transaction=None):
        return Snapshot(self, self.database.rows.get((self.name, self.key)))

    def set(self, data, merge=False):
        key = self.name, self.key
        result = deepcopy(self.database.rows.get(key, {})) if merge else {}
        for field, value in data.items():
            result[field] = result.get(field, 0) + value._value if isinstance(value, firestore.Increment) else value
        self.database.rows[key] = result


class Collection:
    def __init__(self, database, name, condition=None, size=100):
        self.database, self.name, self.condition, self.size = database, name, condition, size

    def document(self, key):
        return Reference(self.database, self.name, key)

    def where(self, *, filter):
        return Collection(self.database, self.name, filter, self.size)

    def limit(self, size):
        return Collection(self.database, self.name, self.condition, size)

    def stream(self):
        rows = [self.document(key).get() for (name, key), value in self.database.rows.items()
                if name == self.name and value.get(self.condition.field_path, datetime.max.replace(tzinfo=timezone.utc)) <= self.condition.value]
        # Simulate a heartbeat refreshing expiry after the query, before deletion.
        if self.database.on_query:
            self.database.on_query(self.name)
        return iter(rows[:self.size])


class Database:
    def __init__(self):
        self.rows = {}
        self.on_query = None

    def transaction(self):
        return SimpleNamespace(set=lambda ref, data, merge=False: ref.set(data, merge),
                               create=lambda ref, data: ref.set(data),
                               delete=lambda ref: self.rows.pop((ref.name, ref.key), None))


@pytest.fixture
def database(monkeypatch):
    database = Database()
    monkeypatch.setattr(firestore, 'transactional', lambda fn: fn)
    monkeypatch.setattr(firebase_store, 'client', lambda: database)
    monkeypatch.setattr(firebase_store, 'collection', lambda name: Collection(database, name))
    monkeypatch.setattr(retention, '_next_local_check', 0)
    monkeypatch.setenv('ZAYA_RATE_LIMIT_SECRET', 'test-key-material-with-at-least-32-characters')
    return database


def test_limits_survive_workers_and_rotate_without_addresses(database, monkeypatch):
    monkeypatch.setattr(retention, 'maybe_cleanup', lambda: None)
    monkeypatch.setattr(shared_limits.time, 'time', lambda: 120)
    assert [shared_limits.consume('192.0.2.10', 'test', 2, 60) for _ in range(3)] == [False, False, True]
    assert shared_limits.consume('192.0.2.10', 'another-scope', 2, 60) is False
    stored = [{'id': key[1], 'data': value} for key, value in database.rows.items()]
    assert '192.0.2.10' not in json.dumps(stored, default=str)
    first_key = shared_limits.bucket_id('192.0.2.10', 'test', 60, 120)
    assert first_key != shared_limits.bucket_id('192.0.2.10', 'test', 60, 180)
    monkeypatch.setattr(shared_limits.time, 'time', lambda: 180)
    assert shared_limits.consume('192.0.2.10', 'test', 2, 60) is False


def test_limit_outage_does_not_downgrade_to_memory(database, monkeypatch):
    def unavailable():
        raise RuntimeError('credential-should-never-be-shown')
    monkeypatch.setattr(firebase_store, 'client', unavailable)
    with pytest.raises(shared_limits.RateLimitUnavailable) as error:
        shared_limits.consume('test', 'test', 2, 60)
    assert 'credential-should-never-be-shown' not in str(error.value)


def test_registration_retry_and_heartbeat_do_not_double_count(database):
    assert firebase_store.record_install('first', 'windows', '0.5.0') is True
    assert firebase_store.record_install('first', 'windows', '0.5.0') is False
    assert firebase_store.record_heartbeat('first', 'windows', '0.5.1') is False
    assert firebase_store.record_install('second', 'android', '0.4.6') is True
    counters = [value for (name, _), value in database.rows.items() if name == 'daily_installs']
    assert counters == [{'total': 2, 'windows': 1, 'android': 1}]
    assert database.rows['installations', 'first']['installed_version'] == '0.5.0'
    assert database.rows['installations', 'first']['current_version'] == '0.5.1'


def test_cleanup_preserves_concurrently_refreshed_installation(database):
    now = datetime.now(timezone.utc)
    for name, key in [('installations', 'old'), ('installations', 'refreshed'), ('admin_sessions', 'expired'), ('request_limits', 'expired')]:
        database.rows[name, key] = {'expires_at': now - timedelta(days=1)}
    def refresh(name):
        if name == 'installations':
            database.rows['installations', 'refreshed']['expires_at'] = now + timedelta(days=90)
    database.on_query = refresh
    retention.maybe_cleanup()
    assert ('installations', 'refreshed') in database.rows
    assert ('installations', 'old') not in database.rows
    assert ('admin_sessions', 'expired') not in database.rows
    assert ('request_limits', 'expired') not in database.rows
    assert database.rows['maintenance', 'retention']['deleted'] == {'installations': 1, 'admin_sessions': 1, 'request_limits': 1}
