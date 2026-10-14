"""Owner terminal action. Approval cannot be supplied as a model parameter."""
import shutil
from core import confirm
from core.execution_policy import classify, require_owner
from core.shell_session import sessions
from core.tool_result import ToolResult, normalize


def terminal_exec(parameters: dict, **_kwargs) -> ToolResult:
    require_owner()
    operation = parameters.get('action', 'run')
    session_id = parameters.get('session_id') or 'default'
    if operation == 'cancel':
        return sessions.cancel(session_id)
    if operation == 'which':
        path = shutil.which(parameters.get('command', ''))
        return ToolResult('success' if path else 'failed', 'Executable lookup.', {'path': path}, [{'path': path}])
    if operation in {'pwd', 'cd', 'session_status'}:
        directory = sessions.cwd(session_id, parameters.get('cwd') if operation == 'cd' else None)
        return ToolResult('success', str(directory), {'cwd': str(directory), 'session_id': session_id,
                          'running': session_id in sessions.processes}, [{'cwd': str(directory)}])
    if operation != 'run':
        return ToolResult('failed', f'Unknown terminal operation: {operation}')
    directory = sessions.cwd(session_id, parameters.get('cwd'))
    command = parameters.get('command', '')
    decision = classify(command, str(directory))
    def execute():
        return sessions.run(command, str(directory), parameters.get('shell', 'powershell'),
                            parameters.get('timeout', 120), session_id)
    if decision.level == 'deny':
        return ToolResult('failed', decision.reason)
    if decision.level == 'confirm':
        def approved():
            from core.task_runtime import get_runtime
            from core.event_bus import bus
            runtime = get_runtime()
            task = runtime.create('Approved terminal command')
            runtime.attempt(task.id, 'terminal_exec')
            result = execute()
            runtime.finish(task.id, result)
            bus.publish('tool.completed', tool='terminal_exec', result=result.to_dict())
            return str(result)
        return normalize(confirm.request('terminal', 'Run terminal command',
                         f'{command}\nWorking directory: {directory}\n{decision.reason}', approved))
    return execute()


TOOL = {'name': 'terminal_exec', 'description': 'Execute real owner-requested shell commands with cwd, timeout, output and exit evidence. Use instead of GUI typing. Destructive or opaque commands require HUD approval.',
        'parameters': {'type': 'OBJECT', 'properties': {
            'action': {'type': 'STRING', 'enum': ['run', 'which', 'pwd', 'cd', 'session_status', 'cancel']},
            'command': {'type': 'STRING'}, 'cwd': {'type': 'STRING'}, 'session_id': {'type': 'STRING'},
            'shell': {'type': 'STRING', 'enum': ['powershell', 'cmd', 'bash']}, 'timeout': {'type': 'NUMBER'}}},
        'handler': terminal_exec}
