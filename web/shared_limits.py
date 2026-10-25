"""Atomic Firestore request limits without storing addresses or stable IP hashes."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
import time


class RateLimitUnavailable(RuntimeError):
    pass


def bucket_id(subject: str, scope: str, window: int, now: int) -> str:
    secret = os.environ.get('ZAYA_RATE_LIMIT_SECRET', '')
    if not secret:
        try:
            credential = json.loads(os.environ.get('FIREBASE_SERVICE_ACCOUNT_JSON', '{}'))
            secret = credential.get('private_key', '') if isinstance(credential, dict) else ''
        except (ValueError, TypeError):
            secret = ''
    if not isinstance(secret, str) or len(secret) < 32:
        raise RateLimitUnavailable('Shared request protection is not configured')
    # The identifier changes every window; no raw or stable address is persisted.
    message = f'{scope}:{now // window}:{subject}'.encode()
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


def consume(subject: str, scope: str, limit: int, window: int) -> bool:
    """Return True once the shared fixed-window quota has already been consumed."""
    from google.cloud import firestore
    from web.firebase_store import client, collection
    now = int(time.time())
    key = bucket_id(subject or 'unknown', scope, window, now)
    ref = collection('request_limits').document(key)

    @firestore.transactional
    def reserve(transaction):
        snapshot = ref.get(transaction=transaction)
        count = int((snapshot.to_dict() or {}).get('count', 0)) if snapshot.exists else 0
        if count >= limit:
            return True
        transaction.set(ref, {'count': count + 1,
                             'expires_at': datetime.fromtimestamp((now // window + 2) * window, timezone.utc)})
        return False
    try:
        limited = reserve(client().transaction())
    except Exception:
        # Never silently downgrade production to process-local limits.
        raise RateLimitUnavailable('Shared request protection is temporarily unavailable') from None
    from web.retention import maybe_cleanup
    maybe_cleanup()
    return limited
