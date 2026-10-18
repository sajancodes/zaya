"""Transactional inbox, unread counts, alerts and transport idempotency."""
from __future__ import annotations
from dataclasses import asdict, replace
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
        CREATE TABLE IF NOT EXISTS wa_chat_aliases (alias TEXT PRIMARY KEY, chat_id TEXT NOT NULL);
        ''')
        for table, column, declaration in [('wa_contacts', 'name_verified', 'INTEGER DEFAULT 0'),
                                            ('wa_messages', 'notified_at', 'REAL'),
                                            ('wa_alerts', 'notify_owner', 'INTEGER DEFAULT 0')]:
            if column not in {row[1] for row in self.db.execute(f'PRAGMA table_info({table})')}:
                self.db.execute(f'ALTER TABLE {table} ADD COLUMN {column} {declaration}')
        self.db.commit()

    def canonical_chat(self, chat_id: str) -> str:
        validate_chat_id(chat_id)
        rows = self.rows('SELECT chat_id FROM wa_chat_aliases WHERE alias=?', (chat_id,))
        return rows[0]['chat_id'] if rows else chat_id

    def link_alias(self, alias: str, chat_id: str) -> None:
        """Unify only identities established by the native WhatsApp event."""
        validate_chat_id(alias)
        chat_id = self.canonical_chat(chat_id)
        if alias == chat_id:
            return
        with self.lock, self.db:
            old = self.db.execute('SELECT * FROM wa_chats WHERE chat_id=?', (alias,)).fetchone()
            target = self.db.execute('SELECT * FROM wa_chats WHERE chat_id=?', (chat_id,)).fetchone()
            if old:
                if not target:
                    self.db.execute('UPDATE wa_chats SET chat_id=? WHERE chat_id=?', (chat_id, alias))
                else:
                    self.db.execute('UPDATE wa_chats SET unread_count=unread_count+?,last_message_at=MAX(COALESCE(last_message_at,0),?),last_manual_owner_message_at=MAX(COALESCE(last_manual_owner_message_at,0),?) WHERE chat_id=?',
                                    (old['unread_count'], old['last_message_at'] or 0, old['last_manual_owner_message_at'] or 0, chat_id))
                    # An owner takeover on either identity must still stop auto mode.
                    if old['mode'] in {'manual', 'paused'}:
                        self.db.execute('UPDATE wa_chats SET mode=?,ai_active=0 WHERE chat_id=?', (old['mode'], chat_id))
                    self.db.execute('DELETE FROM wa_chats WHERE chat_id=?', (alias,))
            for table in ('wa_messages', 'wa_alerts', 'wa_send_intents'):
                self.db.execute(f'UPDATE {table} SET chat_id=? WHERE chat_id=?', (chat_id, alias))
            self.db.execute('UPDATE wa_chat_aliases SET chat_id=? WHERE chat_id=?', (chat_id, alias))
            self.db.execute('INSERT OR REPLACE INTO wa_chat_aliases VALUES(?,?)', (alias, chat_id))

    def identify_contact(self, chat_id: str, name: str) -> dict:
        chat_id = self.canonical_chat(chat_id)
        self.chat(chat_id)
        name = name.strip()
        if not name or len(name) > 100:
            raise ValueError('Supply a contact name of 1 to 100 characters.')
        with self.lock, self.db:
            self.db.execute('INSERT INTO wa_contacts(contact_id,display_name,name_verified) VALUES(?,?,1) ON CONFLICT(contact_id) DO UPDATE SET display_name=excluded.display_name,name_verified=1', (chat_id, name))
            self.db.execute('UPDATE wa_chats SET title=? WHERE chat_id=?', (name, chat_id))
        return self.chat(chat_id)

    def rows(self, query: str, values: tuple = ()) -> list[dict]:
        with self.lock:
            return [dict(row) for row in self.db.execute(query, values).fetchall()]

    def chat(self, chat_id: str) -> dict:
        chat_id = self.canonical_chat(chat_id)
        rows = self.rows('SELECT * FROM wa_chats WHERE chat_id=?', (chat_id,))
        if not rows:
            raise ValueError('Chat has not been observed. Supply an exact observed chat ID.')
        return rows[0]

    def ingest(self, message: Message) -> bool:
        for alias in message.chat_aliases:
            self.link_alias(alias, message.chat_id)
        message = replace(message, chat_id=self.canonical_chat(message.chat_id))
        m = asdict(message)
        with self.lock, self.db:
            if self.db.execute('SELECT 1 FROM wa_messages WHERE message_id=?', (message.message_id,)).fetchone():
                return False
            self.db.execute('INSERT OR IGNORE INTO wa_contacts(contact_id,display_name,first_seen_at,last_seen_at) VALUES(?,?,?,?)',
                            (message.sender_id, message.display_name if message.direction == 'incoming' else message.sender_id, message.timestamp, message.timestamp))
            self.db.execute('UPDATE wa_contacts SET last_seen_at=? WHERE contact_id=?', (message.timestamp, message.sender_id))
            group = message.chat_id.endswith('@g.us')
            mode = 'auto' if not group and self.global_mode() == 'auto' else 'observe'
            self.db.execute('INSERT OR IGNORE INTO wa_chats(chat_id,title,chat_type,mode,ai_active) VALUES(?,?,?,?,?)',
                            (message.chat_id, (message.display_name if message.direction == 'incoming' else '') or message.chat_id,
                             'group' if group else 'dm', mode, int(mode == 'auto')))
            if message.direction == 'incoming' and message.display_name:
                contact = self.db.execute('SELECT display_name,name_verified FROM wa_contacts WHERE contact_id=?', (message.chat_id,)).fetchone()
                title = contact['display_name'] if contact and contact['name_verified'] else message.display_name
                if not message.chat_id.endswith('@g.us'):
                    self.db.execute('UPDATE wa_chats SET title=? WHERE chat_id=?', (title, message.chat_id))
                self.db.execute('UPDATE wa_contacts SET display_name=? WHERE contact_id=? AND name_verified=0', (message.display_name, message.sender_id))
            fields = ['message_id', 'chat_id', 'sender_id', 'direction', 'source', 'text', 'timestamp', 'reply_to_id', 'ai_generated', 'transport_status', 'complete']
            self.db.execute(f'INSERT INTO wa_messages ({",".join(fields)},received_at) VALUES ({",".join("?" for _ in fields)},?)',
                            (*[m[k] for k in fields], time.time()))
            self.db.execute('UPDATE wa_chats SET last_message_at=MAX(COALESCE(last_message_at,0),?), unread_count=unread_count+? WHERE chat_id=?',
                            (message.timestamp, int(message.direction == 'incoming'), message.chat_id))
            if message.direction == 'incoming':
                self.db.execute("UPDATE wa_messages SET notified_at=? WHERE message_id=? AND EXISTS(SELECT 1 FROM wa_chats WHERE chat_id=? AND mode='auto')",
                                (time.time(), message.message_id, message.chat_id))
            if message.direction == 'outgoing':
                if message.ai_generated:
                    self.db.execute('UPDATE wa_chats SET last_ai_message_at=? WHERE chat_id=?', (message.timestamp, message.chat_id))
                else:
                    self.db.execute("UPDATE wa_chats SET mode='manual',ai_active=0,last_manual_owner_message_at=? WHERE chat_id=?", (message.timestamp, message.chat_id))
            return True

    def set_mode(self, chat_id: str, mode: str) -> dict:
        chat_id = self.canonical_chat(chat_id)
        if mode not in MODES:
            raise ValueError('Invalid chat mode.')
        self.chat(chat_id)
        with self.lock, self.db:
            self.db.execute('UPDATE wa_chats SET mode=?,ai_active=?,started_at=?,paused_at=? WHERE chat_id=?',
                            (mode, int(mode == 'auto'), time.time() if mode == 'auto' else None,
                             time.time() if mode in {'manual', 'paused'} else None, chat_id))
            if mode == 'auto':
                self.db.execute('UPDATE wa_messages SET notified_at=? WHERE chat_id=? AND notified_at IS NULL', (time.time(), chat_id))
        return self.chat(chat_id)

    def global_mode(self) -> str:
        rows = self.rows('SELECT value FROM wa_settings WHERE key=?', ('default_dm_mode',))
        return rows[0]['value'] if rows else 'observe'

    def set_global_mode(self, mode: str) -> dict:
        """Fresh owner delegation for direct chats; never replay old messages.

        An owner message still takes over its chat. Explicitly paused chats and
        groups keep their own modes. Future direct chats inherit this setting.
        """
        if mode not in {'auto', 'observe'}:
            raise ValueError('Global WhatsApp mode must be auto or observe.')
        with self.lock, self.db:
            self.db.execute('INSERT OR REPLACE INTO wa_settings VALUES(?,?)', ('default_dm_mode', mode))
            if mode == 'auto':
                changed = self.db.execute("UPDATE wa_chats SET mode='auto',ai_active=1,started_at=? WHERE chat_type='dm' AND mode!='paused'", (time.time(),)).rowcount
                # Auto mode starts with the next incoming message. Old pending
                # previews must not all be read aloud when auto is later stopped.
                self.db.execute("UPDATE wa_messages SET notified_at=? WHERE notified_at IS NULL AND chat_id IN (SELECT chat_id FROM wa_chats WHERE chat_type='dm' AND mode='auto')", (time.time(),))
            else:
                changed = self.db.execute("UPDATE wa_chats SET mode='observe',ai_active=0 WHERE chat_type='dm' AND mode='auto'").rowcount
        return {'scope': 'direct_chats', 'mode': mode, 'updated_chats': changed,
                'group_chats_included': False, 'replays_history': False}

    def conversation(self, chat_id: str, limit: int = 20) -> list[dict]:
        chat_id = self.canonical_chat(chat_id)
        return self.rows('SELECT * FROM wa_messages WHERE chat_id=? ORDER BY timestamp DESC, rowid DESC LIMIT ?', (chat_id, max(1, min(limit, 100))))

    def mark_read(self, chat_id: str) -> None:
        chat_id = self.canonical_chat(chat_id)
        self.chat(chat_id)
        with self.lock, self.db:
            self.db.execute('UPDATE wa_chats SET unread_count=0 WHERE chat_id=?', (chat_id,))

    def claim_message(self, message_id: str) -> bool:
        with self.lock, self.db:
            return self.db.execute('UPDATE wa_messages SET handled=1 WHERE message_id=? AND handled=0', (message_id,)).rowcount == 1

    def save_draft(self, message_id: str, text: str) -> None:
        with self.lock, self.db:
            self.db.execute('UPDATE wa_messages SET draft=? WHERE message_id=?', (text, message_id))

    def alert(self, message: Message, score: int, category: str, reason: str, notify_owner: bool = False) -> bool:
        with self.lock, self.db:
            cursor = self.db.execute('INSERT OR IGNORE INTO wa_alerts(alert_id,chat_id,message_id,score,category,reason,created_at,notify_owner) VALUES(?,?,?,?,?,?,?,?)',
                                     ('alert-' + message.message_id, message.chat_id, message.message_id, score, category, reason, time.time(), int(notify_owner)))
            return cursor.rowcount == 1

    def reserve_send(self, request_id: str, chat_id: str, text: str) -> bool:
        with self.lock, self.db:
            return self.db.execute("INSERT OR IGNORE INTO wa_send_intents VALUES(?,?,?,'pending',NULL,NULL,?)", (request_id, chat_id, text, time.time())).rowcount == 1

    def finish_send(self, request_id: str, status: str, message_id: str | None, detail: str) -> None:
        with self.lock, self.db:
            self.db.execute('UPDATE wa_send_intents SET status=?,message_id=?,detail=? WHERE request_id=?', (status, message_id, detail, request_id))
