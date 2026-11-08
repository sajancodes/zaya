"""High-Performance Semantic Vector Memory & Associative Graph for Zaya.
Created and developed by Sajan Rai.

Provides fast, zero-dependency subword/token hashing vector embeddings with
cosine similarity search, SQLite persistence, and associative relationship linking.
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
import re
import sqlite3
import struct
import threading
import time
from pathlib import Path
from typing import Any, List, Optional, Tuple

try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:
    _HAS_NUMPY = False

from core.runtime_paths import mutable_path

logger = logging.getLogger(__name__)

DEFAULT_VECTOR_DIM = 256
_DEFAULT_DB_PATH = mutable_path(Path(__file__).resolve().parent / "vector_memory.db")

_SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;

CREATE TABLE IF NOT EXISTS vectors (
    id TEXT PRIMARY KEY,
    category TEXT NOT NULL,
    text TEXT NOT NULL,
    dim INTEGER NOT NULL,
    embedding BLOB NOT NULL,
    metadata_json TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_vectors_cat ON vectors(category);

CREATE TABLE IF NOT EXISTS vector_edges (
    source_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    similarity REAL NOT NULL,
    updated_at REAL NOT NULL,
    PRIMARY KEY (source_id, target_id)
);
"""


def _hash_feature(feature: str, dim: int) -> Tuple[int, float]:
    """Map a text feature into a fixed index and sign via deterministic hashing."""
    digest = hashlib.md5(feature.encode("utf-8")).digest()
    idx = int.from_bytes(digest[:4], byteorder="big") % dim
    sign = 1.0 if (digest[4] & 1) == 0 else -1.0
    return idx, sign


def compute_embedding(text: str, dim: int = DEFAULT_VECTOR_DIM) -> List[float]:
    """Compute normalized subword and token hashing vector representation."""
    vec = [0.0] * dim
    clean = re.sub(r"[^\w\s]", " ", text.lower()).strip()
    words = [w for w in clean.split() if w]
    if not words:
        return vec

    # Word unigrams and bigrams
    for i, w in enumerate(words):
        idx, sign = _hash_feature(f"w:{w}", dim)
        vec[idx] += sign * 2.0

        if i + 1 < len(words):
            bi = f"{w}_{words[i+1]}"
            idx_bi, sign_bi = _hash_feature(f"bi:{bi}", dim)
            vec[idx_bi] += sign_bi * 1.5

        # Subword character n-grams (3 to 5 chars) for typo resilience & root matching
        padded = f"<{w}>"
        for n in (3, 4, 5):
            for j in range(len(padded) - n + 1):
                ngram = padded[j:j+n]
                n_idx, n_sign = _hash_feature(f"ng:{ngram}", dim)
                vec[n_idx] += n_sign * 0.8

    # L2 normalize
    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 1e-9:
        vec = [v / norm for v in vec]
    return vec


def _pack_vector(vec: List[float]) -> bytes:
    return struct.pack(f"{len(vec)}f", *vec)


def _unpack_vector(blob: bytes, dim: int) -> List[float]:
    return list(struct.unpack(f"{dim}f", blob))


class SemanticVectorMemory:
    """Thread-safe persistent semantic vector store and associative knowledge graph."""

    def __init__(self, db_path: Optional[Path | str] = None, dim: int = DEFAULT_VECTOR_DIM) -> None:
        self.path = Path(db_path) if db_path else _DEFAULT_DB_PATH
        self.dim = dim
        self._lock = threading.RLock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(str(self.path), timeout=10.0)
        con.row_factory = sqlite3.Row
        return con

    def _init_db(self) -> None:
        with self._lock:
            con = self._connect()
            try:
                con.executescript(_SCHEMA)
                con.commit()
            finally:
                con.close()

    def add(
        self,
        text: str,
        category: str = "general",
        metadata: Optional[dict[str, Any]] = None,
        doc_id: Optional[str] = None,
        edge_min_sim: float = 0.50,
    ) -> str:
        """Add or update a document in semantic vector memory."""
        clean_text = text.strip()
        if not clean_text:
            raise ValueError("Document text cannot be empty.")

        if not doc_id:
            # Deterministic ID based on category and text
            doc_id = hashlib.sha256(f"{category}:{clean_text}".encode("utf-8")).hexdigest()[:16]

        vec = compute_embedding(clean_text, self.dim)
        blob = _pack_vector(vec)
        now = time.time()
        meta_json = json.dumps(metadata or {}, ensure_ascii=False)

        with self._lock:
            con = self._connect()
            try:
                con.execute(
                    """
                    INSERT INTO vectors (id, category, text, dim, embedding, metadata_json, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        category=excluded.category,
                        text=excluded.text,
                        dim=excluded.dim,
                        embedding=excluded.embedding,
                        metadata_json=excluded.metadata_json,
                        updated_at=excluded.updated_at
                    """,
                    (doc_id, category.strip().lower(), clean_text, self.dim, blob, meta_json, now, now),
                )
                con.commit()
                # Auto-link associative neighbors with cosine similarity >= edge_min_sim
                self._update_associative_edges(con, doc_id, vec, min_sim=edge_min_sim)
                con.commit()
            finally:
                con.close()

        return doc_id

    def _update_associative_edges(self, con: sqlite3.Connection, doc_id: str, vec: List[float], min_sim: float = 0.50) -> None:
        """Compute associative edges between the new doc and existing items."""
        rows = con.execute("SELECT id, dim, embedding FROM vectors WHERE id != ?", (doc_id,)).fetchall()
        now = time.time()
        for r in rows:
            other_id = r["id"]
            other_vec = _unpack_vector(r["embedding"], r["dim"])
            sim = self._cosine_similarity(vec, other_vec)
            if sim >= min_sim:
                con.execute(
                    """
                    INSERT INTO vector_edges (source_id, target_id, similarity, updated_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(source_id, target_id) DO UPDATE SET
                        similarity=excluded.similarity,
                        updated_at=excluded.updated_at
                    """,
                    (doc_id, other_id, sim, now),
                )
                con.execute(
                    """
                    INSERT INTO vector_edges (source_id, target_id, similarity, updated_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(source_id, target_id) DO UPDATE SET
                        similarity=excluded.similarity,
                        updated_at=excluded.updated_at
                    """,
                    (other_id, doc_id, sim, now),
                )

    def _cosine_similarity(self, v1: List[float], v2: List[float]) -> float:
        """Cosine similarity for normalized vectors is their dot product."""
        if _HAS_NUMPY:
            return float(np.dot(v1, v2))
        return sum(a * b for a, b in zip(v1, v2))

    def search(
        self,
        query: str,
        category: Optional[str] = None,
        top_k: int = 5,
        min_score: float = 0.20,
    ) -> List[dict[str, Any]]:
        """Semantic search returning top-k matching documents by cosine similarity."""
        clean_q = query.strip()
        if not clean_q:
            return []

        q_vec = compute_embedding(clean_q, self.dim)

        with self._lock:
            con = self._connect()
            try:
                if category:
                    rows = con.execute(
                        "SELECT id, category, text, dim, embedding, metadata_json, created_at, updated_at FROM vectors WHERE category = ?",
                        (category.strip().lower(),),
                    ).fetchall()
                else:
                    rows = con.execute(
                        "SELECT id, category, text, dim, embedding, metadata_json, created_at, updated_at FROM vectors"
                    ).fetchall()

                if not rows:
                    return []

                scored: List[Tuple[float, sqlite3.Row]] = []
                if _HAS_NUMPY and len(rows) > 32:
                    # Vectorized batch cosine similarity
                    matrix = np.array([_unpack_vector(r["embedding"], r["dim"]) for r in rows], dtype=np.float32)
                    q_arr = np.array(q_vec, dtype=np.float32)
                    sims = np.dot(matrix, q_arr)
                    for sim, row in zip(sims, rows):
                        if sim >= min_score:
                            scored.append((float(sim), row))
                else:
                    for r in rows:
                        doc_vec = _unpack_vector(r["embedding"], r["dim"])
                        sim = self._cosine_similarity(q_vec, doc_vec)
                        if sim >= min_score:
                            scored.append((sim, r))

                scored.sort(key=lambda x: x[0], reverse=True)
                results: List[dict[str, Any]] = []

                for sim, r in scored[:top_k]:
                    meta = {}
                    if r["metadata_json"]:
                        try:
                            meta = json.loads(r["metadata_json"])
                        except Exception:
                            pass

                    # Fetch associative neighbors
                    edge_rows = con.execute(
                        "SELECT target_id, similarity FROM vector_edges WHERE source_id = ? ORDER BY similarity DESC LIMIT 3",
                        (r["id"],),
                    ).fetchall()
                    neighbors = [{"target_id": er["target_id"], "similarity": round(er["similarity"], 3)} for er in edge_rows]

                    results.append({
                        "id": r["id"],
                        "category": r["category"],
                        "text": r["text"],
                        "score": round(sim, 4),
                        "metadata": meta,
                        "neighbors": neighbors,
                        "updated_at": r["updated_at"],
                    })

                return results
            finally:
                con.close()

    def get(self, doc_id: str) -> Optional[dict[str, Any]]:
        with self._lock:
            con = self._connect()
            try:
                r = con.execute(
                    "SELECT id, category, text, metadata_json, created_at, updated_at FROM vectors WHERE id = ?",
                    (doc_id,),
                ).fetchone()
                if not r:
                    return None
                meta = {}
                if r["metadata_json"]:
                    try:
                        meta = json.loads(r["metadata_json"])
                    except Exception:
                        pass
                return {
                    "id": r["id"],
                    "category": r["category"],
                    "text": r["text"],
                    "metadata": meta,
                    "created_at": r["created_at"],
                    "updated_at": r["updated_at"],
                }
            finally:
                con.close()

    def delete(self, doc_id: str) -> bool:
        with self._lock:
            con = self._connect()
            try:
                con.execute("DELETE FROM vector_edges WHERE source_id = ? OR target_id = ?", (doc_id, doc_id))
                cur = con.execute("DELETE FROM vectors WHERE id = ?", (doc_id,))
                con.commit()
                return cur.rowcount > 0
            finally:
                con.close()


# Singleton instance
_vector_mem: Optional[SemanticVectorMemory] = None
_vm_lock = threading.Lock()


def get_vector_memory() -> SemanticVectorMemory:
    global _vector_mem
    with _vm_lock:
        if _vector_mem is None:
            _vector_mem = SemanticVectorMemory()
        return _vector_mem
