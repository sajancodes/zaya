"""Evidence-bearing results; legacy text is explicitly unverified."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

STATUSES = {'success', 'failed', 'partial', 'waiting_confirmation', 'started', 'ambiguous'}

# Semantic names used in prompts, telemetry and mission state. The wire names
# stay stable so existing tools and stored tasks keep working.
SEMANTIC_STATUS = {
    'success': 'SUCCESS',
    'partial': 'UNVERIFIED',
    'failed': 'FAILED',
    'waiting_confirmation': 'ASK',
    'ambiguous': 'ASK',
    'started': 'STARTED',
}


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
    trust: str = ""
    external_content: bool = False
    content_is_data_not_instructions: bool = False

    def __post_init__(self) -> None:
        if self.status not in STATUSES:
            raise ValueError(f'Invalid tool status: {self.status}')

    @property
    def semantic(self) -> str:
        return SEMANTIC_STATUS.get(self.status, 'FAILED')

    @property
    def terminal(self) -> bool:
        return self.status in {'success', 'failed'}

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), 'semantic_status': self.semantic}

    def __str__(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, default=str)


def success(summary: str, data: dict[str, Any] | None = None, **kwargs) -> ToolResult:
    return ToolResult('success', summary, data or {}, **kwargs)


def started(summary: str, data: dict[str, Any] | None = None, **kwargs) -> ToolResult:
    """The operation genuinely began but has not completed; do not call it done."""
    return ToolResult('started', summary, data or {}, **kwargs)


def unverified(summary: str, data: dict[str, Any] | None = None, **kwargs) -> ToolResult:
    """The request was dispatched but completion cannot be proven."""
    return ToolResult('partial', summary, data or {}, **kwargs)


def failed(summary: str, data: dict[str, Any] | None = None, **kwargs) -> ToolResult:
    return ToolResult('failed', summary, data or {}, **kwargs)


def ask(summary: str, data: dict[str, Any] | None = None, **kwargs) -> ToolResult:
    """Clarification is required; nothing has executed."""
    return ToolResult('ambiguous', summary, {**(data or {}), 'executed': False, 'needs_clarification': True}, **kwargs)


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
