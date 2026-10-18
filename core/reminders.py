"""Durable reminders and verified delivery submissions, owned by Zaya."""
from datetime import datetime
import json
from pathlib import Path
import platform
import shutil
import sqlite3
import subprocess
import threading
import time
import uuid

DB_PATH = Path(__file__).resolve().parent.parent / 'memory' / 'reminders.db'


class ReminderStore:
    def __init__(self, path=DB_PATH, *, clock=time.time):
        self.path, self.clock = Path(path), clock
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(str(self.path), check_same_thread=False, timeout=10)
        self.db.row_factory = sqlite3.Row
        with self.db:
            self.db.execute('PRAGMA journal_mode=WAL')
            self.db.execute('''CREATE TABLE IF NOT EXISTS reminders (
                id TEXT PRIMARY KEY, message TEXT NOT NULL, due_at REAL NOT NULL,
                created_at REAL NOT NULL, cancelled_at REAL, voice_queued_at REAL,
                desktop_notified_at REAL, scheduler_id TEXT, error TEXT NOT NULL DEFAULT '',
                voice_retry_at REAL NOT NULL DEFAULT 0)''')

    def close(self):
        self.db.close()

    def create(self, message, due_at):
        rid = uuid.uuid4().hex
        with self.lock, self.db:
            self.db.execute('INSERT INTO reminders(id,message,due_at,created_at) VALUES(?,?,?,?)',
                            (rid, message, due_at, self.clock()))
        return self.get(rid)

    def get(self, rid):
        with self.lock:
            row = self.db.execute('SELECT * FROM reminders WHERE id=?', (rid,)).fetchone()
        if row is None:
            raise ValueError('That reminder was not found.')
        return self._public(row)

    def _public(self, row):
        result = dict(row)
        result['due_local'] = datetime.fromtimestamp(result['due_at']).astimezone().isoformat()
        result['state'] = ('cancelled' if result['cancelled_at'] is not None else
                           'voice_queued' if result['voice_queued_at'] is not None else
                           'desktop_notified' if result['desktop_notified_at'] is not None else
                           'due' if result['due_at'] <= self.clock() else 'scheduled')
        return result

    def list(self, limit=10):
        with self.lock:
            rows = self.db.execute('SELECT * FROM reminders ORDER BY created_at DESC LIMIT ?', (min(max(int(limit), 1), 50),)).fetchall()
        return [self._public(row) for row in rows]

    def next_due(self):
        with self.lock:
            row = self.db.execute('''SELECT * FROM reminders WHERE due_at<=? AND cancelled_at IS NULL
                AND voice_queued_at IS NULL AND voice_retry_at<=? ORDER BY due_at,created_at LIMIT 1''',
                                  (self.clock(), self.clock())).fetchone()
        if row is None:
            return None
        item = self._public(row)
        item['summary'] = ('Sir, an overdue reminder: ' if self.clock() - item['due_at'] > 60 else
                           'Sir, your reminder: ') + item['message']
        return item

    def update(self, rid, **values):
        if not values or set(values) - {'scheduler_id', 'error', 'cancelled_at', 'voice_queued_at', 'desktop_notified_at', 'voice_retry_at'}:
            raise ValueError('Invalid reminder update.')
        with self.lock, self.db:
            self.db.execute('UPDATE reminders SET ' + ','.join(f'{key}=?' for key in values) + ' WHERE id=?', (*values.values(), rid))

    def voice_queued(self, item):
        self.update(item['id'], voice_queued_at=self.clock(), error='')

    def voice_failed(self, item, error):
        self.update(item['id'], error=f'Voice delivery failed ({type(error).__name__}).', voice_retry_at=self.clock() + 30)

    def cancel(self, rid):
        self.get(rid)
        self.update(rid, cancelled_at=self.clock())
        return self.get(rid)


def notify_desktop(message, os_name=None):
    """Submit a native notification or raise; message text is never shell code."""
    name = os_name or platform.system().lower()
    if name == 'windows':
        executable = shutil.which('powershell.exe') or shutil.which('pwsh.exe')
        if not executable:
            raise RuntimeError('PowerShell is unavailable for desktop notification.')
        script = '''$ErrorActionPreference = 'Stop'
$notice = [Console]::In.ReadToEnd() | ConvertFrom-Json
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$icon = New-Object System.Windows.Forms.NotifyIcon
try {
    $icon.Icon = [System.Drawing.SystemIcons]::Information
    $icon.Visible = $true
    $icon.BalloonTipTitle = 'Zaya Reminder'
    $icon.BalloonTipText = [string]$notice.message
    $icon.ShowBalloonTip(15000)
    [System.Media.SystemSounds]::Asterisk.Play()
    Start-Sleep -Seconds 16
} finally { $icon.Dispose() }
'''
        result = subprocess.run([executable, '-NoProfile', '-NonInteractive', '-Command', script],
                                input=json.dumps({'message': message}), capture_output=True, text=True,
                                timeout=30, creationflags=subprocess.CREATE_NO_WINDOW)
    elif name in {'mac', 'darwin'}:
        script = 'display notification ' + json.dumps(message, ensure_ascii=False) + ' with title "Zaya Reminder"'
        result = subprocess.run(['osascript', '-e', script], capture_output=True, text=True, timeout=20)
    else:
        result = subprocess.run(['notify-send', '--urgency=normal', '--expire-time=15000',
                                 'Zaya Reminder', message], capture_output=True, text=True, timeout=20)
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or 'Desktop notifier failed.')[-1000:])


def notify_scheduled(rid, database, os_name):
    """OS scheduler callback: persist failure, and never claim speech occurred."""
    store = ReminderStore(database)
    try:
        item = store.get(rid)
        if item['cancelled_at'] is not None or item['desktop_notified_at'] is not None or item['voice_queued_at'] is not None:
            return True
        remaining = item['due_at'] - store.clock()
        if remaining > 60:
            raise RuntimeError('The scheduler ran before this reminder was due.')
        if remaining > 0:
            time.sleep(remaining)  # Minute-resolution schedulers may start early.
        notify_desktop(item['message'], os_name)
        store.update(rid, desktop_notified_at=store.clock(), error='')
        return True
    except Exception as error:
        store.update(rid, error=str(error)[:1000])
        return False
    finally:
        store.close()


_store = None
_store_lock = threading.Lock()


def get_reminders():
    global _store
    with _store_lock:
        if _store is None:
            _store = ReminderStore()
        return _store
