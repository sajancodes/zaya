from core.diagnostics import inspect
from core.execution_policy import require_owner


def system_diagnostics(parameters: dict, **_kwargs):
    require_owner()
    action = parameters.get('action', 'full')
    if action == 'bottleneck':
        from core.diagnostics import diagnose_bottleneck
        return diagnose_bottleneck()
    if action in ('hardware', 'battery'):
        from core.tool_result import ToolResult
        from services.system_monitor import get_system_status
        status = get_system_status()
        batt = status.get('battery')
        if action == 'battery':
            if not batt:
                return ToolResult("failed", "Battery sensor is unavailable on this device.")
            plug_str = "plugged in and charging" if batt["power_plugged"] else "on battery power"
            return ToolResult(
                "success",
                f"Battery is at {batt['percent']}% ({plug_str}).",
                data=batt,
            )
        summary = (
            f"Hardware status: CPU {status['cpu_percent']}%, RAM {status['ram_percent']}% "
            f"({status['ram_used_gb']}GB / {status['ram_total_gb']}GB), Uptime: {status['uptime']}."
        )
        return ToolResult("success", summary, data=status)
    return inspect(action)


TOOL = {'name': 'system_diagnostics', 'description': 'Run non-destructive local capability checks and inspect exact plugin/action failures, audio, providers, runtime, browser, WhatsApp availability, battery health, hardware load, or diagnose CPU/memory bottleneck processes.',
        'parameters': {'type': 'OBJECT', 'properties': {'action': {'type': 'STRING', 'enum': ['plugins', 'actions', 'providers', 'runtime', 'whatsapp', 'browser', 'audio', 'bottleneck', 'hardware', 'battery', 'full']}}},
        'handler': system_diagnostics}
