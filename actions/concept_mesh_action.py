"""Concept Association Mesh Action — Multi-Relational Knowledge Graph (Cycle 79).
Created and developed by Sajan Rai for Zaya.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from core.concept_mesh import get_concept_mesh


def handle_concept_mesh(
    action: str = "stats",
    concept: str = "",
    target: str = "",
    relation: str = "associated_with",
    category: str = "concept",
    weight: float = 0.5,
    depth: int = 1,
    concepts: Optional[List[str]] = None,
) -> str:
    """Query, link, or traverse associative knowledge nodes and relational paths."""
    mesh = get_concept_mesh()

    if action == "query":
        if not concept:
            return "Please provide a 'concept' to query."
        res = mesh.query_neighborhood(concept, depth=depth)
        return json.dumps({"status": "success", "result": res})

    elif action == "link":
        if not concept or not target:
            return "Both 'concept' (source) and 'target' are required to create a link."
        edge = mesh.link(concept, target, relation=relation, weight=weight)
        return json.dumps({
            "status": "success",
            "message": f"Linked '{concept}' to '{target}' via '{relation}'.",
            "edge": edge.to_dict(),
        })

    elif action == "find_path":
        if not concept or not target:
            return "Both 'concept' (source) and 'target' are required to find a path."
        path = mesh.find_path(concept, target, max_depth=max(2, depth))
        if path is None:
            return json.dumps({"status": "not_found", "message": f"No path found between '{concept}' and '{target}'."})
        return json.dumps({"status": "success", "path": path, "steps": len(path)})

    elif action == "record_cooccurrence":
        items = concepts or []
        if isinstance(items, str):
            items = [s.strip() for s in items.split(",") if s.strip()]
        count = mesh.record_cooccurrence(items, relation=relation)
        return json.dumps({
            "status": "success",
            "message": f"Recorded co-occurrence for {len(items)} concepts.",
            "links_reinforced": count,
        })

    elif action == "central_concepts":
        rankings = mesh.get_most_central_concepts(top_k=8)
        return json.dumps({"status": "success", "central_concepts": rankings})

    elif action == "stats":
        stats = mesh.get_stats()
        return json.dumps({"status": "success", "stats": stats})

    return f"Unknown concept mesh action: '{action}'."


TOOL = {
    "name": "concept_mesh",
    "description": (
        "Interact with Zaya's multi-relational Knowledge Graph & Concept Association Mesh. "
        "Allows associative recall, neighborhood graph exploration, pathfinding between concepts, "
        "and relationship reinforcement."
    ),
    "handler": handle_concept_mesh,
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["query", "link", "find_path", "record_cooccurrence", "central_concepts", "stats"],
                "description": "Action to perform on the concept mesh.",
            },
            "concept": {
                "type": "STRING",
                "description": "Source concept identifier or name (e.g. 'zaya', 'github', 'python').",
            },
            "target": {
                "type": "STRING",
                "description": "Target concept identifier for linking or pathfinding.",
            },
            "relation": {
                "type": "STRING",
                "description": "Relational type (e.g. 'depends_on', 'uses', 'associated_with', 'part_of').",
            },
            "category": {
                "type": "STRING",
                "description": "Category for the concept node (project, tool, person, topic, resource).",
            },
            "weight": {
                "type": "NUMBER",
                "description": "Initial association weight (0.0 to 1.0).",
            },
            "depth": {
                "type": "INTEGER",
                "description": "Graph neighborhood traversal depth or max path depth (default 1).",
            },
            "concepts": {
                "type": "ARRAY",
                "items": {"type": "STRING"},
                "description": "List of concept strings for co-occurrence reinforcement.",
            },
        },
        "required": ["action"],
    },
}
