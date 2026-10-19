"""High-performance hybrid local knowledge store backed by SQLite (WAL mode, FTS5).

Provides full-text lexical search with BM25 ranking, structured category-aware limits,
entity relationships, transactional consistency, and JSON store synchronization.
"""
from __future__ import annotations

import json
import logging
import re
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).resolve().parent / "knowledge.db"

_SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;

CREATE TABLE IF NOT EXISTS facts (
    category TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_used_at TEXT,
    expires_at TEXT,
    confidence REAL DEFAULT 1.0,
    source TEXT DEFAULT 'user',
    metadata_json TEXT,
    PRIMARY KEY (category, key)
);

CREATE TABLE IF NOT EXISTS entity_relations (
    source_entity TEXT NOT NULL,
    relation TEXT NOT NULL,
    target_entity TEXT NOT NULL,
    weight REAL DEFAULT 1.0,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (source_entity, relation, target_entity)
);

CREATE VIRTUAL TABLE IF NOT EXISTS facts_fts USING fts5(
    category UNINDEXED,
    key,
    value,
    content='facts',
    content_rowid='rowid'
);

CREATE TRIGGER IF NOT EXISTS facts_ai AFTER INSERT ON facts BEGIN
  INSERT INTO facts_fts(rowid, category, key, value) VALUES (new.rowid, new.category, new.key, new.value);
END;

CREATE TRIGGER IF NOT EXISTS facts_ad AFTER DELETE ON facts BEGIN
  INSERT INTO facts_fts(facts_fts, rowid, category, key, value) VALUES('delete', old.rowid, old.category, old.key, old.value);
END;

CREATE TRIGGER IF NOT EXISTS facts_au AFTER UPDATE ON facts BEGIN
  INSERT INTO facts_fts(facts_fts, rowid, category, key, value) VALUES('delete', old.rowid, old.category, old.key, old.value);
  INSERT INTO facts_fts(rowid, category, key, value) VALUES (new.rowid, new.category, new.key, new.value);
END;
"""


class KnowledgeStore:
    """Thread-safe SQLite + FTS5 knowledge store."""

    def __init__(self, db_path: Path | str | None = None, clock: Callable[[], float] = time.time):
        self._path = Path(db_path) if db_path else DB_PATH
        self._clock = clock
        self._lock = threading.RLock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(str(self._path), timeout=10.0)
        con.row_factory = sqlite3.Row
        return con

    def _init_db(self) -> None:
        with self._lock:
            try:
                con = self._connect()
                try:
                    con.executescript(_SCHEMA)
                    con.commit()
                finally:
                    con.close()
            except Exception as e:
                logger.error("Failed to initialize KnowledgeStore database at %s: %s", self._path, e)

    def put_fact(
        self,
        category: str,
        key: str,
        value: str,
        confidence: float = 1.0,
        source: str = "user",
        expires_at: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Insert or replace a factual memory entry."""
        cat = str(category or "notes").strip().lower()
        k = str(key or "").strip().lower()
        val = str(value or "").strip()
        if not k or not val:
            return

        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self._clock()))
        meta_json = json.dumps(metadata or {}, ensure_ascii=False)

        with self._lock:
            con = self._connect()
            try:
                cur = con.cursor()
                cur.execute(
                    """
                    INSERT INTO facts (category, key, value, created_at, updated_at, expires_at, confidence, source, metadata_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(category, key) DO UPDATE SET
                        value=excluded.value,
                        updated_at=excluded.updated_at,
                        expires_at=excluded.expires_at,
                        confidence=excluded.confidence,
                        source=excluded.source,
                        metadata_json=excluded.metadata_json
                    """,
                    (cat, k, val, now, now, expires_at, float(confidence), str(source), meta_json),
                )
                con.commit()
            finally:
                con.close()

    def get_fact(self, category: str, key: str) -> dict[str, Any] | None:
        with self._lock:
            con = self._connect()
            try:
                cur = con.cursor()
                row = cur.execute(
                    "SELECT category, key, value, created_at, updated_at, confidence, source FROM facts WHERE category=? AND key=?",
                    (category.strip().lower(), key.strip().lower()),
                ).fetchone()
                if row:
                    return dict(row)
                return None
            finally:
                con.close()

    def delete_fact(self, category: str, key: str) -> bool:
        with self._lock:
            con = self._connect()
            try:
                cur = con.cursor()
                cur.execute(
                    "DELETE FROM facts WHERE category=? AND key=?",
                    (category.strip().lower(), key.strip().lower()),
                )
                con.commit()
                return cur.rowcount > 0
            finally:
                con.close()

    def record_relation(self, source_entity: str, relation: str, target_entity: str, weight: float = 1.0) -> None:
        """Record an entity relationship edge."""
        src = str(source_entity or "").strip().lower()
        rel = str(relation or "").strip().lower()
        tgt = str(target_entity or "").strip().lower()
        if not src or not rel or not tgt:
            return
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self._clock()))

        with self._lock:
            con = self._connect()
            try:
                cur = con.cursor()
                cur.execute(
                    """
                    INSERT INTO entity_relations (source_entity, relation, target_entity, weight, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(source_entity, relation, target_entity) DO UPDATE SET
                        weight=excluded.weight,
                        updated_at=excluded.updated_at
                    """,
                    (src, rel, tgt, float(weight), now),
                )
                con.commit()
            finally:
                con.close()

    def get_relations(self, entity: str) -> list[dict[str, Any]]:
        ent = str(entity or "").strip().lower()
        with self._lock:
            con = self._connect()
            try:
                cur = con.cursor()
                rows = cur.execute(
                    "SELECT source_entity, relation, target_entity, weight FROM entity_relations WHERE source_entity=? OR target_entity=?",
                    (ent, ent),
                ).fetchall()
                return [dict(r) for r in rows]
            finally:
                con.close()

    def search_hybrid(self, query: str, limit: int = 8) -> list[dict[str, Any]]:
        """Hybrid search combining FTS5 BM25 ranking and lexical fallback."""
        clean_q = re.sub(r"[^\w\s]", " ", (query or "")).strip()
        tokens = [t for t in clean_q.split() if len(t) > 1]
        results: list[dict[str, Any]] = []

        with self._lock:
            con = self._connect()
            try:
                cur = con.cursor()
                # 1. Try FTS5 BM25 match if query tokens exist
                if tokens:
                    fts_query = " OR ".join(f'"{t}"*' for t in tokens)
                    try:
                        rows = cur.execute(
                            """
                            SELECT f.category, f.key, f.value, f.updated_at, bm25(facts_fts) as score
                            FROM facts_fts
                            JOIN facts f ON f.rowid = facts_fts.rowid
                            WHERE facts_fts MATCH ?
                            ORDER BY score ASC
                            LIMIT ?
                            """,
                            (fts_query, limit),
                        ).fetchall()
                        for r in rows:
                            results.append({
                                "category": r["category"],
                                "key": r["key"],
                                "value": r["value"],
                                "updated_at": r["updated_at"],
                                "score": float(r["score"]),
                            })
                    except Exception as e:
                        logger.debug("FTS5 match failed, falling back to LIKE: %s", e)

                # 2. Fallback / supplementary search if empty or fewer than limit
                if len(results) < limit:
                    seen = {(r["category"], r["key"]) for r in results}
                    # If empty query, return most recently updated facts
                    if not tokens:
                        rows = cur.execute(
                            "SELECT category, key, value, updated_at FROM facts ORDER BY updated_at DESC LIMIT ?",
                            (limit,),
                        ).fetchall()
                    else:
                        like_clause = " OR ".join("key LIKE ? OR value LIKE ?" for _ in tokens)
                        params: list[str] = []
                        for t in tokens:
                            params.extend([f"%{t}%", f"%{t}%"])
                        params.append(str(limit - len(results)))
                        rows = cur.execute(
                            f"SELECT category, key, value, updated_at FROM facts WHERE {like_clause} ORDER BY updated_at DESC LIMIT ?",
                            params,
                        ).fetchall()

                    for r in rows:
                        pair = (r["category"], r["key"])
                        if pair not in seen:
                            results.append({
                                "category": r["category"],
                                "key": r["key"],
                                "value": r["value"],
                                "updated_at": r["updated_at"],
                                "score": 10.0,
                            })
                            seen.add(pair)
                            if len(results) >= limit:
                                break

                return results
            finally:
                con.close()

    def sync_from_json(self, memory_dict: dict[str, Any]) -> int:
        """Sync facts from in-memory / JSON dict representation into SQLite store."""
        count = 0
        with self._lock:
            for cat, items in memory_dict.items():
                if not isinstance(items, dict):
                    continue
                for key, entry in items.items():
                    if isinstance(entry, dict) and "value" in entry:
                        val = str(entry["value"])
                        conf = float(entry.get("confidence", 1.0))
                        src = str(entry.get("source", "user"))
                        exp = entry.get("expires_at")
                        self.put_fact(cat, key, val, confidence=conf, source=src, expires_at=exp)
                        count += 1
                    elif isinstance(entry, str) and entry.strip():
                        self.put_fact(cat, key, entry.strip())
                        count += 1
        return count


_store: KnowledgeStore | None = None


def get_knowledge_store() -> KnowledgeStore:
    global _store
    if _store is None:
        _store = KnowledgeStore()
    return _store
