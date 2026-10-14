"""Evidence-bearing results; legacy text is explicitly unverified."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

STATUSES = {'success', 'failed', 'partial', 'waiting_confirmation'}


def truncate(text: str, limit: int = 16384) -> tuple[str, bool]:
    raw = text.encode('utf-8', errors='replace')
    if len(raw) <= limit:
        return text, False
    half = max(0, (limit - 40) // 2)
    return (raw[:half].decode('utf-8', errors='replace') + '\n...[output truncated]...\n'
            + raw[-half:].decode('utf-8', errors='replace')), True


@dataclass
class ToolResult:
    status: str
    summary: str
    data: dict[str, Any] = field(default_factory=dict)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    retryable: bool = False
    side_effect: bool = False
    undo_id: str | None = None

    def __post_init__(self) -> None:
        if self.status not in STATUSES:
            raise ValueError(f'Invalid tool status: {self.status}')

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def __str__(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, default=str)


def normalize(value: Any) -> ToolResult:
    if isinstance(value, ToolResult):
        return value
    if isinstance(value, dict) and value.get('status') in STATUSES:
        return ToolResult(**{k: v for k, v in value.items() if k in ToolResult.__dataclass_fields__})
    text = str(value or 'No result returned.')
    if '[CONFIRMATION_PENDING]' in text:
        status = 'waiting_confirmation'
    elif text.lower().startswith(('tool ', 'unknown tool:', 'error:', 'failed', 'could not', 'cannot ')):
        status = 'failed'
    else:
        status = 'partial'
    return ToolResult(status, truncate(text)[0], {'legacy': True, 'verified': False})
