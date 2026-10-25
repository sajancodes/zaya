"""Fixed-target desktop launch/restart. Created by Sajan Rai for Zaya."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import threading

import psutil
from core.runtime_paths import get_log_dir

ROOT = Path(__file__).resolve().parents[1]
PID_FILE = get_log_dir() / 'desktop-process.json'
_launch_lock = threading.Lock()
_launched_process = None


def python_windowless():
    candidate = Path(sys.executable).with_name('pythonw.exe')
    return str(candidate if os.name == 'nt' and candidate.exists() else Path(sys.executable))


def spawn_fixed(arguments, *, windowless=True):
    log = get_log_dir() / 'desktop-launcher.log'
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open('ab') as output:
        executable = python_windowless() if windowless else str(Path(sys.executable).with_name('python.exe'))
        return subprocess.Popen([executable, *arguments], cwd=ROOT,
            stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT,
            creationflags=(subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP)
            if os.name == 'nt' else 0, close_fds=True)


def record_desktop():
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(json.dumps({'pid': os.getpid(),
        'created': psutil.Process().create_time()}), encoding='utf-8')


def desktop_running():
    try:
        info = json.loads(PID_FILE.read_text(encoding='utf-8'))
        process = psutil.Process(int(info['pid']))
        return abs(process.create_time() - float(info['created'])) < 0.01 and process.is_running()
    except (OSError, ValueError, KeyError, TypeError, psutil.Error):
        return False


def launch_desktop():
    global _launched_process
    with _launch_lock:
        if desktop_running():
            return 'already_running'
        if _launched_process is not None and _launched_process.poll() is None:
            return 'starting'
        _launched_process = spawn_fixed([str(ROOT / 'main.py')])
        return 'starting'


def schedule_restart():
    """The helper waits for this exact process to EXIT before spawning Zaya."""
    return spawn_fixed(['-m', 'core.desktop_lifecycle', '--wait-pid', str(os.getpid()),
                        '--created', str(psutil.Process().create_time())])


def restart_after_exit(pid, created, timeout=60):
    try:
        process = psutil.Process(pid)
        if abs(process.create_time() - created) < 0.01:
            process.wait(timeout=timeout)
    except psutil.NoSuchProcess:
        pass
    # Timeout/permission errors intentionally stop here: never overlap a live
    # desktop or kill some other process to manufacture a successful restart.
    return launch_desktop()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--wait-pid', required=True, type=int)
    parser.add_argument('--created', required=True, type=float)
    opts = parser.parse_args()
    restart_after_exit(opts.wait_pid, opts.created)
