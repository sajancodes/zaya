from core.diagnostics import inspect
from core.execution_policy import require_owner


def system_diagnostics(parameters: dict, **_kwargs):
    require_owner()
    return inspect(parameters.get('action', 'full'))


TOOL = {'name': 'system_diagnostics', 'description': 'Run non-destructive local capability checks and inspect exact plugin/action failures, audio, providers, runtime, browser and WhatsApp availability.',
        'parameters': {'type': 'OBJECT', 'properties': {'action': {'type': 'STRING', 'enum': ['plugins', 'actions', 'providers', 'runtime', 'whatsapp', 'browser', 'audio', 'full']}}},
        'handler': system_diagnostics}
