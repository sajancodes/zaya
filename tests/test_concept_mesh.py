"""Tests for Autonomous Self-Updating Knowledge Graph & Concept Association Mesh (Cycle 79).
Created and developed by Sajan Rai for Zaya.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
import pytest

from core.concept_mesh import ConceptMesh, get_concept_mesh
from actions.concept_mesh_action import handle_concept_mesh


class TestConceptMesh:
    @pytest.fixture
    def temp_mesh(self):
        with tempfile.TemporaryDirectory() as td:
            storage = Path(td) / "test_mesh.json"
            yield ConceptMesh(storage_path=storage)

    def test_add_node_and_update(self, temp_mesh):
        node = temp_mesh.add_node("zaya", name="Zaya Assistant", category="project", attributes={"version": "2.0"})
        assert node.id == "zaya"
        assert node.name == "Zaya Assistant"
        assert node.category == "project"
        assert node.attributes["version"] == "2.0"
        assert node.access_count == 1

        # Re-adding updates access count and attributes
        updated = temp_mesh.add_node("zaya", attributes={"status": "online"})
        assert updated.access_count == 2
        assert updated.attributes["version"] == "2.0"
        assert updated.attributes["status"] == "online"

    def test_link_and_neighborhood_query(self, temp_mesh):
        temp_mesh.link("zaya", "python", relation="built_with", weight=0.8, bidirectional=True)
        temp_mesh.link("zaya", "gemini", relation="uses_model", weight=0.9, bidirectional=True)
        temp_mesh.link("gemini", "multimodal", relation="capability", weight=0.7, bidirectional=True)

        # Depth 1 neighborhood around zaya
        res1 = temp_mesh.query_neighborhood("zaya", depth=1)
        assert res1["found"] is True
        node_ids = {n["id"] for n in res1["nodes"]}
        assert "zaya" in node_ids
        assert "python" in node_ids
        assert "gemini" in node_ids
        assert "multimodal" not in node_ids

        # Depth 2 neighborhood includes multimodal
        res2 = temp_mesh.query_neighborhood("zaya", depth=2)
        node_ids2 = {n["id"] for n in res2["nodes"]}
        assert "multimodal" in node_ids2

    def test_find_path_bfs(self, temp_mesh):
        temp_mesh.link("a", "b", relation="connects", weight=0.5)
        temp_mesh.link("b", "c", relation="connects", weight=0.5)
        temp_mesh.link("c", "d", relation="connects", weight=0.5)

        path = temp_mesh.find_path("a", "d")
        assert path is not None
        assert len(path) == 3
        assert path[0]["source"] == "a"
        assert path[0]["target"] == "b"
        assert path[2]["source"] == "c"
        assert path[2]["target"] == "d"

        # No path to unconnected node
        temp_mesh.add_node("orphan")
        assert temp_mesh.find_path("a", "orphan") is None

    def test_record_cooccurrence(self, temp_mesh):
        count = temp_mesh.record_cooccurrence(["fastapi", "uvicorn", "docker"])
        assert count == 3  # (fastapi, uvicorn), (fastapi, docker), (uvicorn, docker)

        stats = temp_mesh.get_stats()
        assert stats["total_nodes"] == 3
        # Each pair was linked bidirectionally (6 directed edges)
        assert stats["total_edges"] == 6

    def test_centrality_and_decay(self, temp_mesh):
        temp_mesh.link("hub", "leaf1", weight=0.5)
        temp_mesh.link("hub", "leaf2", weight=0.5)
        temp_mesh.link("hub", "leaf3", weight=0.5)

        central = temp_mesh.get_most_central_concepts(top_k=1)
        assert len(central) == 1
        assert central[0]["id"] == "hub"
        assert central[0]["connections"] == 3

        # Decay edges
        pruned = temp_mesh.decay_weights(decay_factor=0.01, min_cutoff=0.05)
        assert pruned > 0
        stats = temp_mesh.get_stats()
        assert stats["total_edges"] == 0

    def test_persistence_reload(self, temp_mesh):
        temp_mesh.add_node("persisted_node", category="project")
        temp_mesh.link("persisted_node", "persisted_target", relation="links_to")

        # Reload new mesh instance from same path
        new_mesh = ConceptMesh(storage_path=temp_mesh.storage_path)
        stats = new_mesh.get_stats()
        assert stats["total_nodes"] == 2
        assert stats["total_edges"] == 2


class TestConceptMeshAction:
    def test_action_flow(self):
        # Stats
        res = handle_concept_mesh(action="stats")
        data = json.loads(res)
        assert data["status"] == "success"

        # Link
        res2 = handle_concept_mesh(
            action="link",
            concept="zaya_agent",
            target="subagent_swarm",
            relation="coordinates",
            weight=0.85,
        )
        data2 = json.loads(res2)
        assert data2["status"] == "success"
        assert "zaya_agent" in data2["message"]

        # Query
        res3 = handle_concept_mesh(action="query", concept="zaya_agent")
        data3 = json.loads(res3)
        assert data3["status"] == "success"
        assert data3["result"]["found"] is True

        # Find Path
        res4 = handle_concept_mesh(action="find_path", concept="zaya_agent", target="subagent_swarm")
        data4 = json.loads(res4)
        assert data4["status"] == "success"
        assert data4["steps"] == 1

        # Central concepts
        res5 = handle_concept_mesh(action="central_concepts")
        data5 = json.loads(res5)
        assert data5["status"] == "success"
        assert "central_concepts" in data5
