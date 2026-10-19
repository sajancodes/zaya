"""Task-Manager-style application termination for Zaya.

Named app closes must not depend on which window happens to have focus.  This
action resolves the requested app to running processes, protects Zaya and
critical Windows processes, terminates the matching process tree, and verifies
that the selected PIDs actually exited.
"""
from __future__ import annotations

import os
import platform
import re
import subprocess
import time

import psutil
from core.tool_result import ToolResult


_ALIASES = {
    "open code": "opencode.exe",
    "task manager": "taskmgr.exe",
    "taskmanager": "taskmgr.exe",
    "notepad": "notepad.exe",
    "brave": "brave.exe",
    "brave browser": "brave.exe",
    "chrome": "chrome.exe",
    "google chrome": "chrome.exe",
    "edge": "msedge.exe",
    "microsoft edge": "msedge.exe",
    "firefox": "firefox.exe",
    "discord": "discord.exe",
    "spotify": "spotify.exe",
    "obs": "obs64.exe",
    "obs studio": "obs64.exe",
    "vscode": "code.exe",
    "vs code": "code.exe",
    "visual studio code": "code.exe",
    "powershell": "powershell.exe",
    "pwsh": "pwsh.exe",
    "cmd": "cmd.exe",
    "command prompt": "cmd.exe",
}

# Never let a fuzzy app name take down Windows itself.  The current Zaya PID is
# protected separately, so other ordinary Python processes may still be closed
# when the owner explicitly names them.
_PROTECTED = {
    "system", "system idle process", "registry", "memory compression",
    "smss.exe", "csrss.exe", "wininit.exe", "winlogon.exe", "services.exe",
    "lsass.exe", "fontdrvhost.exe", "dwm.exe",
}


def _clean(text: str) -> str:
    text = (text or "").strip().strip('"').strip("'")
    text = re.sub(r"\s+", " ", text)
    return text


def _stem(name: str) -> str:
    name = os.path.basename(_clean(name)).lower()
    return name[:-4] if name.endswith(".exe") else name


def _target_name(app: str) -> str:
    raw = _clean(app)
    low = raw.lower()
    if low in _ALIASES:
        return _ALIASES[low]
    base = os.path.basename(raw)
    if base.lower().endswith(".exe"):
        return base
    return base + ".exe"


def _find_matches(app: str):
    target = _target_name(app)
    wanted = _stem(target)
    exact = []
    for proc in psutil.process_iter(["pid", "ppid", "name", "exe"]):
        try:
            info = proc.info
            if info["pid"] == os.getpid():
                continue
            name = (info.get("name") or "").lower()
            exe = os.path.basename(info.get("exe") or "").lower()
            if name in _PROTECTED or exe in _PROTECTED:
                continue
            if _stem(name) == wanted or _stem(exe) == wanted:
                exact.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    return target, exact


def _root_matches(processes):
    pids = {p.pid for p in processes}
    roots = []
    for proc in processes:
        try:
            if proc.ppid() not in pids:
                roots.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return roots or processes


def _terminate_windows(processes):
    errors = []
    for proc in _root_matches(processes):
        try:
            result = subprocess.run(
                ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                capture_output=True, text=True, timeout=8,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if result.returncode != 0 and psutil.pid_exists(proc.pid):
                errors.append((result.stderr or result.stdout or f"PID {proc.pid}").strip())
        except Exception as exc:  # noqa: BLE001
            errors.append(str(exc))
    return errors


def _terminate_portable(processes):
    errors = []
    selected = []
    for root in _root_matches(processes):
        try:
            selected.extend(root.children(recursive=True))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        selected.append(root)
    seen = set()
    for proc in reversed(selected):
        if proc.pid in seen or proc.pid == os.getpid():
            continue
        seen.add(proc.pid)
        try:
            proc.kill()
        except psutil.NoSuchProcess:
            pass
        except Exception as exc:  # noqa: BLE001
            errors.append(f"PID {proc.pid}: {exc}")
    return errors


def terminate_app(parameters: dict = None, **_kwargs) -> ToolResult:
    from core.execution_policy import require_owner
    require_owner()

    params = parameters or {}
    app = _clean(str(params.get("app") or params.get("name") or ""))
    if not app:
        return ToolResult('failed', 'No application name was provided.')

    coding_state = {}
    if _stem(_target_name(app)) in {'opencode', 'opencode-cli'}:
        from core.coding_jobs import get_jobs
        jobs = get_jobs()
        jobs.stop()  # Invalidate queued speech and cancel planning as well as the child.
        coding_state = jobs.execution_status()

    _target, matches = _find_matches(app)
    if not matches:
        pending = coding_state.get('worker_running', False)
        return ToolResult('partial' if pending else 'success',
                          f'{app} has no matching running app process.' +
                          (' The coding worker cancellation is still pending.' if pending else ''),
                          coding_state, [{'matched_processes': 0, **coding_state}], side_effect=bool(coding_state))

    chosen_pids = {p.pid for p in matches}
    if platform.system() == "Windows":
        errors = _terminate_windows(matches)
    else:
        errors = _terminate_portable(matches)

    deadline = time.monotonic() + 3.0
    alive = set(chosen_pids)
    while alive and time.monotonic() < deadline:
        alive = {pid for pid in alive if psutil.pid_exists(pid)}
        if alive:
            time.sleep(0.08)

    if alive:
        detail = f"; {'; '.join(errors[:2])}" if errors else ""
        return ToolResult('partial', f'Tried to terminate {app}, but {len(alive)} selected process(es) '
                          f'are still running{detail}.', {'remaining_pids': sorted(alive), **coding_state},
                          [{'selected_pids': sorted(chosen_pids), 'remaining_pids': sorted(alive)}], side_effect=True)

    pending = coding_state.get('worker_running', False)
    return ToolResult('partial' if pending else 'success',
                      f'Closed {app} from its process tree ({len(chosen_pids)} process(es) terminated).' +
                      (' Coding worker cancellation is still pending.' if pending else ''), coding_state,
                      [{'selected_pids': sorted(chosen_pids), 'remaining_pids': []}], side_effect=True)


# computer_settings historically mapped close_app to Alt+F4.  Keep close_window
# for the explicit "current window" case, but make the legacy named-app route
# unavailable so a model-routing mistake cannot close the wrong focused window.
try:
    from actions import computer_settings as _legacy_settings
    _legacy_settings.ACTION_MAP.pop("close_app", None)
except Exception:
    pass


TOOL = {
    "name": "terminate_app",
    "description": (
        "Close/quit/kill a NAMED application by terminating its actual process tree, "
        "the equivalent of End task in Task Manager. Use this for requests like "
        "'close Notepad', 'close Task Manager', 'quit Brave', or 'kill Discord'. "
        "It does not use Alt+F4 and does not depend on the focused window. "
        "Do not use it for 'close this window' or 'close this browser tab'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "app": {
                "type": "STRING",
                "description": "The exact application name the owner asked to close, e.g. Notepad, Task Manager, Brave."
            }
        },
        "required": ["app"],
    },
    "handler": terminate_app,
}
