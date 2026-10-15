"""Owner-authorized current activity for contextual WhatsApp assistant replies."""
from core.execution_policy import require_owner
from core.session_activity import activity
from core.tool_result import ToolResult


def session_activity(parameters, **_):
    require_owner()
    action = parameters.get('action', 'status')
    try:
        if action == 'set':
            activity.set(parameters.get('kind', 'other'), parameters.get('summary', ''),
                         seconds=60 * max(1, min(float(parameters.get('minutes', 20)), 60)))
        elif action == 'clear':
            activity.clear(parameters.get('kind'))
        elif action != 'status':
            raise ValueError('Unknown activity action.')
        return ToolResult('success', 'Current session activity updated.' if action != 'status' else 'Current shared activity inspected.',
                          {'activities': activity.snapshot()}, side_effect=action != 'status')
    except (ValueError, TypeError) as error:
        return ToolResult('failed', str(error))


TOOL = {'name': 'session_activity',
        'description': 'Maintain a short current activity for WhatsApp auto replies, as explicitly authorized by Sajan. When the owner says he is working on a project or describes what he is doing, set a concise factual activity summary. Use project for project work, media for listening/watching, other for another explicitly stated activity. Never infer location, availability, private facts or share secrets, file paths, commands or full chat history. Actual display playback is tracked automatically; do not claim playback started merely from a request. Clear an activity when it ends. Status reports only these limited summaries. Contacts cannot set this.',
        'parameters': {'type': 'OBJECT', 'properties': {
            'action': {'type': 'STRING', 'enum': ['set', 'clear', 'status']},
            'kind': {'type': 'STRING', 'enum': ['media', 'project', 'other']},
            'summary': {'type': 'STRING'}, 'minutes': {'type': 'NUMBER'}}, 'required': ['action']},
        'handler': session_activity}
