"""Human-readable activity labels derived from runtime events."""
TOOLS = {'git_control': 'Git operation', 'terminal_exec': 'Terminal task',
         'whatsapp': 'WhatsApp', 'runtime_status': 'Checking task state',
         'system_diagnostics': 'Checking capabilities', 'browser_control': 'Browser task'}
STATES = {'waiting_confirmation': 'awaiting your confirmation', 'waiting_external': 'awaiting verification',
          'executing': 'working', 'verifying': 'verifying', 'completed': 'completed',
          'failed': 'failed', 'cancelled': 'cancelled', 'paused': 'paused', 'created': 'starting'}


def label(event: dict) -> str | None:
    if event['event'].startswith('task.'):
        task = event.get('task', {})
        name = task.get('active_step') or task.get('goal', 'Task')
        return f"{TOOLS.get(name, name.replace('_', ' ').capitalize())} · {STATES.get(task.get('state'), task.get('state', 'working'))}"
    if event['event'] == 'whatsapp.mode.changed':
        mode = event.get('mode', 'observe')
        return 'WhatsApp auto · awaiting complete feed' if mode == 'auto' else f'WhatsApp · {mode}'
    return None
