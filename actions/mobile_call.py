"""Let Zaya decide that something is worth ringing the owner about.

This is the explicit path: everything else (blocked tasks, failed work, urgent
messages, system warnings) reaches the call policy from the runtime. This tool
exists for the cases only the model can recognise — a question it cannot answer
without the owner, or a request the owner made earlier to be told directly.

The policy on the laptop still decides whether the phone actually rings: a
suppressed call becomes a notification, and the tool says so honestly instead of
claiming a ring that never happened.
"""
from core import mobile_protocol as protocol
from core.execution_policy import require_owner
from core.mobile_calls import get_call_manager
from core.tool_result import ToolResult

_URGENCY = {
    'critical': protocol.P0_CRITICAL,
    'immediate': protocol.P1_IMMEDIATE,
    'important': protocol.P2_IMPORTANT,
    'normal': protocol.P3_NORMAL,
    'urgent': protocol.P1_IMMEDIATE,
}


def call_owner(parameters, **_kwargs):
    require_owner()
    reason = str(parameters.get('reason') or '').strip()
    if not reason:
        return ToolResult('failed', 'A call needs a concrete reason.')
    question = str(parameters.get('question') or '').strip()
    urgency = str(parameters.get('urgency') or 'immediate').strip().lower()
    priority = _URGENCY.get(urgency, protocol.P1_IMMEDIATE)
    detail = question or reason
    manager = get_call_manager()
    call = manager.request_call(
        title=f'Zaya: {reason[:80]}',
        detail=detail,
        priority=priority,
        reason=reason,
        briefing=(f'{reason}. ' + (f'You need this decision from him: {question}' if question
                                   else 'Open the call with what you need in one or two sentences.')),
        source='tool',
        key=f'tool:{reason[:80]}',
        requested=parameters.get('requested') is True,
    )
    if call is None:
        # The policy downgraded it. Say that plainly: the owner should look at
        # the notification rather than wait for a ring that is not coming.
        return ToolResult(
            'success',
            'A call was not appropriate right now, so this was sent to the phone as a '
            'notification instead.',
            {'delivery': 'notification', 'priority': protocol.priority_name(priority)},
            side_effect=True)
    return ToolResult(
        'success',
        'Sent an incoming-call request to the connected phone; awaiting answer.',
        {'delivery': 'call', 'call_id': call.call_id,
         'priority': protocol.priority_name(call.priority)},
        side_effect=True)


TOOL = {
    'name': 'call_owner',
    'description': (
        'Ring the owner on his phone when you genuinely need him: a decision only he can '
        'make, something important that failed, a critical system or security problem, or a '
        'request he made earlier to be told directly. Also use it when the owner explicitly says '
        '"call me" or asks to test a phone call: set requested=true so the phone rings even '
        'while he is at the laptop or recently tested a call. Never set requested=true '
        'for an automatic update. Do NOT use it for ordinary updates, '
        'routine progress, or anything that can wait for a normal reply — the laptop decides '
        'the priority and will downgrade a call that is not warranted. State the concrete '
        'reason; the owner hears it when he answers, so he never has to ask what happened.'
    ),
    'parameters': {
        'type': 'OBJECT',
        'properties': {
            'requested': {'type': 'BOOLEAN', 'description': 'True only when the owner explicitly requests an immediate/test call; false for proactive calls.'},
            'reason': {'type': 'STRING',
                       'description': 'One short sentence: why you need the owner now.'},
            'question': {'type': 'STRING',
                         'description': 'The decision or answer you need from him, if any.'},
            'urgency': {'type': 'STRING',
                        'enum': ['critical', 'immediate', 'important', 'normal']},
        },
        'required': ['reason'],
    },
    'handler': call_owner,
    'scheduling': 'SILENT',
}
