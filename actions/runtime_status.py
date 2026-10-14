from dataclasses import asdict
from core.task_runtime import get_runtime, TERMINAL
from core.tool_result import ToolResult


def runtime_status(parameters: dict, **_kwargs) -> ToolResult:
    operation = parameters.get('action', 'summary')
    if operation == 'whatsapp':
        from services.whatsapp.service import get_service
        return get_service().query('status')
    tasks = get_runtime().list(30)
    if operation == 'active_tasks':
        tasks = [t for t in tasks if t.state not in TERMINAL]
    elif operation == 'failures':
        tasks = [t for t in tasks if t.state == 'failed']
    elif operation == 'waiting':
        tasks = [t for t in tasks if t.state.startswith('waiting') or t.state == 'paused']
    return ToolResult('success', f'{len(tasks)} recorded tasks.', {'tasks': [asdict(t) for t in tasks]},
                      [{'source': 'runtime_tasks'}])


TOOL = {'name': 'runtime_status', 'description': 'Read authoritative active, recent, failed or waiting task state. Use for questions about your current work.',
        'parameters': {'type': 'OBJECT', 'properties': {'action': {'type': 'STRING', 'enum': ['summary', 'active_tasks', 'recent_tasks', 'failures', 'waiting', 'whatsapp']}}},
        'handler': runtime_status}
