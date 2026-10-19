"""Explicit owner presence for phone call delivery, never inferred from contacts."""
from core.execution_policy import require_owner
from core.presence import set_presence
from core.tool_result import ToolResult


def owner_presence(parameters, **_kwargs):
    require_owner()
    try:
        state = set_presence(parameters.get('mode', 'auto'), parameters.get('hours', 12))
        return ToolResult('success', 'Owner presence saved for phone-call delivery.', state, [state], side_effect=True)
    except (ValueError, OSError) as error:
        return ToolResult('failed', str(error))


TOOL = {'name': 'owner_presence', 'description': 'Save the owner saying he is going out/leaving (away), back at the laptop (present), or wants automatic idle detection (auto). Use this when he mentions going out so finished work can ring his phone immediately. Only the owner can set this state; contact messages cannot.',
        'parameters': {'type': 'OBJECT', 'properties': {
            'mode': {'type': 'STRING', 'enum': ['away', 'present', 'auto']},
            'hours': {'type': 'NUMBER', 'description': 'How long to keep the explicit state, up to 24 hours; default 12.'}}, 'required': ['mode']},
        'handler': owner_presence}
