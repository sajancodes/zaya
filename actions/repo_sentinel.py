"""Developer Git Repo Telemetry & Workspace Health Sentinel.
Created and developed by Sajan Rai for Zaya.

Inspects Git repository health, uncommitted/untracked changes, upstream sync state,
scans workspace directories for dirty working trees, and provides fast reflex git status.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
from typing import Any, Dict, List, Optional

from core.execution_policy import require_owner


def _run_git(args: List[str], cwd: Optional[Path] = None, timeout: float = 3.0) -> Optional[str]:
    """Execute a git command with timeout and return trimmed stdout."""
    target_dir = cwd or Path.cwd()
    try:
        proc = subprocess.run(
            ["git"] + args,
            cwd=str(target_dir),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if proc.returncode == 0:
            return proc.stdout.strip()
    except Exception:
        pass
    return None


def _inspect_repo_status(repo_dir: Optional[Path] = None) -> Dict[str, Any]:
    """Parse git status, sync state, and last commit into structured telemetry."""
    cwd = (repo_dir or Path.cwd()).resolve()
    raw_status = _run_git(["status", "--porcelain=v1", "-b"], cwd=cwd)

    if raw_status is None:
        return {"is_git_repo": False, "path": str(cwd), "message": "Not a valid Git repository."}

    lines = raw_status.splitlines()
    branch_line = lines[0] if lines else "## Unknown"

    # Parse branch and upstream tracking: ## main...origin/main [ahead 1, behind 2]
    branch = "HEAD (detached)"
    upstream = ""
    ahead = 0
    behind = 0

    m_branch = re.match(r"^##\s+(.+?)(?:\.\.\.([^\s\[]+))?(?:\s+\[(.*)\])?$", branch_line)
    if m_branch:
        branch = m_branch.group(1).strip()
        upstream = m_branch.group(2) or ""
        sync_meta = m_branch.group(3) or ""
        m_ahead = re.search(r"ahead\s+(\d+)", sync_meta)
        if m_ahead:
            ahead = int(m_ahead.group(1))
        m_behind = re.search(r"behind\s+(\d+)", sync_meta)
        if m_behind:
            behind = int(m_behind.group(1))

    staged_count = 0
    unstaged_count = 0
    untracked_count = 0

    for line in lines[1:]:
        if len(line) >= 2:
            idx, work = line[0], line[1]
            if idx == "?" and work == "?":
                untracked_count += 1
            else:
                if idx in ("M", "A", "D", "R", "C"):
                    staged_count += 1
                if work in ("M", "D"):
                    unstaged_count += 1

    clean = (staged_count == 0 and unstaged_count == 0 and untracked_count == 0)

    # Last commit details
    raw_log = _run_git(["log", "-1", "--format=%h|%an|%ar|%s"], cwd=cwd)
    last_commit = None
    if raw_log:
        parts = raw_log.split("|", 3)
        if len(parts) == 4:
            last_commit = {
                "hash": parts[0],
                "author": parts[1],
                "time": parts[2],
                "message": parts[3],
            }

    return {
        "is_git_repo": True,
        "repo_name": cwd.name,
        "path": str(cwd),
        "branch": branch,
        "upstream": upstream,
        "ahead": ahead,
        "behind": behind,
        "clean": clean,
        "staged_count": staged_count,
        "unstaged_count": unstaged_count,
        "untracked_count": untracked_count,
        "last_commit": last_commit,
    }


def _scan_workspaces(root_dir: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Scan parent or Desktop directory for active git repos."""
    root = (root_dir or Path.cwd().parent).resolve()
    repos = []

    try:
        # Check current repo first
        if (Path.cwd() / ".git").exists():
            repos.append(_inspect_repo_status(Path.cwd()))

        # Check sibling directories
        for item in root.iterdir():
            if item.is_dir() and item != Path.cwd() and (item / ".git").exists():
                st = _inspect_repo_status(item)
                if st.get("is_git_repo"):
                    repos.append(st)
    except Exception:
        pass

    return repos


def _get_recent_commits(limit: int = 5, repo_dir: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Return recent commits formatted as structured dictionaries."""
    raw = _run_git(["log", f"-{limit}", "--format=%h|%an|%ar|%s"], cwd=repo_dir)
    commits = []
    if raw:
        for line in raw.splitlines():
            parts = line.split("|", 3)
            if len(parts) == 4:
                commits.append({
                    "hash": parts[0],
                    "author": parts[1],
                    "time": parts[2],
                    "message": parts[3],
                })
    return commits


def _get_branch_list(repo_dir: Optional[Path] = None) -> List[Dict[str, Any]]:
    """List local and remote tracking branches with commit hash and message."""
    raw = _run_git(["branch", "-vv", "--no-color"], cwd=repo_dir)
    branches = []
    if raw:
        for line in raw.splitlines():
            is_current = line.startswith("*")
            clean_line = line.lstrip("* ").strip()
            parts = clean_line.split(None, 2)
            if len(parts) >= 2:
                name = parts[0]
                commit_hash = parts[1]
                extra = parts[2] if len(parts) > 2 else ""
                branches.append({
                    "name": name,
                    "current": is_current,
                    "commit": commit_hash,
                    "tracking": extra,
                })
    return branches


def repo_sentinel(parameters: dict, **_kwargs) -> str:
    """Dispatches Git status, workspace scanning, and branch/commit inspection."""
    require_owner()
    action = str(parameters.get("action") or "status").lower().strip()
    target_path = parameters.get("path") or parameters.get("repo_path")
    repo_dir = Path(target_path).resolve() if target_path else Path.cwd()

    # 1. Single Repo Status
    if action in ("status", "check"):
        st = _inspect_repo_status(repo_dir)
        if not st.get("is_git_repo"):
            return json.dumps({"status": "error", "message": f"'{repo_dir}' is not a valid Git repository."}, indent=2)

        sync_str = "in sync with origin"
        if st["ahead"] > 0:
            sync_str = f"ahead of origin by {st['ahead']} commit(s)"
        elif st["behind"] > 0:
            sync_str = f"behind origin by {st['behind']} commit(s)"

        state_str = "clean" if st["clean"] else f"{st['unstaged_count'] + st['staged_count']} modified, {st['untracked_count']} untracked"
        summary = f"Repo '{st['repo_name']}': on branch '{st['branch']}' ({state_str}, {sync_str})."
        if st.get("last_commit"):
            summary += f" Latest commit: {st['last_commit']['hash']} ({st['last_commit']['message']}) by {st['last_commit']['author']}."

        return json.dumps({"status": "success", "summary": summary, "data": st}, indent=2)

    # 2. Scan Workspace for Multiple Repos
    if action in ("scan", "scan_workspaces", "workspaces"):
        root_path = Path(parameters.get("root_dir")).resolve() if parameters.get("root_dir") else None
        repos = _scan_workspaces(root_path)
        dirty = [r["repo_name"] for r in repos if not r.get("clean")]
        clean_count = len(repos) - len(dirty)
        summary = f"Scanned {len(repos)} repository(s): {clean_count} clean, {len(dirty)} with uncommitted changes" + (f" ({', '.join(dirty)})" if dirty else "") + "."
        return json.dumps({"status": "success", "summary": summary, "data": repos}, indent=2)

    # 3. Recent Commits
    if action in ("commits", "recent_commits", "log"):
        limit = max(1, min(int(parameters.get("limit") or 5), 30))
        commits = _get_recent_commits(limit, repo_dir)
        summary = f"Recent {len(commits)} commit(s) on '{repo_dir.name}': " + "; ".join(f"{c['hash']} '{c['message']}' ({c['time']})" for c in commits[:3])
        return json.dumps({"status": "success", "summary": summary, "data": commits}, indent=2)

    # 4. Branch List
    if action in ("branches", "branch_list"):
        branches = _get_branch_list(repo_dir)
        curr = next((b["name"] for b in branches if b.get("current")), "Unknown")
        summary = f"Repository '{repo_dir.name}' has {len(branches)} branch(es). Current branch: '{curr}'."
        return json.dumps({"status": "success", "summary": summary, "data": branches}, indent=2)

    return json.dumps({
        "status": "error",
        "message": f"Unknown action '{action}'. Choose from: status, scan_workspaces, recent_commits, branch_list."
    }, indent=2)


TOOL = {
    "name": "repo_sentinel",
    "description": "Inspect Git repository health, track uncommitted/untracked changes, verify upstream sync status, scan developer workspaces, and review branch histories.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["status", "scan_workspaces", "recent_commits", "branch_list"],
                "description": "Git inspection action (default: 'status').",
            },
            "path": {
                "type": "STRING",
                "description": "Repository path to inspect (default: active workspace).",
            },
            "limit": {
                "type": "INTEGER",
                "description": "Maximum number of commits or branches to return.",
            },
        },
    },
    "handler": repo_sentinel,
}
