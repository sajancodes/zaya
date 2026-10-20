"""Fast Local Code Search.
Created and developed by Sajan Rai for Zaya.
Search filenames and code text directly, with exact file paths and line numbers.
Fast, local, zero-indexing, and no model downloads required.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.execution_policy import require_owner
from core.tool_result import ToolResult

IGNORED_DIRS = {
    ".git", ".venv", "venv", "__pycache__", "node_modules",
    ".idea", ".vscode", "build", "dist", ".gradle", "target",
    ".pytest_cache", ".ruff_cache", "logs", "assets", ".mypy_cache"
}

DEFAULT_EXTS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css", ".json",
    ".md", ".txt", ".kt", ".java", ".cpp", ".c", ".h", ".rs", ".go",
    ".sh", ".ps1", ".yaml", ".yml", ".toml", ".xml", ".gradle"
}


def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


def search_code_in_directory(
    root_dir: Path,
    query: str,
    is_regex: bool = False,
    case_sensitive: bool = False,
    extensions: Optional[List[str]] = None,
    max_results: int = 100
) -> List[Dict[str, Any]]:
    """Recursively searches text files in root_dir for matches."""
    matches = []
    flags = 0 if case_sensitive else re.IGNORECASE

    try:
        if is_regex:
            pattern = re.compile(query, flags)
        else:
            pattern = re.compile(re.escape(query), flags)
    except re.error as e:
        return [{"error": f"Invalid regex pattern: {e}"}]

    exts = set(extensions) if extensions else DEFAULT_EXTS

    # Check if ripgrep (rg) is installed for maximum performance
    rg_path = shutil.which("rg")
    if rg_path and root_dir.exists():
        cmd = [rg_path, "--line-number", "--no-heading", "--color", "never", "-g", "!.git/*"]
        if not case_sensitive:
            cmd.append("-i")
        if not is_regex:
            cmd.append("-F")
        cmd.extend([query, str(root_dir)])
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            if res.returncode in (0, 1):
                for line in res.stdout.splitlines()[:max_results]:
                    parts = line.split(":", 2)
                    if len(parts) >= 3:
                        try:
                            rel = str(Path(parts[0]).relative_to(root_dir))
                        except Exception:
                            rel = parts[0]
                        matches.append({
                            "file": rel,
                            "line": int(parts[1]),
                            "content": parts[2].strip()
                        })
                return matches
        except Exception:
            pass  # Fallback to pure Python search

    # Python native search fallback
    for root, dirs, files in os.walk(root_dir):
        # Prune ignored directories
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS and not d.startswith(".")]

        for fname in files:
            p = Path(root) / fname
            if p.suffix.lower() not in exts and extensions is not None:
                continue

            try:
                # Limit single file size to 2MB to keep scanning instant
                if p.stat().st_size > 2 * 1024 * 1024:
                    continue

                with open(p, "r", encoding="utf-8", errors="ignore") as f:
                    for line_num, line_str in enumerate(f, 1):
                        if pattern.search(line_str):
                            try:
                                rel = str(p.relative_to(root_dir))
                            except Exception:
                                rel = str(p)
                            matches.append({
                                "file": rel,
                                "line": line_num,
                                "content": line_str.strip()[:200]
                            })
                            if len(matches) >= max_results:
                                return matches
            except Exception:
                continue

    return matches


def fast_code_search(parameters: dict, **_kwargs) -> str:
    """Fast Local Code Search Action."""
    require_owner()
    query = parameters.get("query", "").strip()
    if not query:
        return json.dumps({"status": "error", "message": "Search query cannot be empty."})

    search_path_str = parameters.get("path", "")
    base = Path(search_path_str) if search_path_str else get_base_dir()
    if not base.exists():
        base = get_base_dir()

    is_regex = bool(parameters.get("is_regex", False))
    case_sensitive = bool(parameters.get("case_sensitive", False))
    extensions = parameters.get("extensions")
    max_results = int(parameters.get("max_results", 50))

    results = search_code_in_directory(
        root_dir=base,
        query=query,
        is_regex=is_regex,
        case_sensitive=case_sensitive,
        extensions=extensions,
        max_results=max_results
    )

    return json.dumps({
        "status": "success",
        "query": query,
        "searched_path": str(base),
        "count": len(results),
        "matches": results
    }, indent=2)


TOOL = {
    "name": "fast_code_search",
    "description": "Fast Local Code Search: Search filenames and code text directly across project directories, with file paths and line numbers. No indexing or model downloads.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "query": {
                "type": "STRING",
                "description": "The string or regex pattern to search for."
            },
            "path": {
                "type": "STRING",
                "description": "Directory path to search. Defaults to project root."
            },
            "is_regex": {
                "type": "BOOLEAN",
                "description": "Whether query should be evaluated as a regex."
            },
            "case_sensitive": {
                "type": "BOOLEAN",
                "description": "Whether search is case-sensitive (default: False)."
            },
            "extensions": {
                "type": "ARRAY",
                "items": {"type": "STRING"},
                "description": "Optional list of file extensions to include, e.g. ['.py', '.ts']."
            }
        },
        "required": ["query"]
    },
    "handler": fast_code_search
}
