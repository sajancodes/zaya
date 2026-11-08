"""Quick Notes & Thought Capture Engine.
Created and developed by Sajan Rai for Zaya.

Provides fast, local, private thought capture, tagging, full-text search,
and markdown export without external cloud dependencies.
"""
from __future__ import annotations

import datetime
import json
from pathlib import Path
import sqlite3
from typing import Any, Dict, List, Optional

from core.execution_policy import require_owner


def _get_db_path() -> Path:
    base = Path(__file__).resolve().parent.parent / "memory"
    base.mkdir(parents=True, exist_ok=True)
    return base / "quick_notes.db"


def _init_db(db_path: Path) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                tags TEXT DEFAULT '',
                pinned INTEGER DEFAULT 0
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_notes_created ON notes(created_at)")
        conn.commit()


def quick_notes(parameters: dict, **_kwargs) -> str:
    """Dispatches note creation, search, retrieval, and management."""
    require_owner()
    action = str(parameters.get("action") or "create").lower().strip()
    db_path = _get_db_path()
    _init_db(db_path)

    # 1. Create Note
    if action in ("create", "add", "new", "save"):
        content = str(parameters.get("content") or parameters.get("note") or parameters.get("text") or "").strip()
        if not content:
            return json.dumps({
                "status": "error",
                "message": "Note content cannot be empty."
            }, indent=2)

        # Title: user specified, or first line of note
        title = str(parameters.get("title") or "").strip()
        if not title:
            first_line = content.split("\n")[0].strip()
            title = first_line[:60] if len(first_line) > 60 else first_line

        tags = str(parameters.get("tags") or "").strip()
        pinned = 1 if parameters.get("pinned") in (True, 1, "true", "yes") else 0
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %I:%M %p")

        with sqlite3.connect(db_path) as conn:
            cur = conn.execute(
                "INSERT INTO notes (created_at, title, content, tags, pinned) VALUES (?, ?, ?, ?, ?)",
                (now_str, title, content, tags, pinned)
            )
            note_id = cur.lastrowid
            conn.commit()

        return json.dumps({
            "status": "success",
            "action": "create",
            "note_id": note_id,
            "title": title,
            "created_at": now_str,
            "summary": f"Saved note #{note_id}: '{title}', sir."
        }, indent=2)

    # 2. List Notes
    if action in ("list", "all", "recent"):
        limit = max(1, min(50, int(parameters.get("limit", 10))))
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT id, created_at, title, content, tags, pinned FROM notes ORDER BY pinned DESC, id DESC LIMIT ?",
                (limit,)
            ).fetchall()

        notes = [dict(r) for r in rows]
        if not notes:
            return json.dumps({
                "status": "success",
                "action": "list",
                "notes": [],
                "summary": "You have no saved notes yet, sir."
            }, indent=2)

        summary_titles = [f"#{n['id']} {n['title']}" for n in notes[:5]]
        return json.dumps({
            "status": "success",
            "action": "list",
            "count": len(notes),
            "notes": notes,
            "summary": f"Found {len(notes)} note(s): {', '.join(summary_titles)}."
        }, indent=2)

    # 3. Search Notes
    if action in ("search", "find"):
        query = str(parameters.get("query") or parameters.get("text") or "").strip()
        if not query:
            return json.dumps({
                "status": "error",
                "message": "Please specify a search term."
            }, indent=2)

        pattern = f"%{query}%"
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT id, created_at, title, content, tags, pinned
                FROM notes
                WHERE title LIKE ? OR content LIKE ? OR tags LIKE ?
                ORDER BY pinned DESC, id DESC LIMIT 20
                """,
                (pattern, pattern, pattern)
            ).fetchall()

        results = [dict(r) for r in rows]
        if not results:
            return json.dumps({
                "status": "success",
                "action": "search",
                "query": query,
                "count": 0,
                "notes": [],
                "summary": f"No notes matched '{query}', sir."
            }, indent=2)

        summary_titles = [f"#{n['id']} {n['title']}" for n in results[:3]]
        return json.dumps({
            "status": "success",
            "action": "search",
            "query": query,
            "count": len(results),
            "notes": results,
            "summary": f"Found {len(results)} note(s) matching '{query}': {', '.join(summary_titles)}."
        }, indent=2)

    # 4. Delete Note
    if action in ("delete", "remove"):
        note_id = parameters.get("note_id") or parameters.get("id")
        if not note_id:
            return json.dumps({
                "status": "error",
                "message": "Parameter 'note_id' is required to delete a note."
            }, indent=2)

        with sqlite3.connect(db_path) as conn:
            cur = conn.execute("DELETE FROM notes WHERE id = ?", (int(note_id),))
            deleted = cur.rowcount
            conn.commit()

        if deleted:
            return json.dumps({
                "status": "success",
                "action": "delete",
                "note_id": note_id,
                "summary": f"Note #{note_id} deleted, sir."
            }, indent=2)

        return json.dumps({
            "status": "error",
            "message": f"Note #{note_id} not found."
        }, indent=2)

    return json.dumps({
        "status": "error",
        "message": f"Unsupported action '{action}'. Choose from: create, list, search, delete."
    }, indent=2)


TOOL = {
    "name": "quick_notes",
    "description": (
        "Quick Notes & Thought Capture: Fast local note-taking, idea logging, memo searching, and thought archiving. "
        "Allows taking notes, retrieving recent notes, and searching by keyword or tags without external cloud services."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "'create' to take a note; 'list' to show recent notes; 'search' to find notes by keyword; 'delete' to remove a note by ID.",
                "enum": ["create", "list", "search", "delete"]
            },
            "content": {
                "type": "STRING",
                "description": "The body text / thought content to record."
            },
            "title": {
                "type": "STRING",
                "description": "Optional short title for the note. If omitted, the first line of content is used."
            },
            "query": {
                "type": "STRING",
                "description": "Keyword to search across notes (used with action='search')."
            },
            "note_id": {
                "type": "INTEGER",
                "description": "ID of note to delete (used with action='delete')."
            },
            "tags": {
                "type": "STRING",
                "description": "Optional comma-separated tags (e.g., 'ideas, project, urgent')."
            }
        },
        "required": ["action"]
    },
    "handler": quick_notes,
}
