"""Bounded, traffic-driven expiry cleanup for the no-cost Firestore backend."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
import threading
import time

_lock = threading.Lock()
_next_local_check = 0.0
COLLECTIONS = ('installations', 'admin_sessions', 'request_limits', 'update_receipts')


def maybe_cleanup():
    """At most one worker claims a cleanup pass every ten minutes.

    Each pass deletes at most 100 expired records per collection. Read each
    candidate again transactionally so a concurrent heartbeat cannot be lost.
    Idle deployments need a scheduled caller for time-based enforcement.
    """
    global _next_local_check
    with _lock:
        if time.monotonic() < _next_local_check:
            return
        _next_local_check = time.monotonic() + 600
    try:
        from google.cloud import firestore
        from google.cloud.firestore_v1.base_query import FieldFilter
        from web.firebase_store import client, collection
        db = client()
        control = collection('maintenance').document('retention')
        now = datetime.now(timezone.utc)

        @firestore.transactional
        def claim(transaction):
            previous = control.get(transaction=transaction)
            data = previous.to_dict() or {} if previous.exists else {}
            if data.get('next_run', now) > now:
                return False
            transaction.set(control, {'next_run': now + timedelta(minutes=10)}, merge=True)
            return True
        if not claim(db.transaction()):
            return
        deleted = {}
        for name in COLLECTIONS:
            candidates = list(collection(name).where(filter=FieldFilter('expires_at', '<=', now)).limit(100).stream())

            @firestore.transactional
            def remove(transaction):
                snapshots = [doc.reference.get(transaction=transaction) for doc in candidates]
                expired = [doc for doc in snapshots if doc.exists and (doc.to_dict() or {}).get('expires_at', now + timedelta(days=1)) <= now]
                for doc in expired:
                    transaction.delete(doc.reference)
                return len(expired)
            deleted[name] = remove(db.transaction()) if candidates else 0
        control.set({'last_completed': now, 'deleted': deleted}, merge=True)
    except Exception:
        # Do not expose record IDs, credentials, SDK payloads or private data.
        logging.getLogger('zaya-web').warning('Expiry cleanup did not complete; a later request will retry.')
