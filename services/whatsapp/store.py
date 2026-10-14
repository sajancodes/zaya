"""Transactional inbox, unread counts, alerts and transport idempotency."""
from __future__ import annotations
from dataclasses import asdict
import json
import sqlite3
import threading
import time
from pathlib import Path
from services.whatsapp.models import Message, validate_chat_id

MODES = {'observe', 'draft', 'auto', 'manual', 'paused'}


class WhatsAppStore:
    def __init__(self, path: Path | str = ':memory:') -> None:
        if str(path) != ':memory:':
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(str(path), check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA busy_timeout=5000')
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS wa_contacts (
          contact_id TEXT PRIMARY KEY, display_name TEXT, aliases_json TEXT DEFAULT '[]',
          priority INTEGER DEFAULT 0, notes TEXT DEFAULT '', first_seen_at REAL, last_seen_at REAL);
        CREATE TABLE IF NOT EXISTS wa_chats (
          chat_id TEXT PRIMARY KEY, title TEXT, chat_type TEXT DEFAULT 'dm', mode TEXT DEFAULT 'observe',
          ai_active INTEGER DEFAULT 0, started_at REAL, paused_at REAL, last_message_at REAL,
          unread_count INTEGER DEFAULT 0, last_manual_owner_message_at REAL, last_ai_message_at REAL);
        CREATE TABLE IF NOT EXISTS wa_messages (
          message_id TEXT PRIMARY KEY, chat_id TEXT NOT NULL, sender_id TEXT, direction TEXT,
          source TEXT, text TEXT, timestamp REAL, received_at REAL, handled INTEGER DEFAULT 0,
          reply_to_id TEXT, ai_generated INTEGER DEFAULT 0, transport_status TEXT,
          complete INTEGER DEFAULT 1, draft TEXT);
        CREATE INDEX IF NOT EXISTS wa_message_chat_time ON wa_messages(chat_id, timestamp);
        CREATE TABLE IF NOT EXISTS wa_alerts (
          alert_id TEXT PRIMARY KEY, chat_id TEXT, message_id TEXT UNIQUE, score INTEGER,
          category TEXT, reason TEXT, created_at REAL, delivered_at REAL, acknowledged_at REAL);
        CREATE TABLE IF NOT EXISTS wa_send_intents (
          request_id TEXT PRIMARY KEY, chat_id TEXT, text TEXT, status TEXT,
          message_id TEXT, detail TEXT, created_at REAL);
        CREATE TABLE IF NOT EXISTS wa_settings (key TEXT PRIMARY KEY, value TEXT);
        ''')
        self.db.commit()

    def rows(self, query: str, values: tuple = ()) -> list[dict]:
        with self.lock:
            return [dict(row) for row in self.db.execute(query, values).fetchall()]

    def chat(self, chat_id: str) -> dict:
        validate_chat_id(chat_id)
        rows = self.rows('SELECT * FROM wa_chats WHERE chat_id=?', (chat_id,))
        if not rows:
            raise ValueError('Chat has not been observed. Supply an exact observed chat ID.')
        return rows[0]

    def ingest(self, message: Message) -> bool:
        m = asdict(message)
        with self.lock, self.db:
            if self.db.execute('SELECT 1 FROM wa_messages WHERE message_id=?', (message.message_id,)).fetchone():
                return False
            self.db.execute('INSERT OR IGNORE INTO wa_contacts(contact_id,display_name,first_seen_at,last_seen_at) VALUES(?,?,?,?)',
                            (message.sender_id, message.display_name or message.sender_id, message.timestamp, message.timestamp))
            self.db.execute('UPDATE wa_contacts SET last_seen_at=? WHERE contact_id=?', (message.timestamp, message.sender_id))
            self.db.execute('INSERT OR IGNORE INTO wa_chats(chat_id,title,chat_type) VALUES(?,?,?)',
                            (message.chat_id, message.display_name or message.chat_id, 'group' if message.chat_id.endswith('@g.us') else 'dm'))
            fields = ['message_id', 'chat_id', 'sender_id', 'direction', 'source', 'text', 'timestamp', 'reply_to_id', 'ai_generated', 'transport_status', 'complete']
            self.db.execute(f'INSERT INTO wa_messages ({",".join(fields)},received_at) VALUES ({",".join("?" for _ in fields)},?)',
                            (*[m[k] for k in fields], time.time()))
            self.db.execute('UPDATE wa_chats SET last_message_at=MAX(COALESCE(last_message_at,0),?), unread_count=unread_count+? WHERE chat_id=?',
                            (message.timestamp, int(message.direction == 'incoming'), message.chat_id))
            if message.direction == 'outgoing':
                if message.ai_generated:
                    self.db.execute('UPDATE wa_chats SET last_ai_message_at=? WHERE chat_id=?', (message.timestamp, message.chat_id))
                else:
                    self.db.execute("UPDATE wa_chats SET mode='manual',ai_active=0,last_manual_owner_message_at=? WHERE chat_id=?", (message.timestamp, message.chat_id))
            return True

    def set_mode(self, chat_id: str, mode: str) -> dict:
        if mode not in MODES:
            raise ValueError('Invalid chat mode.')
        self.chat(chat_id)
        with self.lock, self.db:
            self.db.execute('UPDATE wa_chats SET mode=?,ai_active=?,started_at=?,paused_at=? WHERE chat_id=?',
                            (mode, int(mode == 'auto'), time.time() if mode == 'auto' else None,
                             time.time() if mode in {'manual', 'paused'} else None, chat_id))
        return self.chat(chat_id)

    def conversation(self, chat_id: str, limit: int = 20) -> list[dict]:
        validate_chat_id(chat_id)
        return self.rows('SELECT * FROM wa_messages WHERE chat_id=? ORDER BY timestamp DESC LIMIT ?', (chat_id, max(1, min(limit, 100))))

    def mark_read(self, chat_id: str) -> None:
        self.chat(chat_id)
        with self.lock, self.db:
            self.db.execute('UPDATE wa_chats SET unread_count=0 WHERE chat_id=?', (chat_id,))

    def claim_message(self, message_id: str) -> bool:
        with self.lock, self.db:
            return self.db.execute('UPDATE wa_messages SET handled=1 WHERE message_id=? AND handled=0', (message_id,)).rowcount == 1

    def save_draft(self, message_id: str, text: str) -> None:
        with self.lock, self.db:
            self.db.execute('UPDATE wa_messages SET draft=? WHERE message_id=?', (text, message_id))

    def alert(self, message: Message, score: int, category: str, reason: str) -> bool:
        with self.lock, self.db:
            cursor = self.db.execute('INSERT OR IGNORE INTO wa_alerts(alert_id,chat_id,message_id,score,category,reason,created_at) VALUES(?,?,?,?,?,?,?)',
                                     ('alert-' + message.message_id, message.chat_id, message.message_id, score, category, reason, time.time()))
            return cursor.rowcount == 1

    def reserve_send(self, request_id: str, chat_id: str, text: str) -> bool:
        with self.lock, self.db:
            return self.db.execute("INSERT OR IGNORE INTO wa_send_intents VALUES(?,?,?,'pending',NULL,NULL,?)", (request_id, chat_id, text, time.time())).rowcount == 1

    def finish_send(self, request_id: str, status: str, message_id: str | None, detail: str) -> None:
        with self.lock, self.db:
            self.db.execute('UPDATE wa_send_intents SET status=?,message_id=?,detail=? WHERE request_id=?', (status, message_id, detail, request_id))
