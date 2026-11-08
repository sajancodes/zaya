from pathlib import Path
import sqlite3
import pytest
from core.task_runtime import TaskRuntime
from memory.conversation_store import ConversationStore


def test_task_runtime_pragmas_and_close(tmp_path: Path):
    db_file = tmp_path / "test_runtime.db"
    runtime = TaskRuntime(db_file)
    
    # Verify WAL journal mode
    journal_mode = runtime.db.execute("PRAGMA journal_mode").fetchone()[0]
    assert journal_mode.lower() == "wal"
    
    # Verify busy_timeout
    busy_timeout = runtime.db.execute("PRAGMA busy_timeout").fetchone()[0]
    assert busy_timeout >= 5000
    
    # Verify synchronous mode is NORMAL (1)
    sync_mode = runtime.db.execute("PRAGMA synchronous").fetchone()[0]
    assert sync_mode == 1
    
    # Create a task to verify operation
    task = runtime.create("Verify database hardening")
    assert task.goal == "Verify database hardening"
    
    # Close and verify clean checkpoint
    runtime.close()
    
    # Verify file can be reopened without issues
    reopened = sqlite3.connect(str(db_file))
    cur = reopened.cursor()
    cur.execute("SELECT id, payload FROM runtime_tasks WHERE id=?", (task.id,))
    row = cur.fetchone()
    assert row is not None
    assert row[0] == task.id
    reopened.close()


def test_conversation_store_pragmas(tmp_path: Path):
    db_file = tmp_path / "test_conversation.db"
    store = ConversationStore(path=db_file)
    
    with store.connect() as db:
        journal_mode = db.execute("PRAGMA journal_mode").fetchone()[0]
        assert journal_mode.lower() == "wal"
        
        busy_timeout = db.execute("PRAGMA busy_timeout").fetchone()[0]
        assert busy_timeout >= 5000
        
        sync_mode = db.execute("PRAGMA synchronous").fetchone()[0]
        assert sync_mode == 1
        
        db.execute("INSERT INTO messages (role, text, created) VALUES (?, ?, ?)", ("user", "hello", 12345.0))
        
    assert store.has_history() is True
