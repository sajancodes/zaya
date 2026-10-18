"""Locate the OpenCode CLI that Zaya drives in a hidden terminal.

OpenCode ships in more than one place on a developer machine, and they are not
interchangeable:

* ``%APPDATA%\\ai.opencode.desktop\\cli\\<version>-<arch>\\opencode-cli.exe`` is
  the build the desktop application provisions and keeps current. It matches the
  session database that is actually in use. The version folder changes without
  notice, so it is discovered rather than hard-coded.
* A global npm install may be an older major that cannot read that database
  (it refuses with "Database is not empty and has no session table").

Resolution prefers the desktop build and picks the newest version folder. The
binary is only trusted once it answers ``--version``. Everything here is
argv-only and windowless so a job can never flash a console.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import threading
from pathlib import Path

_HIDDEN = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
_PROBE_TIMEOUT = 25.0
_VERSION_RE = re.compile(r"(\d+)\.(\d+)\.(\d+)")

_cache: "CliInfo | None" = None
_cache_lock = threading.Lock()


class CliMissing(RuntimeError):
    """Raised when no usable OpenCode CLI can be found."""


def version_key(text: str) -> tuple[int, int, int]:
    match = _VERSION_RE.search(text or "")
    return tuple(int(part) for part in match.groups()) if match else (0, 0, 0)


def desktop_cli_binaries() -> list[Path]:
    """Every packaged desktop CLI, newest first."""
    appdata = os.environ.get("APPDATA")
    if not appdata:
        return []
    root = Path(appdata) / "ai.opencode.desktop" / "cli"
    if not root.is_dir():
        return []
    found = [folder / "opencode-cli.exe" for folder in root.iterdir() if (folder / "opencode-cli.exe").is_file()]
    found.sort(key=lambda path: version_key(path.parent.name), reverse=True)
    return found


def candidate_binaries() -> list[Path]:
    """Ordered candidates. Only real executables are returned: a ``.cmd`` shim
    cannot be launched without a shell, which the runner refuses to use."""
    ordered: list[Path] = list(desktop_cli_binaries())
    for name in (("opencode-cli.exe", "opencode.exe") if os.name == 'nt' else ('opencode',)):
        located = shutil.which(name)
        if located:
            ordered.append(Path(located))
    npm_bin = Path(os.environ.get("APPDATA") or "") / "npm" / "node_modules" / "opencode-ai" / "bin" / "opencode.exe"
    if npm_bin.is_file():
        ordered.append(npm_bin)
    npm_cli = Path(os.environ.get("APPDATA") or "") / "npm" / "node_modules" / "@opencode" / "cli" / "bin" / "opencode.exe"
    if npm_cli.is_file():
        ordered.append(npm_cli)
    unique: list[Path] = []
    for path in ordered:
        if path not in unique:
            unique.append(path)
    return unique


def probe(binary: Path, timeout: float = _PROBE_TIMEOUT) -> str:
    """Return the version string, or raise ``CliMissing``/``RuntimeError``."""
    try:
        result = subprocess.run([str(binary), "--version"], capture_output=True, text=True,
                                encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL,
                                timeout=timeout, **_HIDDEN)
    except (OSError, subprocess.SubprocessError) as error:
        raise CliMissing(f"OpenCode CLI could not be started ({binary}): {error}") from error
    version = (result.stdout or "").strip() or (result.stderr or "").strip()
    if result.returncode != 0 or not version:
        raise CliMissing(f"OpenCode CLI did not answer --version ({binary}).")
    return version.splitlines()[0].strip()


class CliInfo:
    """A verified CLI binary and the version it reported."""

    __slots__ = ("path", "version")

    def __init__(self, path: Path, version: str) -> None:
        self.path = path
        self.version = version

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"CliInfo(path={str(self.path)!r}, version={self.version!r})"


def resolve(refresh: bool = False) -> CliInfo:
    """Find and verify a usable CLI. Result is cached; ``refresh`` re-probes."""
    global _cache
    with _cache_lock:
        if _cache is not None and not refresh:
            return _cache
        errors: list[str] = []
        for binary in candidate_binaries():
            if os.name == 'nt' and binary.suffix.lower() != ".exe":
                continue
            try:
                version = probe(binary)
            except (CliMissing, RuntimeError) as error:
                errors.append(str(error))
                continue
            _cache = CliInfo(binary, version)
            return _cache
    detail = "; ".join(errors) if errors else "no opencode executable was found on this machine"
    raise CliMissing(f"OpenCode is not available: {detail}")
