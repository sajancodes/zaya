"""Smart Clipboard History & Snippet Vault Engine.
Created and developed by Sajan Rai for Zaya.

Provides private, local clipboard history tracking, persistent snippet tagging,
search, and instant system clipboard injection. All data is persisted locally
in SQLite (memory/clipboard_vault.db) with strict owner authentication.
"""
from __future__ import annotations

import ctypes
import datetime
import json
from pathlib import Path
import sqlite3
from typing import Any, Dict, List, Optional

import pyperclip

from core.execution_policy import require_owner

MAX_UNPINNED_HISTORY = 100


def _get_db_path() -> Path:
    base = Path(__file__).resolve().parent.parent / "memory"
    base.mkdir(parents=True, exist_ok=True)
    return base / "clipboard_vault.db"


def _init_db(db_path: Path) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS clips (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                content TEXT NOT NULL,
                label TEXT DEFAULT '',
                pinned INTEGER DEFAULT 0,
                char_count INTEGER NOT NULL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_clips_created ON clips(created_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_clips_label ON clips(label)")
        conn.commit()


def _read_system_clipboard() -> str:
    """Read current text from system clipboard using pyperclip or ctypes fallback."""
    try:
        val = pyperclip.paste()
        if isinstance(val, str):
            return val
    except Exception:
        pass

    # Win32 ctypes fallback
    try:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        CF_UNICODETEXT = 13
        if user32.OpenClipboard(None):
            h_data = user32.GetClipboardData(CF_UNICODETEXT)
            if h_data:
                p_data = kernel32.GlobalLock(h_data)
                text = ctypes.c_wchar_p(p_data).value
                kernel32.GlobalUnlock(h_data)
                user32.CloseClipboard()
                return text or ""
            user32.CloseClipboard()
    except Exception:
        pass
    return ""


def _write_system_clipboard(text: str) -> bool:
    """Write text to system clipboard using pyperclip or ctypes fallback."""
    try:
        pyperclip.copy(text)
        return True
    except Exception:
        pass

    try:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        CF_UNICODETEXT = 13
        GMEM_MOVEABLE = 0x0002
        encoded = text.encode("utf-16-le") + b"\x00\x00"
        h_mem = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(encoded))
        if h_mem:
            p_mem = kernel32.GlobalLock(h_mem)
            ctypes.memmove(p_mem, encoded, len(encoded))
            kernel32.GlobalUnlock(h_mem)
            if user32.OpenClipboard(None):
                user32.EmptyClipboard()
                user32.SetClipboardData(CF_UNICODETEXT, h_mem)
                user32.CloseClipboard()
                return True
    except Exception:
        pass
    return False


def _trim_history(conn: sqlite3.Connection) -> None:
    """Keep only the latest N unpinned clips to prevent unbounded disk growth."""
    conn.execute(
        """
        DELETE FROM clips
        WHERE pinned = 0 AND id NOT IN (
            SELECT id FROM clips
            WHERE pinned = 0
            ORDER BY id DESC
            LIMIT ?
        )
        """,
        (MAX_UNPINNED_HISTORY,),
    )
    conn.commit()


def clipboard_vault(parameters: dict, **_kwargs) -> str:
    """Dispatches clipboard reading, copying, snippet storage, and search."""
    require_owner()
    action = str(parameters.get("action") or "read").lower().strip()
    db_path = _get_db_path()
    _init_db(db_path)

    # 1. Read Current System Clipboard
    if action in ("read", "current", "get"):
        text = _read_system_clipboard()
        if not text:
            return json.dumps({
                "status": "success",
                "summary": "Clipboard is currently empty.",
                "data": {"content": "", "char_count": 0}
            }, indent=2)

        # Auto-store into vault if different from the latest entry
        with sqlite3.connect(db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT content FROM clips ORDER BY id DESC LIMIT 1")
            row = cur.fetchone()
            if not row or row[0] != text:
                now_iso = datetime.datetime.now().isoformat()
                cur.execute(
                    "INSERT INTO clips (created_at, content, label, pinned, char_count) VALUES (?, ?, ?, ?, ?)",
                    (now_iso, text, "", 0, len(text)),
                )
                _trim_history(conn)

        preview = text[:80] + ("..." if len(text) > 80 else "")
        return json.dumps({
            "status": "success",
            "summary": f"Clipboard contains {len(text)} character(s): '{preview}'",
            "data": {"content": text, "char_count": len(text)}
        }, indent=2)

    # 2. Write / Copy Text to System Clipboard
    if action in ("copy", "set", "write"):
        text = str(parameters.get("text") or parameters.get("content") or "")
        label = str(parameters.get("label") or "").strip()
        pinned = 1 if parameters.get("pinned") else 0

        if not text:
            return json.dumps({"status": "error", "message": "Text cannot be empty when copying to clipboard."}, indent=2)

        success = _write_system_clipboard(text)
        if not success:
            return json.dumps({"status": "error", "message": "Failed to access system clipboard."}, indent=2)

        with sqlite3.connect(db_path) as conn:
            now_iso = datetime.datetime.now().isoformat()
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO clips (created_at, content, label, pinned, char_count) VALUES (?, ?, ?, ?, ?)",
                (now_iso, text, label, pinned, len(text)),
            )
            clip_id = cur.lastrowid
            _trim_history(conn)

        summary = f"Copied {len(text)} characters to clipboard."
        if label:
            summary += f" Saved as snippet '{label}'."
        return json.dumps({
            "status": "success",
            "summary": summary,
            "data": {"id": clip_id, "char_count": len(text), "label": label, "pinned": bool(pinned)}
        }, indent=2)

    # 3. Save / Pin Snippet
    if action in ("save_snippet", "pin", "add_snippet"):
        label = str(parameters.get("label") or "").strip()
        text = str(parameters.get("text") or parameters.get("content") or "").strip()
        if not text:
            text = _read_system_clipboard()

        if not text:
            return json.dumps({"status": "error", "message": "Snippet content cannot be empty."}, indent=2)

        with sqlite3.connect(db_path) as conn:
            now_iso = datetime.datetime.now().isoformat()
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO clips (created_at, content, label, pinned, char_count) VALUES (?, ?, ?, 1, ?)",
                (now_iso, text, label, len(text)),
            )
            clip_id = cur.lastrowid
            conn.commit()

        return json.dumps({
            "status": "success",
            "summary": f"Snippet #{clip_id} '{label or 'untitled'}' pinned to vault ({len(text)} chars).",
            "data": {"id": clip_id, "label": label, "char_count": len(text), "pinned": True}
        }, indent=2)

    # 4. Copy Saved Snippet by Label or ID
    if action in ("copy_snippet", "use_snippet", "recall"):
        label = str(parameters.get("label") or "").strip()
        clip_id = parameters.get("id")

        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            if clip_id:
                cur.execute("SELECT * FROM clips WHERE id = ?", (clip_id,))
            elif label:
                cur.execute("SELECT * FROM clips WHERE label = ? ORDER BY id DESC LIMIT 1", (label,))
                if not cur.fetchone():
                    # Fuzzy match label
                    cur.execute("SELECT * FROM clips WHERE label LIKE ? ORDER BY id DESC LIMIT 1", (f"%{label}%",))
            else:
                return json.dumps({"status": "error", "message": "Must provide 'label' or 'id' to copy snippet."}, indent=2)

            cur = conn.cursor()
            if clip_id:
                cur.execute("SELECT * FROM clips WHERE id = ?", (clip_id,))
            else:
                cur.execute("SELECT * FROM clips WHERE label LIKE ? ORDER BY id DESC LIMIT 1", (f"%{label}%",))
            row = cur.fetchone()

        if not row:
            return json.dumps({"status": "error", "message": f"Snippet '{label or clip_id}' not found."}, indent=2)

        content = row["content"]
        _write_system_clipboard(content)
        return json.dumps({
            "status": "success",
            "summary": f"Snippet #{row['id']} ('{row['label']}') injected into clipboard ({len(content)} chars). Ready to paste.",
            "data": {"id": row["id"], "label": row["label"], "char_count": len(content)}
        }, indent=2)

    # 5. Search / List Clips
    if action in ("search", "list", "history"):
        query = str(parameters.get("query") or parameters.get("search") or "").strip()
        limit = max(1, min(int(parameters.get("limit") or 20), 50))
        only_pinned = bool(parameters.get("pinned_only") or parameters.get("pinned"))

        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            if only_pinned:
                if query:
                    cur.execute(
                        "SELECT id, created_at, content, label, pinned, char_count FROM clips WHERE pinned = 1 AND (content LIKE ? OR label LIKE ?) ORDER BY id DESC LIMIT ?",
                        (f"%{query}%", f"%{query}%", limit),
                    )
                else:
                    cur.execute(
                        "SELECT id, created_at, content, label, pinned, char_count FROM clips WHERE pinned = 1 ORDER BY id DESC LIMIT ?",
                        (limit,),
                    )
            else:
                if query:
                    cur.execute(
                        "SELECT id, created_at, content, label, pinned, char_count FROM clips WHERE content LIKE ? OR label LIKE ? ORDER BY id DESC LIMIT ?",
                        (f"%{query}%", f"%{query}%", limit),
                    )
                else:
                    cur.execute(
                        "SELECT id, created_at, content, label, pinned, char_count FROM clips ORDER BY id DESC LIMIT ?",
                        (limit,),
                    )
            rows = cur.fetchall()

        clips_list = []
        for r in rows:
            preview = r["content"][:100] + ("..." if len(r["content"]) > 100 else "")
            clips_list.append({
                "id": r["id"],
                "created_at": r["created_at"],
                "label": r["label"],
                "pinned": bool(r["pinned"]),
                "char_count": r["char_count"],
                "preview": preview,
            })

        summary = f"Found {len(clips_list)} clip(s) in clipboard vault."
        return json.dumps({"status": "success", "summary": summary, "data": clips_list}, indent=2)

    # 6. Delete Clip or Clear Unpinned
    if action in ("delete", "remove", "clear"):
        clip_id = parameters.get("id")
        with sqlite3.connect(db_path) as conn:
            if clip_id:
                conn.execute("DELETE FROM clips WHERE id = ?", (clip_id,))
                summary = f"Clip #{clip_id} removed from vault."
            else:
                # Clear all unpinned
                conn.execute("DELETE FROM clips WHERE pinned = 0")
                summary = "Cleared all unpinned clipboard history from vault."
            conn.commit()

        return json.dumps({"status": "success", "summary": summary}, indent=2)

    return json.dumps({
        "status": "error",
        "message": f"Unknown action '{action}'. Choose from: read, copy, save_snippet, copy_snippet, search, delete."
    }, indent=2)


TOOL = {
    "name": "clipboard_vault",
    "description": "Read, copy, search, pin snippets, and manage local clipboard history securely in a private SQLite database.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["read", "copy", "save_snippet", "copy_snippet", "search", "delete"],
                "description": "The clipboard operation to perform (default: 'read').",
            },
            "text": {
                "type": "STRING",
                "description": "Text to write to clipboard or store in a snippet.",
            },
            "label": {
                "type": "STRING",
                "description": "Label or tag for snippet recall (e.g. 'wifi_password', 'repo_link').",
            },
            "id": {
                "type": "INTEGER",
                "description": "Specific clip ID to copy, inspect, or delete.",
            },
            "query": {
                "type": "STRING",
                "description": "Search term for filtering clipboard history.",
            },
            "pinned": {
                "type": "BOOLEAN",
                "description": "Whether to pin the clip or filter only pinned snippets.",
            },
        },
    },
    "handler": clipboard_vault,
}
