from core.git_utils import GitRepo
from core.tool_result import ToolResult
from core.execution_policy import require_owner


def git_control(parameters: dict, **_kwargs) -> ToolResult:
    require_owner()
    try:
        return GitRepo(parameters.get('path', '.')).operate(parameters.get('action', 'repo_info'), parameters)
    except (ValueError, RuntimeError, OSError) as error:
        return ToolResult('failed', str(error))


TOOL = {'name': 'git_control', 'description': 'Inspect and operate real repositories using structured Git. Stage explicit paths, inspect diff, commit, push and verify remote SHA. No force push or destructive reset.',
        'parameters': {'type': 'OBJECT', 'properties': {
            'action': {'type': 'STRING', 'enum': ['repo_info', 'status', 'diff', 'diff_staged', 'branches', 'checkout', 'create_branch', 'fetch', 'pull', 'stage', 'unstage', 'commit', 'push', 'log', 'remote', 'open_remote', 'verify_push']},
            'path': {'type': 'STRING'}, 'branch': {'type': 'STRING'}, 'remote': {'type': 'STRING'},
            'paths': {'type': 'ARRAY', 'items': {'type': 'STRING'}}, 'message': {'type': 'STRING'}}}, 'handler': git_control}
