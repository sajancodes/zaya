"""High-performance hybrid local knowledge store backed by SQLite (WAL mode, FTS5).

Provides full-text lexical search with BM25 ranking, structured category-aware limits,
entity relationships, transactional consistency, corruption recovery, and JSON store synchronization.
"""
from __future__ import annotations

import json
import logging
import re
import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from core.runtime_paths import mutable_path
from typing import Any, Callable
from memory.fact_policy import confidence as fact_confidence, expiry as fact_expiry

logger = logging.getLogger(__name__)

_DEFAULT_DB_PATH = mutable_path(Path(__file__).resolve().parent / "knowledge.db")

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

CREATE TABLE IF NOT EXISTS aliases (
    alias TEXT NOT NULL,
    canonical_key TEXT NOT NULL,
    category TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (alias, category)
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


def _derive_default_db_path() -> Path:
    """Derive SQLite DB path from memory_manager.MEMORY_PATH so tests monkeypatching MEMORY_PATH isolate DB."""
    try:
        from memory import memory_manager
        return memory_manager.MEMORY_PATH.parent / "knowledge.db"
    except Exception:
        return _DEFAULT_DB_PATH


class KnowledgeStore:
    """Thread-safe SQLite + FTS5 knowledge store."""

    def __init__(self, db_path: Path | str | None = None, clock: Callable[[], float] = time.time):
        self._custom_path = Path(db_path) if db_path else None
        self._clock = clock
        self._lock = threading.RLock()
        self._init_db()

    @property
    def path(self) -> Path:
        if self._custom_path:
            return self._custom_path
        return _derive_default_db_path()

    def _connect(self) -> sqlite3.Connection:
        p = self.path
        p.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(str(p), timeout=10.0)
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
                logger.error("Failed to initialize KnowledgeStore database at %s: %s", self.path, e)
                self._handle_corruption(e)

    def _handle_corruption(self, err: Exception) -> None:
        """Recover from SQLite database corruption by backing up corrupt file, recreating schema, and resyncing from JSON."""
        logger.warning("Attempting SQLite corruption recovery for %s due to: %s", self.path, err)
        with self._lock:
            try:
                corrupt_backup = self.path.with_suffix(".corrupt")
                if self.path.exists():
                    self.path.replace(corrupt_backup)
                con = self._connect()
                try:
                    con.executescript(_SCHEMA)
                    con.commit()
                finally:
                    con.close()
                # Rebuild from memory_manager JSON
                # Atomic JSON replacement permits a coherent snapshot without
                # acquiring the manager lock while holding the index lock.
                # Taking those locks in reverse order can deadlock a writer.
                from memory.memory_manager import MEMORY_PATH
                data = json.loads(MEMORY_PATH.read_text(encoding='utf-8')) if MEMORY_PATH.exists() else {}
                self.sync_from_json(data)
                logger.info("Corruption recovery successful: rebuilt %s from JSON store", self.path)
            except Exception as rec_err:
                logger.error("Corruption recovery failed: %s", rec_err)

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
        confidence = fact_confidence(confidence)
        if confidence < .7:
            return
        try:
            expires_at = fact_expiry(expires_at)
        except (TypeError, ValueError, OverflowError):
            return

        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self._clock()))
        meta_json = json.dumps(metadata or {}, ensure_ascii=False)

        with self._lock:
            try:
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
            except sqlite3.DatabaseError as e:
                self._handle_corruption(e)

    def get_fact(self, category: str, key: str) -> dict[str, Any] | None:
        with self._lock:
            con = self._connect()
            try:
                cur = con.cursor()
                row = cur.execute(
                    "SELECT category, key, value, created_at, updated_at, confidence, source, expires_at, last_used_at FROM facts WHERE category=? AND key=?",
                    (category.strip().lower(), key.strip().lower()),
                ).fetchone()
                if row:
                    return dict(row)
                return None
            except sqlite3.DatabaseError as e:
                self._handle_corruption(e)
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
            except sqlite3.DatabaseError as e:
                self._handle_corruption(e)
                return False
            finally:
                con.close()

    def record_alias(self, alias: str, canonical_key: str, category: str) -> None:
        """Map an alias/synonym to a canonical memory key."""
        a = str(alias or "").strip().lower()
        c = str(canonical_key or "").strip().lower()
        cat = str(category or "").strip().lower()
        if not a or not c or not cat:
            return
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self._clock()))

        with self._lock:
            con = self._connect()
            try:
                cur = con.cursor()
                cur.execute(
                    """
                    INSERT INTO aliases (alias, canonical_key, category, created_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(alias, category) DO UPDATE SET
                        canonical_key=excluded.canonical_key
                    """,
                    (a, c, cat, now),
                )
                con.commit()
            except sqlite3.DatabaseError as e:
                self._handle_corruption(e)
            finally:
                con.close()

    def resolve_alias(self, alias: str, category: str | None = None) -> str | None:
        """Resolve an alias to its canonical key."""
        a = str(alias or "").strip().lower()
        with self._lock:
            con = self._connect()
            try:
                cur = con.cursor()
                if category:
                    row = cur.execute(
                        "SELECT canonical_key FROM aliases WHERE alias=? AND category=?",
                        (a, category.strip().lower()),
                    ).fetchone()
                else:
                    row = cur.execute(
                        "SELECT canonical_key FROM aliases WHERE alias=?",
                        (a,),
                    ).fetchone()
                return str(row["canonical_key"]) if row else None
            except sqlite3.DatabaseError as e:
                self._handle_corruption(e)
                return None
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
            except sqlite3.DatabaseError as e:
                self._handle_corruption(e)
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
            except sqlite3.DatabaseError as e:
                self._handle_corruption(e)
                return []
            finally:
                con.close()

    def search_hybrid(self, query: str, limit: int = 8) -> list[dict[str, Any]]:
        """Hybrid search combining FTS5 BM25 ranking, expiration filtering, alias resolution, 1-hop entity boosting, and last_used_at update."""
        clean_q = re.sub(r"[^\w\s]", " ", (query or "")).strip()
        tokens = [t for t in clean_q.split() if len(t) > 1]
        now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self._clock()))

        # Expand query tokens with aliases and 1-hop related entity targets
        expanded_keys: set[str] = set()
        for t in tokens:
            canon = self.resolve_alias(t)
            if canon:
                expanded_keys.add(canon)
            # 1-hop relation lookup
            rels = self.get_relations(t)
            for r in rels:
                tgt = r.get("target_entity")
                if tgt:
                    expanded_keys.add(tgt)

        results: list[dict[str, Any]] = []

        with self._lock:
            con = self._connect()
            try:
                cur = con.cursor()
                # 1. Try FTS5 BM25 match excluding expired facts
                search_terms = list(tokens) + list(expanded_keys)
                if search_terms:
                    fts_query = " OR ".join(f'"{t}"*' for t in search_terms)
                    try:
                        rows = cur.execute(
                            """
                            SELECT f.category, f.key, f.value, f.updated_at, f.expires_at, bm25(facts_fts) as score
                            FROM facts_fts
                            JOIN facts f ON f.rowid = facts_fts.rowid
                            WHERE facts_fts MATCH ?
                              AND f.confidence>=0.7
                              AND (f.expires_at IS NULL OR julianday(f.expires_at) > julianday(?))
                            ORDER BY score ASC
                            LIMIT ?
                            """,
                            (fts_query, now_iso, limit),
                        ).fetchall()
                        for r in rows:
                            # Apply 1-hop entity relation boosting
                            base_score = float(r["score"])
                            if r["key"] in expanded_keys:
                                base_score -= 1.5  # lower score is better in BM25 ASC
                            results.append({
                                "category": r["category"],
                                "key": r["key"],
                                "value": r["value"],
                                "updated_at": r["updated_at"],
                                "score": base_score,
                            })
                    except Exception as e:
                        logger.debug("FTS5 match failed, falling back to LIKE: %s", e)

                # 2. Fallback / supplementary search if empty or fewer than limit
                if len(results) < limit:
                    seen = {(r["category"], r["key"]) for r in results}
                    # If empty query, return most recently updated facts
                    if not search_terms:
                        rows = cur.execute(
                            "SELECT category, key, value, updated_at FROM facts WHERE confidence>=0.7 AND (expires_at IS NULL OR julianday(expires_at) > julianday(?)) ORDER BY updated_at DESC LIMIT ?",
                            (now_iso, limit),
                        ).fetchall()
                    else:
                        like_clause = " OR ".join("key LIKE ? OR value LIKE ?" for _ in search_terms)
                        params: list[Any] = [now_iso]
                        for t in search_terms:
                            params.extend([f"%{t}%", f"%{t}%"])
                        params.append(limit - len(results))
                        rows = cur.execute(
                            f"SELECT category, key, value, updated_at FROM facts WHERE confidence>=0.7 AND (expires_at IS NULL OR julianday(expires_at) > julianday(?)) AND ({like_clause}) ORDER BY updated_at DESC LIMIT ?",
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

                # Sort by score ascending
                results.sort(key=lambda r: r["score"])
                final_results = results[:limit]

                # Update last_used_at ONLY on the returned facts
                if final_results:
                    for r in final_results:
                        cur.execute(
                            "UPDATE facts SET last_used_at=? WHERE category=? AND key=?",
                            (now_iso, r["category"], r["key"]),
                        )
                    con.commit()

                return final_results
            except sqlite3.DatabaseError as e:
                self._handle_corruption(e)
                return []
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
                        conf = fact_confidence(entry.get("confidence", 1.0))
                        if conf < .7:
                            continue
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
