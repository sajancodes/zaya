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


def _normalise_extensions(extensions: Optional[List[str]]) -> set[str]:
    """Turn a caller-supplied extension list into a comparable set.

    Accepts ".PY", "py" and ".py" alike so a mixed-case list still matches.
    """
    if not extensions:
        return set(DEFAULT_EXTS)
    out = set()
    for ext in extensions:
        if not isinstance(ext, str):
            continue
        cleaned = ext.strip().lower()
        if not cleaned:
            continue
        out.add(cleaned if cleaned.startswith(".") else f".{cleaned}")
    return out or set(DEFAULT_EXTS)


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

    exts = _normalise_extensions(extensions)

    # Check if ripgrep (rg) is installed for maximum performance
    rg_path = shutil.which("rg")
    if rg_path and root_dir.exists():
        cmd = [rg_path, "--line-number", "--no-heading", "--color", "never"]
        # Only search the requested file types. Without this the ripgrep path
        # ignored the extension filter entirely and returned matches from
        # every file in the tree, while the Python fallback filtered them.
        for ext in sorted(exts):
            cmd.extend(["-g", f"*{ext}"])
        # Mirror the Python fallback's directory exclusions so both search
        # paths agree on what counts as source code.
        for ignored in sorted(IGNORED_DIRS):
            cmd.extend(["-g", f"!{ignored}/**"])
        cmd.extend(["-g", "!.git/*"])
        if not case_sensitive:
            cmd.append("-i")
        if not is_regex:
            cmd.append("-F")
        cmd.extend(["--", query, "."])
        try:
            # cwd=root_dir keeps rg's output paths RELATIVE. Parsing an
            # absolute Windows path with split(":", 2) splits on the drive
            # letter ("C:\...\file.py:12:text" -> parts[1] is the path, not
            # the line number), which raised ValueError and silently mixed
            # half-parsed rows into the results.
            res = subprocess.run(
                cmd, capture_output=True, text=True, timeout=15, cwd=str(root_dir)
            )
            if res.returncode in (0, 1):
                found: List[Dict[str, Any]] = []
                for line in res.stdout.splitlines():
                    if len(found) >= max_results:
                        break
                    parts = line.split(":", 2)
                    if len(parts) < 3:
                        continue
                    path_part, line_part, content = parts
                    try:
                        line_no = int(line_part)
                    except ValueError:
                        continue
                    if path_part.startswith(".\\") or path_part.startswith("./"):
                        path_part = path_part[2:]
                    # Authoritative filter, in case a glob ever lets a
                    # non-matching file through.
                    if Path(path_part).suffix.lower() not in exts:
                        continue
                    found.append({
                        "file": path_part,
                        "line": line_no,
                        "content": content.strip()
                    })
                return found
        except Exception:
            pass  # Fallback to pure Python search

    # Python native search fallback
    for root, dirs, files in os.walk(root_dir):
        # Prune ignored directories
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS and not d.startswith(".")]

        for fname in files:
            p = Path(root) / fname
            # The extension filter must apply in BOTH modes. The old guard
            # ("... and extensions is not None") made the default extension
            # list dead code, so every file in the tree was scanned.
            if p.suffix.lower() not in exts:
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
    query = str(parameters.get("query", "") or "").strip()
    if not query:
        return json.dumps({"status": "error", "message": "Search query cannot be empty."})

    search_path_str = parameters.get("path", "")
    base = Path(search_path_str) if search_path_str else get_base_dir()
    if not base.exists():
        base = get_base_dir()

    is_regex = bool(parameters.get("is_regex", False))
    case_sensitive = bool(parameters.get("case_sensitive", False))
    extensions = parameters.get("extensions")
    try:
        max_results = int(parameters.get("max_results", 50))
    except (TypeError, ValueError):
        max_results = 50
    max_results = max(1, min(max_results, 1000))

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
