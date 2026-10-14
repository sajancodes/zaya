"""Standalone Hermes hook. No imports from Zaya or access to privileged tools.

Offline events remain in a local SQLite outbox and are replayed on the next hook.
Hermes calls this synchronously/asynchronously according to its public hook API.
"""
import json
from pathlib import Path
import sqlite3
import time
import urllib.request
from urllib.parse import urlsplit


def handle(event_type: str, context: dict) -> None:
    if event_type != 'gateway:startup' and context.get('platform') != 'whatsapp':
        return
    folder = Path(__file__).resolve().parent
    allowed = {'platform', 'chat_id', 'user_id', 'thread_id', 'chat_type', 'session_id', 'message', 'response', 'timestamp', 'display_name'}
    payload = json.dumps({'event': event_type, 'context': {k: v for k, v in context.items() if k in allowed}}, ensure_ascii=False)
    if len(payload.encode('utf-8')) > 60000:
        return
    with sqlite3.connect(folder / 'zaya-hook-outbox.db', timeout=3) as db:
        db.execute('CREATE TABLE IF NOT EXISTS pending(id INTEGER PRIMARY KEY, payload TEXT, created REAL)')
        db.execute('INSERT INTO pending(payload,created) VALUES(?,?)', (payload, time.time()))
        db.execute('DELETE FROM pending WHERE created < ?', (time.time() - 7 * 86400,))
        db.commit()
        try:
            path = json.loads((folder / 'zaya-path.json').read_text(encoding='utf-8'))['descriptor']
            descriptor = json.loads(Path(path).read_text(encoding='utf-8'))
            url = urlsplit(descriptor['url'])
            if url.scheme != 'http' or url.hostname != '127.0.0.1' or url.path != '/events':
                return
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            for event_id, body in db.execute('SELECT id,payload FROM pending ORDER BY id LIMIT 100').fetchall():
                request = urllib.request.Request(descriptor['url'], data=body.encode('utf-8'), headers={
                    'Authorization': 'Bearer ' + descriptor['token'], 'Content-Type': 'application/json'})
                with opener.open(request, timeout=.75) as response:
                    if response.status != 204:
                        break
                db.execute('DELETE FROM pending WHERE id=?', (event_id,))
            db.commit()
        except (OSError, ValueError, KeyError):
            return  # durable outbox retains the event; never block Hermes while Zaya is offline
