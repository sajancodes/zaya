"""Bounded subprocess execution with cwd sessions and process-tree cancellation."""
from __future__ import annotations
import os
import logging
import shlex
import shutil
import signal
import subprocess
import threading
import time
import uuid
from pathlib import Path
from core.audit import redact
from core.tool_result import ToolResult

log = logging.getLogger(__name__)


def split_command(command: str) -> list[str]:
    """Parse argv without losing quoted arguments or Windows path separators."""
    if not command.strip():
        return []
    if os.name != 'nt':
        return shlex.split(command)
    import ctypes
    from ctypes import wintypes
    shell = ctypes.WinDLL('shell32', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    shell.CommandLineToArgvW.argtypes = (wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_int))
    shell.CommandLineToArgvW.restype = ctypes.POINTER(wintypes.LPWSTR)
    kernel.LocalFree.argtypes = (ctypes.c_void_p,)
    kernel.LocalFree.restype = ctypes.c_void_p
    count = ctypes.c_int()
    argv = shell.CommandLineToArgvW(command.strip(), ctypes.byref(count))
    if not argv:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return [argv[index] for index in range(count.value)]
    finally:
        kernel.LocalFree(ctypes.cast(argv, ctypes.c_void_p))


class OutputBuffer:
    def __init__(self, limit: int = 16384) -> None:
        self.half = limit // 2
        self.head = b''
        self.tail = b''
        self.total = 0

    def add(self, data: bytes) -> None:
        self.total += len(data)
        needed = self.half - len(self.head)
        self.head += data[:needed]
        self.tail = (self.tail + data[needed:])[-self.half:]

    def text(self) -> str:
        marker = b'\n...[output truncated]...\n' if self.total > self.half * 2 else b''
        return redact((self.head + marker + self.tail).decode('utf-8', errors='replace'))


def terminate_tree(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    if os.name == 'nt':
        try:
            subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], capture_output=True, timeout=10,
                           creationflags=subprocess.CREATE_NO_WINDOW)
        except (OSError, subprocess.TimeoutExpired):
            log.warning('Process-tree termination failed for PID %s; trying the child directly.', process.pid)
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except OSError:
            log.warning('Process-group termination failed for PID %s.', process.pid)
    if process.poll() is None:
        try:
            process.kill()
        except OSError:
            log.warning('Unable to kill PID %s; termination is unconfirmed.', process.pid)


class ShellSessions:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self.sessions: dict[str, Path] = {}
        self.processes: dict[str, subprocess.Popen] = {}
        self.cancelled: set[str] = set()

    def cwd(self, session_id: str, cwd: str | None = None) -> Path:
        with self._lock:
            base = self.sessions.get(session_id, Path.cwd())
            path = (base / Path(cwd).expanduser()).resolve() if cwd else base
            if not path.is_dir():
                raise ValueError(f'Working directory does not exist: {path}')
            self.sessions[session_id] = path
            return path

    def cancel(self, session_id: str) -> ToolResult:
        with self._lock:
            process = self.processes.get(session_id)
            if process is None or process.poll() is not None:
                return ToolResult('failed', 'No running process in that session.')
            self.cancelled.add(session_id)
        terminate_tree(process)
        return ToolResult('success', 'Process cancellation requested.', {'session_id': session_id}, [{'pid': process.pid}], side_effect=True)

    def run(self, command: str, cwd: str | None = None, shell: str = 'powershell', timeout: float = 120,
            session_id: str | None = None) -> ToolResult:
        session_id = session_id or uuid.uuid4().hex
        directory = self.cwd(session_id, cwd)
        timeout = max(0.1, min(float(timeout), 600))
        if os.name == 'nt':
            if shell == 'cmd':
                argv = [os.environ.get('COMSPEC', 'cmd.exe'), '/d', '/s', '/c', command]
            else:
                executable = shutil.which('pwsh') or shutil.which('powershell')
                if not executable:
                    return ToolResult('failed', 'PowerShell is unavailable.')
                argv = [executable, '-NoProfile', '-NonInteractive', '-Command', command]
        else:
            argv = [shutil.which('bash') or '/bin/sh', '-c', command]
        return self.run_argv(argv, directory, timeout, session_id, command)

    def run_argv(self, argv: list[str], cwd: Path, timeout: float = 120, session_id: str | None = None,
                 command: str | None = None) -> ToolResult:
        session_id = session_id or uuid.uuid4().hex
        start = time.monotonic()
        with self._lock:
            if session_id in self.processes:
                return ToolResult('failed', 'Session already has a running command.')
            options = {'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {'start_new_session': True}
            try:
                process = subprocess.Popen(argv, cwd=str(cwd), stdin=subprocess.DEVNULL,
                                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, **options)
            except OSError as error:
                return ToolResult('failed', f'Process could not start: {error}', evidence=[{'started': False}])
            self.processes[session_id] = process
        outputs = [OutputBuffer(), OutputBuffer()]
        def drain(stream, output):
            try:
                while chunk := stream.read(4096):
                    output.add(chunk)
            finally:
                stream.close()
        threads = [threading.Thread(target=drain, args=(stream, output), daemon=True)
                   for stream, output in zip((process.stdout, process.stderr), outputs)]
        for thread in threads:
            thread.start()
        timed_out = False
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            terminate_tree(process)
            try:
                process.wait(timeout=10)
            except (OSError, subprocess.TimeoutExpired):
                log.warning('PID %s did not exit after termination; reporting the timeout.', process.pid)
        finally:
            for thread in threads:
                thread.join(timeout=10)
            with self._lock:
                self.processes.pop(session_id, None)
                cancelled = session_id in self.cancelled
                self.cancelled.discard(session_id)
        data = {'session_id': session_id, 'command': redact(command or ' '.join(argv)), 'cwd': str(cwd),
                'pid': process.pid, 'exit_code': process.returncode, 'stdout': outputs[0].text(),
                'stderr': outputs[1].text(), 'duration_ms': int((time.monotonic() - start) * 1000),
                'timed_out': timed_out, 'cancelled': cancelled,
                'truncated': any(o.total > o.half * 2 for o in outputs)}
        ok = process.returncode == 0 and not timed_out and not cancelled
        summary = 'Command completed.' if ok else ('Command timed out.' if timed_out else ('Command cancelled.' if cancelled else f'Command exited with code {process.returncode}.'))
        # An arbitrary shell command may partially mutate before failing: no blind automatic retry.
        return ToolResult('success' if ok else 'failed', summary, data,
                          [{'exit_code': process.returncode, 'pid': process.pid, 'timed_out': timed_out}], side_effect=True)


sessions = ShellSessions()
