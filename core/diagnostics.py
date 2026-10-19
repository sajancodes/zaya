"""Non-destructive capability inspection, with exact loader failures."""
from __future__ import annotations
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
            import json
            voice_path = Path(__file__).resolve().parent.parent / 'logs' / 'runtime' / 'voice_status.json'
            try:
                checks['audio']['live_voice'] = json.loads(voice_path.read_text(encoding='utf-8'))
            except (OSError, ValueError):
                checks['audio']['live_voice'] = {'available': False}
        except Exception as error:
            checks['audio'] = {'error': str(error)}
    if operation in {'full', 'whatsapp'}:
        checks['hermes_cli'] = shutil.which('hermes')
        try:
            from services.whatsapp.service import get_service
            checks['whatsapp'] = get_service().query('status').data
        except ImportError:
            checks['whatsapp'] = {'available': False, 'reason': 'WhatsApp service not installed.'}
    if operation in {'full', 'bottleneck'}:
        checks['bottleneck'] = diagnose_bottleneck().data
    return ToolResult('success', 'Local diagnostics collected; capability availability is reported per check.', checks,
                      [{'checks': list(checks)}])


def diagnose_bottleneck(top_n: int = 5) -> ToolResult:
    """Identify top CPU and RAM consuming processes without blocking execution.

    Labels system/svchost service instances and excludes Zaya's own process.
    """
    try:
        import psutil
        import time

        my_pid = os.getpid()
        procs: list[psutil.Process] = []

        # First pass: collect processes and initialize cpu_percent
        for p in psutil.process_iter(['pid', 'name']):
            try:
                pid = p.info.get('pid', 0)
                if pid in (0, 4, my_pid):
                    continue
                p.cpu_percent(interval=None)
                procs.append(p)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        # Brief non-blocking sleep for delta calculation
        time.sleep(0.1)

        records: list[dict] = []
        for p in procs:
            try:
                cpu = p.cpu_percent(interval=None)
                mem = p.memory_percent()
                name = p.name()
                pid = p.pid

                label = name
                # Contextual labeling for svchost or system processes
                if name.lower() == 'svchost.exe':
                    label = f"svchost.exe (System Service {pid})"
                elif name.lower() in ('system', 'registry', 'smss.exe'):
                    label = f"{name} (Windows Core)"

                records.append({
                    'pid': pid,
                    'name': name,
                    'label': label,
                    'cpu_percent': round(cpu, 1),
                    'memory_percent': round(mem, 1),
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        by_cpu = sorted(records, key=lambda x: x['cpu_percent'], reverse=True)[:top_n]
        by_mem = sorted(records, key=lambda x: x['memory_percent'], reverse=True)[:top_n]

        overall_cpu = psutil.cpu_percent(interval=None)
        overall_mem = psutil.virtual_memory().percent

        summary = (
            f"Overall CPU: {overall_cpu}%, RAM: {overall_mem}%. "
            f"Top CPU consumer: {by_cpu[0]['label']} ({by_cpu[0]['cpu_percent']}%) "
            f"Top RAM consumer: {by_mem[0]['label']} ({by_mem[0]['memory_percent']}%)."
        ) if by_cpu and by_mem else "System resource consumers sampled."

        data = {
            'overall_cpu_percent': overall_cpu,
            'overall_ram_percent': overall_mem,
            'top_cpu_processes': by_cpu,
            'top_memory_processes': by_mem,
        }
        return ToolResult('success', summary, data)

    except Exception as e:
        return ToolResult('failed', f"Failed to diagnose system bottleneck: {e}")
