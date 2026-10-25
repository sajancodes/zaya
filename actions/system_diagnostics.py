from core.diagnostics import inspect
from core.execution_policy import require_owner


def system_diagnostics(parameters: dict, **_kwargs):
    require_owner()
    action = parameters.get('action', 'full')
    if action == 'bottleneck':
        from core.diagnostics import diagnose_bottleneck
        return diagnose_bottleneck()
    return inspect(action)


TOOL = {'name': 'system_diagnostics', 'description': 'Run non-destructive local capability checks and inspect exact plugin/action failures, audio, providers, runtime, browser, WhatsApp availability, or diagnose CPU/memory bottleneck processes.',
        'parameters': {'type': 'OBJECT', 'properties': {'action': {'type': 'STRING', 'enum': ['plugins', 'actions', 'providers', 'runtime', 'whatsapp', 'browser', 'audio', 'bottleneck', 'full']}}},
        'handler': system_diagnostics}
