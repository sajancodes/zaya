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
        data = {'platform': platform, 'current_version': version, 'last_seen': now,
                'expires_at': datetime.now(timezone.utc) + timedelta(days=90)}
        if not existing.exists:
            data.update(first_seen=now, installed_version=version)
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
    distribution = {v: count(installs.where(filter=FieldFilter('current_version', '==', v))) for v in versions}
    daily = []
    for offset in range(13, -1, -1):
        day = datetime.now(timezone.utc).date() - timedelta(days=offset)
        item = collection('daily_downloads').document(day.isoformat()).get().to_dict() or {}
        daily.append({'day': day.isoformat(), 'count': item.get('total', 0)})
    return {'downloads': {k: downloads.get(k, 0) for k in ('total', *platforms)},
            'installations': totals, 'active': {'online_now': since('last_seen', 180),
            'last_24h': since('last_seen', 86400), 'last_7d': since('last_seen', 7*86400),
            'last_30d': since('last_seen', 30*86400)},
            'version_distribution': distribution, 'daily_installs': [], 'daily_downloads': daily,
            'updated_at': now, 'definitions': {'online_now': 'Opted-in installations seen within 3 minutes.',
            'installations': 'Retained anonymous installations, not people; expires after 90 inactive days.'}}


def store_session(token, username, expires):
    collection('admin_sessions').document(hashlib.sha256(token.encode()).hexdigest()).set({
        'username': username, 'expires_at': datetime.fromtimestamp(expires, timezone.utc)})


def validate_session(token):
    doc = collection('admin_sessions').document(hashlib.sha256(token.encode()).hexdigest()).get()
    return doc.exists and doc.to_dict()['expires_at'] > datetime.now(timezone.utc)


def revoke_session(token):
    collection('admin_sessions').document(hashlib.sha256(token.encode()).hexdigest()).delete()
