"""Autonomous Self-Updating Knowledge Graph & Concept Association Mesh (Cycle 79).
Created and developed by Sajan Rai for Zaya.

Maintains a multi-relational associative knowledge graph linking projects, tools,
people, concepts, files, and domains. Powers associative recall, relational reasoning,
and cross-domain cognitive context.
"""
from __future__ import annotations

import collections
import json
import logging
import math
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from threading import RLock
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


@dataclass
class ConceptNode:
    id: str
    name: str
    category: str = "concept"  # "project", "tool", "person", "topic", "resource", "concept"
    attributes: Dict[str, Any] = field(default_factory=dict)
    access_count: int = 0
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ConceptNode:
        return cls(
            id=data["id"],
            name=data.get("name", data["id"]),
            category=data.get("category", "concept"),
            attributes=data.get("attributes", {}),
            access_count=data.get("access_count", 0),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
        )


@dataclass
class ConceptEdge:
    source: str
    target: str
    relation: str = "associated_with"
    weight: float = 0.5  # 0.0 to 1.0
    cooccurrence_count: int = 1
    last_reinforced: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ConceptEdge:
        return cls(
            source=data["source"],
            target=data["target"],
            relation=data.get("relation", "associated_with"),
            weight=data.get("weight", 0.5),
            cooccurrence_count=data.get("cooccurrence_count", 1),
            last_reinforced=data.get("last_reinforced", time.time()),
        )


class ConceptMesh:
    """Multi-relational associative knowledge graph with BFS paths and co-occurrence learning."""

    def __init__(self, storage_path: Optional[Path | str] = None) -> None:
        base_dir = Path(__file__).resolve().parent.parent
        self.storage_path = Path(storage_path) if storage_path else base_dir / "memory" / "concept_mesh.json"
        self._lock = RLock()
        self._nodes: Dict[str, ConceptNode] = {}
        self._edges: Dict[str, ConceptEdge] = {}  # key: f"{source}:{relation}:{target}"
        self._adj: Dict[str, List[str]] = collections.defaultdict(list)  # node_id -> list of edge keys
        self._load_from_disk()

    def _edge_key(self, source: str, relation: str, target: str) -> str:
        return f"{source.lower()}:{relation.lower()}:{target.lower()}"

    def add_node(
        self,
        node_id: str,
        name: Optional[str] = None,
        category: str = "concept",
        attributes: Optional[Dict[str, Any]] = None,
    ) -> ConceptNode:
        """Register or update a concept node."""
        nid = node_id.strip().lower()
        if not nid:
            raise ValueError("node_id cannot be empty")

        with self._lock:
            now = time.time()
            if nid in self._nodes:
                node = self._nodes[nid]
                if name:
                    node.name = name
                if category:
                    node.category = category
                if attributes:
                    node.attributes.update(attributes)
                node.updated_at = now
                node.access_count += 1
            else:
                node = ConceptNode(
                    id=nid,
                    name=name or node_id,
                    category=category,
                    attributes=attributes or {},
                    access_count=1,
                    created_at=now,
                    updated_at=now,
                )
                self._nodes[nid] = node

            self._save_to_disk()
            return node

    def link(
        self,
        source: str,
        target: str,
        relation: str = "associated_with",
        weight: float = 0.5,
        bidirectional: bool = True,
    ) -> ConceptEdge:
        """Create or reinforce a relationship between two concept nodes."""
        s = source.strip().lower()
        t = target.strip().lower()
        rel = relation.strip().lower()
        if not s or not t or s == t:
            raise ValueError("source and target must be distinct and non-empty")

        with self._lock:
            if s not in self._nodes:
                self.add_node(s)
            if t not in self._nodes:
                self.add_node(t)

            edge = self._create_or_reinforce_edge(s, t, rel, weight)
            if bidirectional:
                rev_rel = rel if rel in ("associated_with", "collaborates_with", "related_to") else f"inverse_{rel}"
                self._create_or_reinforce_edge(t, s, rev_rel, weight)

            self._save_to_disk()
            return edge

    def _create_or_reinforce_edge(self, s: str, t: str, rel: str, initial_weight: float) -> ConceptEdge:
        key = self._edge_key(s, rel, t)
        now = time.time()
        if key in self._edges:
            edge = self._edges[key]
            edge.cooccurrence_count += 1
            # Reinforce weight asymptotically towards 1.0
            edge.weight = min(1.0, edge.weight + (1.0 - edge.weight) * 0.20)
            edge.last_reinforced = now
        else:
            edge = ConceptEdge(
                source=s,
                target=t,
                relation=rel,
                weight=max(0.05, min(1.0, initial_weight)),
                cooccurrence_count=1,
                last_reinforced=now,
            )
            self._edges[key] = edge
            self._adj[s].append(key)
        return edge

    def record_cooccurrence(self, concepts: List[str], relation: str = "associated_with") -> int:
        """Reinforce mutual associations among a group of co-occurring concepts."""
        cleaned = [c.strip().lower() for c in concepts if c and c.strip()]
        unique = list(dict.fromkeys(cleaned))
        if len(unique) < 2:
            return 0

        links_created = 0
        with self._lock:
            for i in range(len(unique)):
                for j in range(i + 1, len(unique)):
                    self.link(unique[i], unique[j], relation=relation, weight=0.3, bidirectional=True)
                    links_created += 1
        return links_created

    def query_neighborhood(
        self,
        concept: str,
        depth: int = 1,
        min_weight: float = 0.1,
    ) -> Dict[str, Any]:
        """Query associative neighborhood around a central concept up to depth hops."""
        root = concept.strip().lower()
        with self._lock:
            if root not in self._nodes:
                return {"root": root, "found": False, "nodes": [], "edges": []}

            # Increment access count
            self._nodes[root].access_count += 1

            visited_nodes: Set[str] = {root}
            result_edges: List[Dict[str, Any]] = []
            queue: collections.deque[Tuple[str, int]] = collections.deque([(root, 0)])

            while queue:
                current, d = queue.popleft()
                if d >= depth:
                    continue

                for edge_key in self._adj.get(current, []):
                    edge = self._edges.get(edge_key)
                    if not edge or edge.weight < min_weight:
                        continue

                    target = edge.target
                    result_edges.append(edge.to_dict())
                    if target not in visited_nodes:
                        visited_nodes.add(target)
                        queue.append((target, d + 1))

            nodes_data = [self._nodes[nid].to_dict() for nid in visited_nodes if nid in self._nodes]
            return {
                "root": root,
                "found": True,
                "nodes": nodes_data,
                "edges": result_edges,
                "total_associations": len(result_edges),
            }

    def find_path(self, source: str, target: str, max_depth: int = 4) -> Optional[List[Dict[str, Any]]]:
        """Find the strongest shortest relational path between two concepts via BFS."""
        s = source.strip().lower()
        t = target.strip().lower()
        if s == t:
            return []

        with self._lock:
            if s not in self._nodes or t not in self._nodes:
                return None

            queue: collections.deque[Tuple[str, List[Dict[str, Any]]]] = collections.deque([(s, [])])
            visited: Set[str] = {s}

            while queue:
                curr, path = queue.popleft()
                if len(path) >= max_depth:
                    continue

                for edge_key in self._adj.get(curr, []):
                    edge = self._edges.get(edge_key)
                    if not edge:
                        continue

                    neighbor = edge.target
                    new_path = path + [edge.to_dict()]
                    if neighbor == t:
                        return new_path

                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append((neighbor, new_path))

            return None

    def get_most_central_concepts(self, top_k: int = 8) -> List[Dict[str, Any]]:
        """Rank concepts by degree centrality (connection density)."""
        with self._lock:
            rankings = []
            for nid, node in self._nodes.items():
                out_edges = self._adj.get(nid, [])
                total_weight = sum(self._edges[k].weight for k in out_edges if k in self._edges)
                rankings.append({
                    "id": nid,
                    "name": node.name,
                    "category": node.category,
                    "connections": len(out_edges),
                    "total_weight": round(total_weight, 2),
                    "access_count": node.access_count,
                })
            rankings.sort(key=lambda x: (x["connections"], x["total_weight"]), reverse=True)
            return rankings[:top_k]

    def decay_weights(self, decay_factor: float = 0.95, min_cutoff: float = 0.05) -> int:
        """Apply cognitive forgetting/decay to idle associative edges."""
        pruned_count = 0
        with self._lock:
            keys_to_delete = []
            for k, edge in self._edges.items():
                edge.weight *= decay_factor
                if edge.weight < min_cutoff:
                    keys_to_delete.append(k)

            for k in keys_to_delete:
                edge = self._edges.pop(k)
                if edge.source in self._adj and k in self._adj[edge.source]:
                    self._adj[edge.source].remove(k)
                pruned_count += 1

            if pruned_count > 0:
                self._save_to_disk()

        return pruned_count

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            categories: Dict[str, int] = collections.defaultdict(int)
            for n in self._nodes.values():
                categories[n.category] += 1

            return {
                "total_nodes": len(self._nodes),
                "total_edges": len(self._edges),
                "categories": dict(categories),
                "storage_path": str(self.storage_path),
            }

    def _save_to_disk(self) -> None:
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "nodes": {nid: n.to_dict() for nid, n in self._nodes.items()},
                "edges": {k: e.to_dict() for k, e in self._edges.items()},
            }
            tmp_path = self.storage_path.with_suffix(".tmp")
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            tmp_path.replace(self.storage_path)
        except Exception as e:
            logger.warning("Failed to save concept mesh to disk: %s", e)

    def _load_from_disk(self) -> None:
        if not self.storage_path.exists():
            return
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            raw_nodes = data.get("nodes", {})
            for nid, nd in raw_nodes.items():
                self._nodes[nid] = ConceptNode.from_dict(nd)

            raw_edges = data.get("edges", {})
            for k, ed in raw_edges.items():
                edge = ConceptEdge.from_dict(ed)
                self._edges[k] = edge
                if k not in self._adj[edge.source]:
                    self._adj[edge.source].append(k)

        except Exception as e:
            logger.warning("Failed to load concept mesh from disk: %s", e)


# ── Global Singleton ─────────────────────────────────────────────────────────

_concept_mesh: Optional[ConceptMesh] = None


def get_concept_mesh() -> ConceptMesh:
    global _concept_mesh
    if _concept_mesh is None:
        _concept_mesh = ConceptMesh()
    return _concept_mesh
