import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from core.shell_session import ShellSessions
from actions.terminal_exec import terminal_exec
from core import confirm


class TerminalTests(unittest.TestCase):
    def test_real_exit_stdout_stderr_and_cwd(self):
        with tempfile.TemporaryDirectory() as folder:
            s = ShellSessions()
            r = s.run_argv([sys.executable, '-c', 'import os,sys; print(os.getcwd()); print("problem",file=sys.stderr); sys.exit(7)'], Path(folder))
            self.assertEqual(r.status, 'failed')
            self.assertEqual(r.data['exit_code'], 7)
            self.assertIn(folder.lower(), r.data['stdout'].strip().lower())
            self.assertIn('problem', r.data['stderr'])

    def test_output_limit(self):
        r = ShellSessions().run_argv([sys.executable, '-c', 'print("x"*1000000)'], Path.cwd())
        self.assertTrue(r.data['truncated'])
        self.assertLess(len(r.data['stdout']), 17000)

    def test_timeout_kills_process(self):
        r = ShellSessions().run_argv([sys.executable, '-c', 'import time; time.sleep(30)'], Path.cwd(), timeout=.2)
        self.assertTrue(r.data['timed_out'])
        self.assertEqual(r.status, 'failed')

    def test_cancel(self):
        s, results = ShellSessions(), []
        t = threading.Thread(target=lambda: results.append(s.run_argv([sys.executable, '-c', 'import time; time.sleep(30)'], Path.cwd(), session_id='test')))
        t.start()
        for _ in range(100):
            if 'test' in s.processes:
                break
            time.sleep(.02)
        self.assertEqual(s.cancel('test').status, 'success')
        t.join(15)
        self.assertFalse(t.is_alive())
        self.assertTrue(results[0].data['cancelled'])

    def test_dangerous_command_never_runs_without_hud(self):
        confirm.bind(None, None)
        r = terminal_exec({'command': 'git reset --hard'})
        self.assertNotEqual(r.status, 'success')
        self.assertIn('not done', r.summary)

    def test_real_shell(self):
        r = terminal_exec({'command': 'git --version', 'session_id': 'git-version'})
        # --version uses conservative approval; an ordinary status requires no gate.
        with tempfile.TemporaryDirectory() as folder:
            r = terminal_exec({'command': 'Write-Output hello' if sys.platform == 'win32' else 'echo hello', 'cwd': folder})
            self.assertEqual(r.status, 'success')
            self.assertIn('hello', r.data['stdout'])
