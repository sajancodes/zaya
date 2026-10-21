"""Owner terminal action. Approval cannot be supplied as a model parameter."""
import shutil
import os
import re
from pathlib import Path
from core import confirm
from core.execution_policy import classify, require_owner
from core.shell_session import sessions
from core.tool_result import ToolResult, normalize


def _editor_target(value: str, directory: Path) -> Path:
    path = Path(value).expanduser()
    parts = value.replace('\\', '/').split('/')
    if parts and parts[0].lower() == 'desktop':
        from actions.file_controller import _resolve_path
        path = _resolve_path('desktop').joinpath(*parts[1:])
    return (directory / path).resolve() if not path.is_absolute() else path.resolve()


def _open_project(value: str, directory: Path, session_id: str) -> ToolResult:
    require_owner()
    if not value.strip():
        return ToolResult('failed', 'Specify an existing project directory.')
    target = _editor_target(value, directory)
    if not target.is_dir():
        return ToolResult('failed', f'Project directory does not exist: {target}', {'path': str(target)})
    executable = shutil.which('code')
    if not executable:
        return ToolResult('failed', 'VS Code is not available on PATH.')
    if os.name == 'nt' and Path(executable).suffix.lower() in {'.cmd', '.bat'}:
        native = Path(executable).parent.parent / 'Code.exe'
        if not native.is_file():
            return ToolResult('failed', 'The native VS Code launcher could not be verified.')
        executable = str(native)
    def launch():
        result = sessions.run_argv([executable, '--reuse-window', str(target)], directory, 30, session_id)
        if result.status == 'success':
            result.status = 'partial'
            result.summary = f'VS Code launch requested for existing folder {target}. The opened window has not been independently verified.'
            result.data.update(project_path=str(target), launch_requested=True, workspace_verified=False)
        return result
    if classify(f'code "{target}"', str(directory)).level == 'confirm':
        from core.operator import current_task, current_request
        originating_task = current_task.get()
        originating_request = current_request.get()

        def approved():
            from core.task_runtime import get_runtime
            from core.event_bus import bus
            runtime = get_runtime()
            task = runtime.get(originating_task) if originating_task else None
            if task is not None and task.state == 'cancelled':
                return 'The project launch was cancelled before approval.'
            task = task or runtime.create('Approved VS Code project launch')
            runtime.transition(task.id, 'executing', active_step='terminal_exec.open_project')
            try:
                result = launch()
            except Exception as error:
                result = ToolResult('failed', f'VS Code launch failed: {error}')
            runtime.finish(task.id, result)
            if originating_request and result.data.get('launch_requested'):
                runtime.remember(originating_request, result)
            bus.publish('tool.failed' if result.status == 'failed' else 'tool.completed',
                        tool='terminal_exec', result=result.to_dict())
            return str(result)

        def cancelled(reason):
            if originating_task:
                from core.task_runtime import get_runtime
                get_runtime().transition(originating_task, 'cancelled', error=reason)

        return normalize(confirm.request('open_project', 'Open project in VS Code', str(target),
                                         approved, on_cancel=cancelled))
    return launch()


def terminal_exec(parameters: dict, **_kwargs) -> ToolResult:
    require_owner()
    operation = parameters.get('action', 'run')
    session_id = parameters.get('session_id') or 'default'
    if operation == 'open_project':
        directory = sessions.cwd(session_id, parameters.get('cwd'))
        return _open_project(str(parameters.get('path') or ''), directory, session_id)
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
    from core.opencode_cli import launches_cli
    if launches_cli(str(parameters.get('command') or '')):
        return ToolResult('failed', 'Use coding_job for OpenCode work so Zaya can prepare the prompt, monitor it and send follow-ups in a hidden session. Do not open an interactive console.',
                          {'use_tool': 'coding_job'})
    directory = sessions.cwd(session_id, parameters.get('cwd'))
    command = parameters.get('command', '')
    if not re.search(r'[;&|<>`$\r\n]', command):
        from core.shell_session import split_command
        argv = split_command(command)
        if len(argv) == 2 and Path(argv[0]).name.lower() in {'code', 'code.exe', 'code.cmd'} and not argv[1].startswith('-'):
            return _open_project(argv[1], directory, session_id)
    decision = classify(command, str(directory))
    def execute():
        return sessions.run(command, str(directory), parameters.get('shell', 'powershell'),
                            parameters.get('timeout', 120), session_id)
    if decision.level == 'deny':
        return ToolResult('failed', decision.reason)
    if decision.level == 'confirm':
        from core.operator import current_task, current_request
        originating_task = current_task.get()
        originating_request = current_request.get()
        def approved():
            from core.task_runtime import get_runtime
            from core.event_bus import bus
            runtime = get_runtime()
            task = runtime.get(originating_task) if originating_task else runtime.create('Approved terminal command')
            runtime.transition(task.id, 'executing', active_step='terminal_exec')
            result = execute()
            runtime.finish(task.id, result)
            if originating_request and result.status == 'success':
                runtime.remember(originating_request, result)
            bus.publish('tool.completed', tool='terminal_exec', result=result.to_dict())
            return str(result)
        def cancelled(reason):
            if originating_task:
                from core.task_runtime import get_runtime
                get_runtime().transition(originating_task, 'cancelled', error=reason)
        return normalize(confirm.request('terminal', 'Run terminal command',
                         f'{command}\nWorking directory: {directory}\n{decision.reason}', approved, on_cancel=cancelled))
    result = execute()
    result.side_effect = decision.level != 'read'
    return result


TOOL = {'name': 'terminal_exec', 'description': 'Execute real owner-requested shell commands with cwd, timeout, output and exit evidence. Use instead of GUI typing. The owner\'s saved Full Access setting controls whether approval is needed; always call the tool and follow its actual result.',
        'parameters': {'type': 'OBJECT', 'properties': {
            'action': {'type': 'STRING', 'enum': ['run', 'open_project', 'which', 'pwd', 'cd', 'session_status', 'cancel']},
            'path': {'type': 'STRING', 'description': 'Existing project folder for open_project. Desktop paths are resolved against the owner desktop, not the terminal cwd.'},
            'command': {'type': 'STRING'}, 'cwd': {'type': 'STRING'}, 'session_id': {'type': 'STRING'},
            'shell': {'type': 'STRING', 'enum': ['powershell', 'cmd', 'bash']}, 'timeout': {'type': 'NUMBER'}}},
        'handler': terminal_exec}
