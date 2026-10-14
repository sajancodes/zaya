"""Non-destructive capability inspection, with exact loader failures."""
from __future__ import annotations
from dataclasses import asdict
import os
from pathlib import Path
import shutil
from core.tool_result import ToolResult

registries: dict = {}


def inspect(operation: str = 'full') -> ToolResult:
    from memory.config_manager import load_api_keys, CONFIG_FILE
    from core.task_runtime import get_runtime
    from core.site_registry import browser_state
    checks: dict = {}
    if operation in {'full', 'plugins', 'actions'}:
        for kind in ('plugins', 'actions'):
            registry = registries.get(kind)
            if registry:
                checks[kind] = registry.list_for_ui() if kind == 'plugins' else [
                    {'name': r.name, 'file': r.file, 'valid': r.valid, 'error': r.error, 'enabled': r.valid}
                    for r in registry._all_records]
            else:
                checks[kind] = {'loaded': False, 'reason': 'App registry not bound in this process.'}
    if operation in {'full', 'providers'}:
        checks['providers'] = {'config_exists': CONFIG_FILE.exists(), 'gemini_key_present': bool(load_api_keys().get('gemini_api_key')),
                               'engine': 'Gemini Live', 'model_source': 'core.gemini.live_candidates'}
    if operation in {'full', 'runtime'}:
        runtime = get_runtime()
        checks['runtime'] = {'sqlite_ok': runtime.db.execute('PRAGMA quick_check').fetchone()[0] == 'ok',
                             'memory_writable': os.access(Path(__file__).resolve().parent.parent / 'memory', os.W_OK),
                             'tasks': len(runtime.list()), 'git': shutil.which('git'),
                             'shell': shutil.which('pwsh') or shutil.which('powershell') or shutil.which('bash')}
    if operation in {'full', 'browser'}:
        checks['browser'] = {'state': dict(browser_state), 'executables': {name: shutil.which(name) for name in ('brave', 'chrome', 'msedge', 'firefox')}}
    if operation in {'full', 'audio'}:
        try:
            import sounddevice
            checks['audio'] = {'devices': [dict(d) for d in sounddevice.query_devices()]}
        except Exception as error:
            checks['audio'] = {'error': str(error)}
    if operation in {'full', 'whatsapp'}:
        checks['hermes_cli'] = shutil.which('hermes')
        try:
            from services.whatsapp.service import get_service
            checks['whatsapp'] = get_service().query('status').data
        except ImportError:
            checks['whatsapp'] = {'available': False, 'reason': 'WhatsApp service not installed.'}
    return ToolResult('success', 'Local diagnostics collected; capability availability is reported per check.', checks,
                      [{'checks': list(checks)}])
