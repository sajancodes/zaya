from pathlib import Path
from core.execution_policy import require_owner
from core.tool_result import ToolResult
from memory.profile_bootstrap import bootstrap, PROFILE_PATH
from memory.project_index import register_project


def personal_profile(parameters: dict, **_kwargs):
    require_owner()
    try:
        if parameters.get('action', 'status') == 'import':
            result = bootstrap(Path(parameters['path']).expanduser().resolve())
            return ToolResult('success', 'Explicitly supplied private profile imported locally.', result,
                              [{'fact_count': result['fact_count']}], side_effect=True)
        if parameters.get('action') == 'register_project':
            result = register_project(parameters['path'], parameters['name'], parameters.get('aliases', []))
            return ToolResult('success', 'Local project alias registered.', {'name': result['name'], 'path': result['path']},
                              [{'source': 'local project index'}], side_effect=True)
        return ToolResult('success', 'Private profile status.', {'exists': PROFILE_PATH.exists()}, [{'profile_exists': PROFILE_PATH.exists()}])
    except (OSError, ValueError, KeyError) as error:
        return ToolResult('failed', str(error))


TOOL = {'name': 'personal_profile', 'description': 'Explicitly import a user-supplied non-sensitive local profile JSON or register project path aliases. Actual profile data remains local and ignored by Git.',
        'parameters': {'type': 'OBJECT', 'properties': {'action': {'type': 'STRING', 'enum': ['status', 'import', 'register_project']},
            'path': {'type': 'STRING'}, 'name': {'type': 'STRING'}, 'aliases': {'type': 'ARRAY', 'items': {'type': 'STRING'}}}}, 'handler': personal_profile}
