"""Semantic Vector Recall & Associative Knowledge Action for Zaya.
Created and developed by Sajan Rai.

Enables Jarvis-grade semantic concept matching, architectural memory recall,
and associative knowledge discovery across projects, decisions, and system configurations.
"""
from __future__ import annotations

from typing import Any

from core.execution_policy import require_owner
from core.tool_result import ToolResult
from memory.vector_memory import get_vector_memory


def semantic_recall(parameters: dict[str, Any], **_kwargs) -> ToolResult:
    """Execute semantic memory recall or knowledge persistence."""
    require_owner()
    action = str(parameters.get("action", "search")).lower().strip()
    vm = get_vector_memory()

    if action == "search":
        query = str(parameters.get("query", "")).strip()
        if not query:
            return ToolResult("failed", "Parameter 'query' is required for semantic search.", {})

        category = parameters.get("category")
        top_k = int(parameters.get("top_k", 5))
        min_score = float(parameters.get("min_score", 0.15))

        matches = vm.search(query=query, category=category, top_k=top_k, min_score=min_score)
        if not matches:
            return ToolResult("success", f"No semantic memories matched query '{query}'.", {"matches": []})

        summary = f"Found {len(matches)} semantic memory match(es) for '{query}'."
        evidence = [
            {"source": "vector_memory", "id": m["id"], "score": m["score"], "category": m["category"]}
            for m in matches
        ]
        return ToolResult("success", summary, {"matches": matches}, evidence=evidence)

    elif action == "store":
        text = str(parameters.get("text", "")).strip()
        if not text:
            return ToolResult("failed", "Parameter 'text' is required to store semantic memory.", {})

        category = str(parameters.get("category", "general")).strip()
        metadata = parameters.get("metadata") or {}
        doc_id = parameters.get("id")

        assigned_id = vm.add(text=text, category=category, metadata=metadata, doc_id=doc_id)
        return ToolResult(
            "success",
            f"Stored semantic memory in category '{category}' with ID: {assigned_id}.",
            {"id": assigned_id, "category": category, "text": text},
        )

    elif action == "delete":
        doc_id = str(parameters.get("id", "")).strip()
        if not doc_id:
            return ToolResult("failed", "Parameter 'id' is required to delete semantic memory.", {})

        deleted = vm.delete(doc_id)
        if deleted:
            return ToolResult("success", f"Semantic memory '{doc_id}' deleted.", {"id": doc_id})
        return ToolResult("failed", f"Semantic memory '{doc_id}' not found.", {"id": doc_id})

    return ToolResult("failed", f"Unknown action '{action}'. Valid actions are 'search', 'store', 'delete'.", {})


TOOL = {
    "name": "semantic_recall",
    "description": (
        "Search or store concepts in persistent semantic vector memory with associative relationship graph. "
        "Allows recalling notes, preferences, architectural decisions, and configurations even when words do not match lexically."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["search", "store", "delete"],
                "description": "Action to perform: 'search' (default), 'store', or 'delete'.",
            },
            "query": {
                "type": "STRING",
                "description": "Natural language concept or query to search semantically (required for 'search').",
            },
            "text": {
                "type": "STRING",
                "description": "Knowledge or decision text to persist in semantic memory (required for 'store').",
            },
            "category": {
                "type": "STRING",
                "description": "Optional category filter (e.g., 'architecture', 'preference', 'project', 'debugging').",
            },
            "id": {
                "type": "STRING",
                "description": "Explicit document ID for storing or target ID for deleting.",
            },
            "top_k": {
                "type": "INTEGER",
                "description": "Number of semantic results to return (default: 5).",
            },
            "min_score": {
                "type": "NUMBER",
                "description": "Minimum cosine similarity score threshold (default: 0.15).",
            },
        },
        "required": ["action"],
    },
    "handler": semantic_recall,
}
