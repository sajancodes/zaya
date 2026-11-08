"""Tests for Semantic Vector Memory and Semantic Recall Action.
Created and developed by Sajan Rai for Zaya.
"""
from __future__ import annotations

import tempfile
from pathlib import Path
import pytest

from core.execution_policy import TRUST_EXTERNAL_MESSAGE, with_trust
from memory.vector_memory import (
    SemanticVectorMemory,
    compute_embedding,
)
from actions.semantic_recall import semantic_recall


@pytest.fixture
def temp_vector_mem():
    with tempfile.TemporaryDirectory() as td:
        db_path = Path(td) / "test_vector.db"
        vm = SemanticVectorMemory(db_path=db_path)
        yield vm


def test_embedding_computation_and_normalization():
    vec1 = compute_embedding("Deploying docker containers to cluster", dim=128)
    assert len(vec1) == 128
    # L2 norm should be approximately 1.0
    norm = sum(v * v for v in vec1) ** 0.5
    assert abs(norm - 1.0) < 1e-4

    # Empty text produces zero vector
    vec_empty = compute_embedding("", dim=128)
    assert all(v == 0.0 for v in vec_empty)


def test_semantic_similarity_ranking(temp_vector_mem):
    vm = temp_vector_mem
    doc1 = vm.add("Docker container deployment and Kubernetes cluster configuration", category="ops")
    doc2 = vm.add("Baking artisan sourdough bread with flour and water", category="cooking")
    doc3 = vm.add("Setting up container registry and Docker credentials", category="ops")

    # Query related to containers
    results = vm.search("deploy docker containers", top_k=3, min_score=0.1)
    assert len(results) >= 2
    # Ops documents should rank higher than cooking
    top_ids = [r["id"] for r in results]
    assert doc1 in top_ids or doc3 in top_ids
    assert results[0]["id"] in {doc1, doc3}
    assert results[0]["score"] > 0.25


def test_persistence_and_deletion(temp_vector_mem):
    vm = temp_vector_mem
    doc_id = vm.add("Architectural decision: use SQLite WAL for concurrent durability", category="architecture")

    # Re-open with new instance pointing to same file
    vm2 = SemanticVectorMemory(db_path=vm.path)
    item = vm2.get(doc_id)
    assert item is not None
    assert item["text"] == "Architectural decision: use SQLite WAL for concurrent durability"

    # Search in reopened DB
    hits = vm2.search("SQLite WAL concurrency", top_k=1)
    assert len(hits) == 1
    assert hits[0]["id"] == doc_id

    # Delete
    deleted = vm2.delete(doc_id)
    assert deleted is True
    assert vm2.get(doc_id) is None


def test_associative_edges(temp_vector_mem):
    vm = temp_vector_mem
    # Add two highly similar documents
    id1 = vm.add("FastAPI server endpoint routing and request handling", category="backend")
    id2 = vm.add("FastAPI server routing and HTTP response handler", category="backend")

    results = vm.search("FastAPI server routing", top_k=2)
    assert len(results) > 0
    # Should contain neighbor references
    item = [r for r in results if r["id"] == id1][0]
    neighbor_targets = [n["target_id"] for n in item["neighbors"]]
    assert id2 in neighbor_targets


def test_semantic_recall_action(temp_vector_mem, monkeypatch):
    monkeypatch.setattr("actions.semantic_recall.get_vector_memory", lambda: temp_vector_mem)

    # Store
    store_res = semantic_recall({
        "action": "store",
        "text": "Owner prefers dark theme in IDE and dashboard.",
        "category": "preference",
    })
    assert store_res.status == "success"
    doc_id = store_res.data["id"]

    # Search
    search_res = semantic_recall({
        "action": "search",
        "query": "What theme does owner like?",
        "category": "preference",
    })
    assert search_res.status == "success"
    assert len(search_res.data["matches"]) > 0

    # Delete
    del_res = semantic_recall({"action": "delete", "id": doc_id})
    assert del_res.status == "success"

    # Unauthorized access check
    with with_trust(TRUST_EXTERNAL_MESSAGE):
        with pytest.raises(PermissionError):
            semantic_recall({"action": "search", "query": "test"})
