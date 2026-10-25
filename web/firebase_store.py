"""Server-only Firestore storage. No client access to analytics or sessions."""
from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import datetime, timedelta, timezone
from functools import lru_cache


@lru_cache(maxsize=1)
def client():
    import firebase_admin
    from firebase_admin import credentials, firestore
    try:
        app = firebase_admin.get_app('zaya-release')
    except ValueError:
        raw = os.environ.get('FIREBASE_SERVICE_ACCOUNT_JSON')
        credential = credentials.Certificate(json.loads(raw)) if raw else credentials.ApplicationDefault()
        app = firebase_admin.initialize_app(credential, {
            'projectId': os.environ.get('FIREBASE_PROJECT_ID')
        }, name='zaya-release')
    return firestore.client(app)


def collection(name):
    return client().collection('zaya_' + name)


def record_install(installation_id, platform, version):
    from google.cloud import firestore
    ref = collection('installations').document(installation_id)
    @firestore.transactional
    def update(transaction):
        existing = ref.get(transaction=transaction)
        now = int(time.time())
        day = datetime.fromtimestamp(now, timezone.utc).date().isoformat()
        new_day = (existing.to_dict() or {}).get('last_active_day') != day
        data = {'platform': platform, 'current_version': version, 'last_seen': now,
                'expires_at': datetime.now(timezone.utc) + timedelta(days=90), 'last_active_day': day}
        if not existing.exists:
            data.update(first_seen=now, installed_version=version)
            aggregation = collection('maintenance').document('install_aggregation')
            if not aggregation.get(transaction=transaction).exists:
                transaction.create(aggregation, {'started_at': now})
            # A retried request or duplicate heartbeat cannot count a second install.
            day = datetime.fromtimestamp(now, timezone.utc).date().isoformat()
            transaction.set(collection('daily_installs').document(day), {
                'total': firestore.Increment(1), platform: firestore.Increment(1)}, merge=True)
        if new_day:
            transaction.set(collection('daily_actives').document(day), {
                'day': day, 'total': firestore.Increment(1), platform: firestore.Increment(1)}, merge=True)
        transaction.set(ref, data, merge=True)
        return not existing.exists
    return update(client().transaction())


def record_heartbeat(installation_id, platform, version):
    return record_install(installation_id, platform, version)


def record_download(platform, version, client_ip=None):
    from google.cloud import firestore
    now = datetime.now(timezone.utc)
    # Persist aggregate counts only, never addresses, user agents or referrers.
    batch = client().batch()
    for ref in (collection('counters').document('downloads'),
                collection('daily_downloads').document(now.strftime('%Y-%m-%d'))):
        batch.set(ref, {'total': firestore.Increment(1), platform: firestore.Increment(1)}, merge=True)
    batch.commit()


def record_update_event(event_id, platform, target_version, stage):
    from google.cloud import firestore
    now = datetime.now(timezone.utc)
    day = now.date().isoformat()
    # Event receipts store expiry only, with no installation UUID or other content.
    receipt = collection('update_receipts').document(hashlib.sha256(event_id.encode()).hexdigest())
    totals = collection('daily_updates').document(f'{day}:{platform}:{target_version or "unknown"}')
    @firestore.transactional
    def record(transaction):
        if receipt.get(transaction=transaction).exists:
            return False
        transaction.create(receipt, {'expires_at': now + timedelta(days=1)})
        transaction.set(totals, {'day':day, 'platform':platform, 'target_version':target_version,
                               stage:firestore.Increment(1)}, merge=True)
        return True
    return record(client().transaction())


def get_all_releases(db_path=None):
    return [doc.to_dict() for doc in collection('releases').order_by('published_at', direction='DESCENDING').limit(200).stream()]


def get_latest_release(platform='windows', db_path=None, channel='stable'):
    # Bounded catalog avoids composite index requirements. Versions are immutable.
    rows = [r for r in get_all_releases() if r.get('platform') == platform
            and r.get('channel', 'stable') == channel and r.get('active', True)]
    return max(rows, key=lambda r: r.get('published_at', 0), default=None)


def upsert_release(version, platform, filename, url, sha256, size, release_notes='', published_at=None, db_path=None, channel='stable', build=0):
    from web.release_validation import validate_release
    data = dict(version=version, platform=platform, filename=filename, url=url,
                sha256=sha256, size=int(size), release_notes=release_notes,
                published_at=published_at or int(time.time()), channel=channel, build=int(build))
    validate_release(data)
    key = hashlib.sha256(f'{version}:{platform}'.encode()).hexdigest()
    ref = collection('releases').document(key)
    from google.cloud import firestore
    @firestore.transactional
    def store(transaction):
        previous = ref.get(transaction=transaction)
        if previous.exists:
            old = previous.to_dict()
            if any(old.get(k) != data[k] for k in ('sha256', 'url', 'size', 'filename')):
                raise ValueError('Published release artifacts are immutable. Use a new version.')
            return  # Preserve an administrator kill switch across metadata sync.
        transaction.create(ref, {**data, 'active': True})
    store(client().transaction())


def set_release_active(version, platform, active):
    key = hashlib.sha256(f'{version}:{platform}'.encode()).hexdigest()
    collection('releases').document(key).update({'active': bool(active)})


def count(query):
    return query.count().get()[0][0].value


def get_analytics_metrics():
    from google.cloud.firestore_v1.base_query import FieldFilter
    now = int(time.time())
    installs = collection('installations')
    def since(field, seconds):
        return count(installs.where(filter=FieldFilter(field, '>=', now - seconds)))
    platforms = ('windows', 'linux', 'android')
    totals = {'total': count(installs), **{p: count(installs.where(filter=FieldFilter('platform', '==', p))) for p in platforms}}
    downloads = collection('counters').document('downloads').get().to_dict() or {}
    releases = get_all_releases()
    versions = {r['version'] for r in releases}
    # Manual beta packages intentionally stay outside the automatic-update catalog.
    import json
    from pathlib import Path
    for name in ('windowsBeta.json', 'linuxBeta.json'):
        beta = json.loads((Path(__file__).parent / 'src/data' / name).read_text(encoding='utf-8'))
        if beta.get('published'):
            versions.add(beta['version'])
    distribution = {v: count(installs.where(filter=FieldFilter('current_version', '==', v))) for v in versions}
    daily = []
    daily_installs = []
    aggregation = collection('maintenance').document('install_aggregation').get().to_dict() or {}
    started = aggregation.get('started_at')
    start_day = datetime.fromtimestamp(started, timezone.utc).date() if started else None
    for offset in range(13, -1, -1):
        day = datetime.now(timezone.utc).date() - timedelta(days=offset)
        item = collection('daily_downloads').document(day.isoformat()).get().to_dict() or {}
        daily.append({'day': day.isoformat(), 'count': item.get('total', 0)})
        if start_day is not None and day >= start_day:
            installs_day = collection('daily_installs').document(day.isoformat()).get().to_dict() or {}
            daily_installs.append({'day': day.isoformat(), 'count': installs_day.get('total', 0)})
    maintenance = collection('maintenance').document('retention').get().to_dict() or {}
    last_cleanup = maintenance.get('last_completed')
    recent_updates = [doc.to_dict() for doc in collection('daily_updates').where(filter=FieldFilter('day', '>=', (datetime.now(timezone.utc).date() - timedelta(days=13)).isoformat())).order_by('day', direction='DESCENDING').limit(100).stream()]
    daily_actives = [doc.to_dict() for doc in collection('daily_actives').order_by('day', direction='DESCENDING').limit(14).stream()]
    return {'daily_actives': [{'day': item['day'], 'count': item['total']} for item in reversed(daily_actives)], 'update_health':recent_updates, 'update_health_definition':'Opt-in reports only. Installer started means process launch, not completed installation. Version adoption comes from later heartbeats.',
            'retention': {'mode': 'traffic-driven', 'last_completed': int(last_cleanup.timestamp()) if last_cleanup else None,
                          'last_deleted': maintenance.get('deleted', {}),
                          'limitation': 'Runs on protected request traffic; idle deployments require a scheduled caller. Up to 100 expired records per collection per pass.'},
            'downloads': {k: downloads.get(k, 0) for k in ('total', *platforms)},
            'installations': totals, 'active': {'online_now': since('last_seen', 180),
            'last_24h': since('last_seen', 86400), 'last_7d': since('last_seen', 7*86400),
            'last_30d': since('last_seen', 30*86400)},
            'version_distribution': distribution, 'daily_installs': daily_installs, 'daily_downloads': daily, 'daily_installs_since': started,
            'updated_at': now, 'definitions': {'online_now': 'Opted-in installations seen within 3 minutes.',
            'installations': 'Retained anonymous installations, not people. Expiry cleanup targets 90 inactive days and runs in bounded passes on request traffic.',
            'daily_installs': 'Anonymous IDs first registered or re-registered after retention expiry per UTC day. History begins when aggregation is enabled.'}}


def store_session(token, username, expires):
    collection('admin_sessions').document(hashlib.sha256(token.encode()).hexdigest()).set({
        'username': username, 'expires_at': datetime.fromtimestamp(expires, timezone.utc)})


def validate_session(token):
    doc = collection('admin_sessions').document(hashlib.sha256(token.encode()).hexdigest()).get()
    return doc.exists and doc.to_dict()['expires_at'] > datetime.now(timezone.utc)


def revoke_session(token):
    collection('admin_sessions').document(hashlib.sha256(token.encode()).hexdigest()).delete()
