"""Resolve working directories for coding and software setup jobs.

Owner-approved roots are searched; an explicit absolute path is accepted but
still validated. The whole home directory is never scanned. A job is only
started against something that actually looks like a project or repository,
unless a new project was requested. Software setup can instead use home or an
existing approved directory without adding home to the coding roots.
"""
from __future__ import annotations

import os
from pathlib import Path

APPROVED_ROOTS = (
    Path.home() / "Desktop" / "ZayaProjects",
    Path.home() / "Desktop",
    Path.home() / "Documents",
    Path.home() / "dev",
)

# Markers that make a directory a believable project. One is enough.
PROJECT_MARKERS = (
    ".git", "pyproject.toml", "setup.py", "setup.cfg", "requirements.txt", "tox.ini",
    "package.json", "tsconfig.json", "Cargo.toml", "go.mod", "pom.xml", "build.gradle",
    "Gemfile", "composer.json", "CMakeLists.txt", "Makefile", "*.sln", "*.csproj",
    ".opencode", "opencode.json", "opencode.jsonc", "AGENTS.md", "readme.md",
)

SOURCE_SUFFIXES = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".cs", ".c", ".cpp", ".h", ".hpp",
    ".go", ".rs", ".rb", ".php", ".swift", ".kt", ".sh", ".ps1", ".sql", ".html",
}


class ProjectError(ValueError):
    """The requested project could not be resolved to a safe directory."""


def approved_roots() -> list[Path]:
    seen: list[Path] = []
    for root in APPROVED_ROOTS:
        try:
            resolved = root.expanduser().resolve()
        except OSError:
            continue
        if resolved not in seen:
            seen.append(resolved)
    return seen


def is_within(path: Path, root: Path) -> bool:
    """True when ``path`` equals ``root`` or sits inside it."""
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (ValueError, OSError):
        return False


def looks_like_project(directory: Path) -> bool:
    """A directory that plausibly holds code: a marker file, or source files."""
    if not directory.is_dir():
        return False
    try:
        entries = list(directory.iterdir())
    except OSError:
        return False
    names = {entry.name.lower() for entry in entries}
    for marker in PROJECT_MARKERS:
        if marker.startswith("*"):
            if any(n.endswith(marker[1:].lower()) for n in names):
                return True
        elif marker.lower() in names:
            return True
    for entry in entries:
        if entry.is_file() and entry.suffix.lower() in SOURCE_SUFFIXES:
            return True
    return False


def find_named_project(name: str) -> list[Path]:
    """Directories under an approved root whose name matches ``name``.

    Only direct children are considered, so nothing under the home directory is
    walked. ``name`` is compared case-insensitively, ignoring surrounding space.
    """
    wanted = name.strip().strip('"').strip("'").lower().replace("\\", "/").rstrip("/").split("/")[-1]
    if not wanted:
        return []
    matches: list[Path] = []
    for root in approved_roots():
        if not root.is_dir():
            continue
        try:
            children = sorted(root.iterdir())
        except OSError:
            continue
        for child in children:
            if child.is_dir() and child.name.lower() == wanted and child not in matches:
                matches.append(child)
    return matches


def resolve_project(requested: str, *, allow_empty: bool = False) -> Path:
    """Return the validated project directory for ``requested``.

    ``requested`` may be an absolute path the owner supplied, or a folder name
    found under an approved root. Raises ``ProjectError`` with a sentence Zaya
    can say when it cannot be resolved safely.
    """
    text = (requested or "").strip().strip('"').strip("'")
    if not text:
        raise ProjectError("I need to know which project directory to work in.")

    expanded = Path(os.path.expandvars(os.path.expanduser(text)))
    candidates: list[Path] = []

    if expanded.is_absolute():
        explicit = expanded
        if not explicit.exists():
            raise ProjectError(f"There is no directory at {explicit}.")
        if not is_within(explicit, explicit) or not explicit.is_dir():
            raise ProjectError(f"{explicit} is not a directory.")
        candidates.append(explicit)
    else:
        candidates.extend(find_named_project(text))

    if not candidates:
        roots = ", ".join(str(root) for root in approved_roots() if root.is_dir())
        raise ProjectError(
            f"I could not find a project called '{text}'. I look in: {roots}. "
            f"Give me an absolute path if it lives somewhere else."
        )

    if len(candidates) > 1:
        raise ProjectError('More than one project has that name. Give me the exact directory.')
    project = candidates[0].resolve()
    if not any(is_within(project, root) for root in approved_roots()):
        raise ProjectError(f"{project} is outside the folders I am allowed to code in.")
    if not allow_empty and not looks_like_project(project):
        raise ProjectError(f"{project} does not look like a project or repository.")
    return project


def prepare_project(requested: str, *, create: bool = False) -> Path:
    """Create a specifically requested new project, without overwriting files."""
    if not create:
        return resolve_project(requested)
    text = (requested or '').strip().strip('"').strip("'")
    path = Path(os.path.expandvars(os.path.expanduser(text)))
    if not text or (not path.is_absolute() and (path.name != text or text in {'.', '..'})):
        raise ProjectError('Give me a project folder name or an absolute directory.')
    target = (path if path.is_absolute() else approved_roots()[0] / path).resolve()
    if not any(is_within(target, root) and target != root for root in approved_roots()):
        raise ProjectError('The new project must be a folder inside an approved project root.')
    target.mkdir(parents=True, exist_ok=True)
    return resolve_project(str(target), allow_empty=True)


def contains(project: Path, other: str | Path) -> bool:
    """True when ``other`` (absolute or relative) stays inside ``project``."""
    raw = Path(str(other)).expanduser()
    candidate = raw if raw.is_absolute() else project / raw
    return is_within(candidate, project)


def prepare_workspace(requested: str, *, purpose: str = 'coding', create: bool = False) -> Path:
    """Setup may use home as cwd without making home a general coding root.

    This is working-directory selection, not a sandbox for the child process.
    Installer destinations are governed by the owner request and CLI permissions.
    """
    if purpose not in {'coding', 'setup'}:
        raise ProjectError('Use coding or setup as the task purpose.')
    if purpose == 'coding':
        return prepare_project(requested, create=create)
    if create:
        raise ProjectError('Software setup uses an existing directory; do not create a project.')
    text = (requested or '').strip().strip('"').strip("'")
    home = Path.home().resolve()
    candidate = home if text.lower() in {'', '~', 'home'} else Path(os.path.expandvars(os.path.expanduser(text)))
    if candidate.is_absolute() and candidate.resolve() == home and home.is_dir():
        return home
    return resolve_project(text, allow_empty=True)
