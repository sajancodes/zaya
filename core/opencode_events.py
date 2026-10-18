"""Parse the NDJSON event stream that ``opencode run --format json`` writes.

The stream is line-delimited JSON emitted on stdout. Each record is::

    {"type": "...", "timestamp": 169..., "sessionID": "ses_...", "part": {...}}

Observed record types (OpenCode 2.0.x):

* ``step_start``  / ``step_finish`` — one model/tool step; ``part.reason`` says
  why the step ended.
* ``text``        — the assistant's prose. ``part.text``.
* ``tool_use``    — a tool call. ``part.tool`` names it (read/edit/write/patch/
  shell/grep/glob/...), ``part.state.status`` is completed/running/error, and
  ``part.state.input`` / ``output`` / ``metadata`` carry the detail.

The parser never trusts the shape: unknown record types, missing keys, partial
lines and unparseable JSON all degrade to a safe value instead of raising. Raw
tool output is not kept — only bounded, structured fields — so nothing that
could contain source text or secrets reaches narration or the job store.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Iterable, Iterator

MAX_TEXT = 1500
MAX_COMMAND = 800
MAX_PATH = 512

FILE_TOOLS = {"read", "edit", "write", "patch"}
CHANGE_TOOLS = {"edit", "write", "patch"}


@dataclass(frozen=True)
class Event:
    """One normalised stream record."""

    kind: str = "unknown"          # step_start | step_finish | text | tool | unknown
    session_id: str = ""
    tool: str = ""
    status: str = ""               # completed | running | error | pending
    text: str = ""
    command: str = ""
    path: str = ""
    title: str = ""
    files: tuple[str, ...] = ()
    additions: int = 0
    deletions: int = 0
    error: str = ""
    reason: str = ""
    exit_code: int | None = None
    timestamp: float = 0.0
    id: str = ""

    @property
    def is_tool(self) -> bool:
        return self.kind == "tool"

    @property
    def is_change(self) -> bool:
        return self.kind == "tool" and self.tool in CHANGE_TOOLS

    @property
    def failed(self) -> bool:
        return self.status == "error"


def _text(value, limit: int) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        value = str(value)
    value = value.strip()
    return value if len(value) <= limit else value[:limit]


def _files(metadata: dict) -> tuple[tuple[str, ...], int, int]:
    names: list[str] = []
    additions = deletions = 0
    raw = metadata.get("files") if isinstance(metadata, dict) else None
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            name = _text(item.get("file"), MAX_PATH)
            if name and name not in names:
                names.append(name)
            try:
                additions += int(item.get("additions") or 0)
                deletions += int(item.get("deletions") or 0)
            except (TypeError, ValueError):
                continue
    return tuple(names), additions, deletions


def _exit_code(metadata: dict) -> int | None:
    """A shell tool writes its exit status under ``metadata.metadata.exit``."""
    inner = metadata.get("metadata") if isinstance(metadata, dict) else None
    if not isinstance(inner, dict):
        inner = metadata
    try:
        return int(inner.get("exit"))
    except (TypeError, ValueError):
        return None


def parse_event(payload: object) -> Event | None:
    """Normalise one decoded record. Returns ``None`` for a non-record."""
    if not isinstance(payload, dict):
        return None
    raw_type = payload.get("type")
    if not isinstance(raw_type, str) or not raw_type:
        return None
    part = payload.get("part")
    part = part if isinstance(part, dict) else {}
    session_id = _text(payload.get("sessionID") or part.get("sessionID"), 128)
    try:
        timestamp = float(payload.get("timestamp") or 0) / 1000.0
    except (TypeError, ValueError):
        timestamp = 0.0

    if raw_type == "text":
        return Event(kind="text", session_id=session_id, text=_text(part.get("text"), MAX_TEXT),
                     timestamp=timestamp)

    if raw_type == "error":
        error = payload.get("error")
        if isinstance(error, dict):
            data = error.get("data")
            error = data.get("message") if isinstance(data, dict) else error.get("message") or error.get("name")
        return Event(kind="error", session_id=session_id, error=_text(error, MAX_TEXT))

    if raw_type == "tool_use":
        state = part.get("state") if isinstance(part.get("state"), dict) else {}
        tool = _text(part.get("tool"), 64)
        status = _text(state.get("status"), 32)
        source = state.get("input") if isinstance(state.get("input"), dict) else {}
        metadata = state.get("metadata") if isinstance(state.get("metadata"), dict) else {}
        names, additions, deletions = _files(metadata)
        output = _text(state.get("output"), MAX_TEXT)
        error = _text(state.get("error") or output, MAX_TEXT) if status == "error" else ""
        exit_code = _exit_code(metadata)
        return Event(
            kind="tool", session_id=session_id, tool=tool, status=status,
            command=_text(source.get("command"), MAX_COMMAND),
            path=_text(source.get("path") or source.get("filePath"), MAX_PATH),
            title=_text(state.get("title") or metadata.get("title"), 200),
            files=names, additions=additions, deletions=deletions,
            error=error, exit_code=exit_code, timestamp=timestamp,
            id=_text(part.get("callID") or part.get("id") or part.get("partID"), 128),
        )

    if raw_type in ("step_start", "step_finish"):
        return Event(kind=raw_type, session_id=session_id,
                     reason=_text(part.get("reason"), 64), timestamp=timestamp)

    return Event(kind="unknown", session_id=session_id, title=_text(raw_type, 64), timestamp=timestamp)


def parse_line(line: str) -> Event | None:
    """Parse one stdout line. Blank or malformed lines return ``None``."""
    if not line:
        return None
    line = line.strip()
    if not line or not line.startswith("{"):
        return None
    try:
        payload = json.loads(line)
    except (ValueError, TypeError):
        return None
    return parse_event(payload)


def iter_events(lines: Iterable[str]) -> Iterator[Event]:
    """Yield every usable event from an iterable of lines, skipping noise."""
    for line in lines:
        event = parse_line(line)
        if event is not None:
            yield event


@dataclass
class Tally:
    """Accumulated, bounded facts about a job derived purely from its stream."""

    session_id: str = ""
    reads: int = 0
    searches: int = 0
    edits: int = 0
    shells: int = 0
    failures: int = 0
    changed: list[str] = field(default_factory=list)
    additions: int = 0
    deletions: int = 0
    last_text: str = ""
    last_tool: str = ""
    last_error: str = ""
    _seen: set[str] = field(default_factory=set, repr=False)

    def add(self, event: Event) -> None:
        if event.session_id and not self.session_id:
            self.session_id = event.session_id
        if event.kind == "text" and event.text:
            self.last_text = event.text
        if not event.is_tool:
            return
        if event.status not in {"completed", "error"}:
            return
        if event.id:
            if event.id in self._seen:
                return
            self._seen.add(event.id)
        self.last_tool = event.tool or self.last_tool
        if event.tool in FILE_TOOLS:
            self.reads += 1
        if event.tool in {"grep", "glob"}:
            self.searches += 1
        if event.tool in CHANGE_TOOLS and not event.failed:
            self.edits += 1
            for name in event.files or ((event.path,) if event.path else ()):
                short = name.replace("\\", "/")
                if short and short not in self.changed:
                    self.changed.append(short)
            self.additions += event.additions
            self.deletions += event.deletions
        if event.tool == "shell":
            self.shells += 1
        if event.failed:
            self.failures += 1
            self.last_error = event.error or event.command or event.tool
