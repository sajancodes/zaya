"""Consent-only site aggregates; no IPs, URLs, user agents or browsing trails."""
from datetime import datetime, timedelta, timezone
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import time

from pydantic import BaseModel, ConfigDict, Field, UUID4
from typing import Literal


class SiteEvent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    consent: Literal[True]
    event_id: UUID4
    visitor_id: UUID4
    session_id: UUID4
    path: str = Field(max_length=120)
    kind: Literal['view', 'download'] = 'view'
    platform: Literal['windows', 'linux', 'android', 'none'] = 'none'
    source: Literal['direct', 'search', 'social', 'referral'] = 'direct'


@lru_cache(maxsize=1)
def public_paths():
    return frozenset(json.loads(Path(__file__).with_name('public_routes.json').read_text(encoding='utf-8')))


def sanitize(event, user_agent=''):
    if event.path not in public_paths() or event.path.startswith(('/admin', '/api')):
        raise ValueError('Only public page paths can be counted.')
    if event.kind == 'download' and event.platform == 'none':
        raise ValueError('Download platform required.')
    agent = user_agent[:1024].lower()
    browser = ('Edge' if 'edg' in agent else 'Firefox' if 'firefox' in agent
               else 'Chromium' if 'chrome' in agent or 'chromium' in agent
               else 'Safari' if 'safari' in agent else 'Other')
    operating_system = ('Android' if 'android' in agent else 'iOS' if 'iphone' in agent or 'ipad' in agent
                        else 'Windows' if 'windows' in agent else 'macOS' if 'macintosh' in agent
                        else 'Linux' if 'linux' in agent else 'Other')
    device = 'Tablet' if 'ipad' in agent or 'tablet' in agent else 'Mobile' if 'mobile' in agent or 'android' in agent else 'Desktop'
    return {**event.model_dump(mode='json'), 'browser': browser, 'os': operating_system, 'device': device}


def is_rate_limited(address):
    from web.database import firebase_enabled
    if firebase_enabled():
        from web.shared_limits import consume
        return consume(address, 'site-analytics', 60, 60)
    from web.telemetry_service import is_rate_limited as local_limit
    return local_limit('site:' + address)


def _increment(data, key):
    data[key] = int(data.get(key, 0)) + 1


def _aggregate(total, daily, event, new_visitor, new_session, new_daily_visitor, now):
    total.setdefault('started_at', now)
    if new_visitor:
        _increment(total, 'visitor_ids')
    if new_session:
        for data in (total, daily):
            _increment(data, 'visits')
            if not new_visitor:
                _increment(data, 'returning_visits')
        for category in ('source', 'browser', 'os', 'device'):
            _increment(daily.setdefault(category, {}), event[category])
    if new_daily_visitor:
        _increment(daily, 'unique_browsers')
    if event['kind'] == 'view':
        for data in (total, daily):
            _increment(data, 'pageviews')
        _increment(daily.setdefault('pages', {}), event['path'])
    else:
        for data in (total, daily):
            _increment(data, 'download_clicks')
        _increment(daily.setdefault('platforms', {}), event['platform'])


def record_event(event):
    from web.database import firebase_enabled
    now = int(time.time())
    day = datetime.fromtimestamp(now, timezone.utc).date().isoformat()
    if firebase_enabled():
        return _record_firestore(event, now, day)
    conn = _sqlite()
    try:
        with conn:
            conn.execute('BEGIN IMMEDIATE')
            if conn.execute('SELECT 1 FROM site_receipts WHERE id=?', (event['event_id'],)).fetchone():
                return False
            visitor = conn.execute('SELECT 1 FROM site_visitors WHERE id=?', (event['visitor_id'],)).fetchone()
            session = conn.execute('SELECT 1 FROM site_sessions WHERE id=?', (event['session_id'],)).fetchone()
            daily_visitor = conn.execute('SELECT 1 FROM site_daily_visitors WHERE id=?', (day + event['visitor_id'],)).fetchone()
            def load(key):
                row = conn.execute('SELECT payload FROM site_aggregates WHERE id=?', (key,)).fetchone()
                return json.loads(row[0]) if row else {}
            total, daily = load('total'), load(day)
            _aggregate(total, daily, event, not visitor, not session, not daily_visitor, now)
            for key, data in (('total', total), (day, daily)):
                conn.execute('INSERT OR REPLACE INTO site_aggregates VALUES (?,?)', (key, json.dumps(data)))
            for table, key, expiry in (('site_receipts', event['event_id'], now + 86400),
                                       ('site_visitors', event['visitor_id'], now + 90*86400),
                                       ('site_sessions', event['session_id'], now + 90*86400),
                                       ('site_daily_visitors', day + event['visitor_id'], now + 90*86400)):
                conn.execute(f'INSERT OR REPLACE INTO {table} VALUES (?,?,?)', (key, now, expiry))
                conn.execute(f'DELETE FROM {table} WHERE rowid IN (SELECT rowid FROM {table} WHERE expires_at<=? LIMIT 100)', (now,))
        return True
    finally:
        conn.close()


def _sqlite():
    from web.database import get_connection
    conn = get_connection()
    for table in ('site_receipts', 'site_visitors', 'site_sessions', 'site_daily_visitors'):
        conn.execute(f'CREATE TABLE IF NOT EXISTS {table} (id TEXT PRIMARY KEY, last_seen INTEGER, expires_at INTEGER)')
    conn.execute('CREATE TABLE IF NOT EXISTS site_aggregates (id TEXT PRIMARY KEY, payload TEXT NOT NULL)')
    conn.commit()
    return conn


def _record_firestore(event, now, day):
    from google.cloud import firestore
    from web.firebase_store import client, collection
    refs = [collection('site_receipts').document(event['event_id']),
            collection('site_visitors').document(event['visitor_id']),
            collection('site_sessions').document(event['session_id']),
            collection('site_daily_visitors').document(hashlib.sha256((day + event['visitor_id']).encode()).hexdigest()),
            collection('site_aggregates').document('total'), collection('site_days').document(day)]
    @firestore.transactional
    def record(transaction):
        receipt = refs[0].get(transaction=transaction)
        if receipt.exists:
            return False
        snapshots = [ref.get(transaction=transaction) for ref in refs[1:]]
        total, daily = snapshots[3].to_dict() or {}, snapshots[4].to_dict() or {}
        _aggregate(total, daily, event, not snapshots[0].exists, not snapshots[1].exists, not snapshots[2].exists, now)
        for index in range(4):
            transaction.set(refs[index], {'last_seen': now, 'expires_at': datetime.fromtimestamp(now, timezone.utc) + timedelta(days=1 if index == 0 else 90)})
        transaction.set(refs[4], total)
        transaction.set(refs[5], {**daily, 'day': day})
        return True
    return record(client().transaction())


def report(days=30):
    from web.database import firebase_enabled
    if days not in (7, 30, 90):
        raise ValueError('Unsupported report period.')
    now = int(time.time())
    today = datetime.fromtimestamp(now, timezone.utc).date()
    first = today - timedelta(days=days-1)
    cutoff = int(datetime.combine(first, datetime.min.time(), timezone.utc).timestamp())
    if firebase_enabled():
        from google.cloud.firestore_v1.base_query import FieldFilter
        from web.firebase_store import collection, count
        total = collection('site_aggregates').document('total').get().to_dict() or {}
        rows = {doc.id: doc.to_dict() for doc in collection('site_days').where(filter=FieldFilter('day', '>=', first.isoformat())).order_by('day').limit(days).stream()}
        unique = count(collection('site_visitors').where(filter=FieldFilter('last_seen', '>=', cutoff)))
    else:
        conn = _sqlite()
        try:
            rows = {row[0]: json.loads(row[1]) for row in conn.execute('SELECT id,payload FROM site_aggregates')}
            total = rows.pop('total', {})
            unique = conn.execute('SELECT COUNT(*) FROM site_visitors WHERE last_seen>=?', (cutoff,)).fetchone()[0]
        finally:
            conn.close()
    timeline, period, breakdowns = [], {key: 0 for key in ('visits', 'pageviews', 'download_clicks', 'returning_visits')}, {key: {} for key in ('pages', 'source', 'browser', 'os', 'device', 'platforms')}
    for offset in range(days):
        day = (first + timedelta(days=offset)).isoformat()
        if not total.get('started_at') or day < datetime.fromtimestamp(total['started_at'], timezone.utc).date().isoformat():
            continue
        data = rows.get(day, {})
        timeline.append({'day': day, **{key: data.get(key, 0) for key in ('visits', 'pageviews', 'unique_browsers', 'download_clicks')}})
        for key in ('visits', 'pageviews', 'download_clicks', 'returning_visits'):
            period[key] = period.get(key, 0) + data.get(key, 0)
        for key, values in breakdowns.items():
            for label, value in data.get(key, {}).items():
                values[label] = values.get(label, 0) + value
    period['unique_browsers'] = unique
    return {'days': days, 'started_at': total.get('started_at'), 'updated_at': now,
            'totals': {key: total.get(key, 0) for key in ('visits', 'pageviews', 'visitor_ids', 'download_clicks')},
            'period': period, 'daily': timeline,
            'breakdowns': {key: [{'label': label, 'count': count} for label, count in sorted(values.items(), key=lambda item: (-item[1], item[0]))] for key, values in breakdowns.items()},
            'definition': 'Consent-only estimates, not all visitors or people. Visits use a 30-minute browser session. Browser IDs rotate every 30 days. Download clicks do not prove completed downloads or installations. Admin pages, private content, full referrers and IP addresses are excluded. History starts when tracking is enabled; earlier traffic cannot be backfilled.'}
