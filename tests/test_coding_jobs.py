"""Hidden subprocess lifecycle and owner-only coding integration checks."""
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from core.coding_jobs import CodingJob, CodingJobs
from core.coding_supervisor import Brief
from core.execution_policy import TRUST_EXTERNAL_MESSAGE, TRUST_LOCAL_OWNER, with_trust
from core.opencode_cli import CliInfo
from core.opencode_events import Event, Tally, parse_line
from core.opencode_narrator import Narrator
from core.task_runtime import TaskRuntime


def record(kind, **part):
    return json.dumps({'type': kind, 'sessionID': 'ses_fixture', 'part': part}) + '\n'


class Process:
    def __init__(self, stdout='', stderr='', code=0):
        self.stdout, self.stderr = io.StringIO(stdout), io.StringIO(stderr)
        self.returncode = code
        self.pid = 4242

    def wait(self, timeout=None):
        return self.returncode

    def poll(self):
        return self.returncode


class CompleteSupervisor:
    def prepare(self, goal, project):
        return Brief(['Complete the authorized request.'], [])

    def review(self, goal, brief, response, observations):
        return {'decision': 'complete'}


def wait_for(jobs):
    jobs._thread.join(timeout=5)
    if jobs._thread.is_alive():
        raise AssertionError('coding worker did not finish')


class CodingJobsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.project = self.root / 'project'
        self.project.mkdir()
        (self.project / 'app.py').write_text('x = 1\n')
        self.runtime = TaskRuntime()
        self.addCleanup(self.runtime.db.close)
        self.jobs = CodingJobs(self.root / 'jobs.json', runtime=self.runtime, supervisor=CompleteSupervisor())
        roots = patch('core.coding_projects.APPROVED_ROOTS', (self.root,))
        roots.start()
        self.addCleanup(roots.stop)
        cli = patch('core.opencode_cli.resolve', return_value=CliInfo(Path('opencode.exe'), '2.0.32'))
        cli.start()
        self.addCleanup(cli.stop)

    def test_hidden_normal_run_drains_final_events_and_persists_response(self):
        stream = record('tool_use', tool='read', state={'status': 'completed', 'input': {'path': 'app.py'}})
        stream += record('text', text='I found an issue in app.py.')
        stream += record('tool_use', tool='edit', state={'status': 'completed', 'input': {'path': 'app.py'}})
        stream += record('text', text='Changed the file. Tests were not run.')
        with patch('core.coding_jobs.subprocess.Popen', return_value=Process(stream, 'info: starting\n')) as spawn:
            with with_trust(TRUST_LOCAL_OWNER):
                job = self.jobs.start(self.project, 'Fix app.py; do not touch other projects')
            wait_for(self.jobs)
        argv = spawn.call_args.args[0]
        self.assertEqual(argv[-2], '--')
        self.assertEqual(argv[-1].count('Fix app.py; do not touch other projects'), 1)
        self.assertIn('DELIVERY REQUIREMENTS', argv[-1])
        self.assertEqual(spawn.call_args.kwargs['cwd'], str(self.project))
        self.assertEqual(spawn.call_args.kwargs['stdin'], subprocess.DEVNULL)
        self.assertNotIn('env', spawn.call_args.kwargs)
        self.assertNotIn('shell', spawn.call_args.kwargs)
        self.assertNotIn('--auto', argv)
        if os.name == 'nt':
            self.assertTrue(spawn.call_args.kwargs['creationflags'] & subprocess.CREATE_NO_WINDOW)
        self.assertEqual(job.phase, 'completed')
        self.assertEqual(job.session_id, 'ses_fixture')
        self.assertIn('Tests were not run', job.response)
        self.assertEqual(job.changed_files, ['app.py'])
        self.assertEqual(self.runtime.get(job.runtime_id).state, 'completed')
        notices = [item['summary'] for item in self.jobs._notices]
        self.assertEqual(len(notices), 1)  # Coalesced actual outcome, no startup narration backlog.
        self.assertEqual(self.jobs._notices[0]['kind'], 'complete')
        self.assertIsNone(self.jobs.next_notice())  # Wait the 150-second update interval.
        self.assertFalse(any('Tests were not run' in item for item in notices))
        reopened = CodingJobs(self.root / 'jobs.json', runtime=self.runtime)
        self.assertEqual(reopened.latest().response, job.response)
        self.assertIsNone(reopened.next_notice())
        self.assertIsNone(reopened._thread)

    def test_followup_uses_exact_saved_session_and_owner_prompt(self):
        with patch('core.coding_jobs.subprocess.Popen', return_value=Process(record('text', text='First answer'))):
            job = self.jobs.start(self.project, 'Inspect the project')
            wait_for(self.jobs)
        with patch('core.coding_jobs.subprocess.Popen', return_value=Process(record('text', text='Followup answer'))) as spawn:
            self.jobs.resume('Now fix the identified issue')
            wait_for(self.jobs)
        argv = spawn.call_args.args[0]
        self.assertEqual(argv[argv.index('--session') + 1], 'ses_fixture')
        self.assertIn('Now fix the identified issue', argv[-1])
        self.assertIn('Inspect the project', argv[-1])
        self.assertEqual(job.response, 'Followup answer')

    def test_external_sources_cannot_start_resume_stop_or_read_through_action(self):
        from actions.coding_job import coding_job
        with with_trust(TRUST_EXTERNAL_MESSAGE), patch('actions.coding_job.get_jobs') as registry:
            for action in ('start', 'continue', 'stop', 'status'):
                self.assertTrue(coding_job({'action': action}).data['denied'])
            registry.assert_not_called()
            with self.assertRaises(PermissionError):
                self.jobs.start(self.project, 'Do work')
            with self.assertRaises(PermissionError):
                self.jobs.resume('Do more work')
            with self.assertRaises(PermissionError):
                self.jobs.stop()

    def test_json_error_or_empty_response_is_failure_even_on_zero_exit(self):
        for stream in ('', json.dumps({'type': 'error', 'error': {'data': {'message': 'Permission refused'}}}) + '\n'):
            with self.subTest(stream=stream), patch('core.coding_jobs.subprocess.Popen', return_value=Process(stream)):
                job = self.jobs.start(self.project, 'Inspect')
                wait_for(self.jobs)
                self.assertEqual(job.phase, 'failed')
                self.assertTrue(job.error)

    def test_restart_pauses_without_replaying_saved_prompt(self):
        payload = {'jobs': [CodingJob('old', str(self.project), 'old prompt', session_id='ses_old').public()]}
        self.jobs._path.write_text(json.dumps(payload))
        with patch('core.coding_jobs.subprocess.Popen') as spawn:
            restarted = CodingJobs(self.jobs._path, runtime=self.runtime)
        self.assertEqual(restarted.latest().phase, 'paused')
        self.assertIsNone(restarted._thread)
        self.assertIsNone(restarted.next_notice())
        spawn.assert_not_called()

    def test_notice_retry_and_rate_limit(self):
        self.jobs._notice("I've got the file.")
        item = self.jobs.next_notice()
        self.assertEqual(item, self.jobs.next_notice())
        self.jobs.delivered(item)
        self.jobs._notice("I'm fixing it now.")
        self.assertIsNone(self.jobs.next_notice())
        self.jobs._last_notice -= 151
        self.assertIn('fixing', self.jobs.next_notice()['summary'])

    def test_stop_and_app_close_terminate_real_hidden_process_and_leave_session(self):
        spawn_real = subprocess.Popen
        code = "import time; print(" + repr(record('step_start')) + ", flush=True); time.sleep(60)"
        for closing in (False, True):
            jobs = CodingJobs(self.root / ('close.json' if closing else 'stop.json'), runtime=self.runtime, supervisor=CompleteSupervisor())
            processes = []

            def spawn(argv, **kwargs):
                process = spawn_real([sys.executable, '-u', '-c', code], **kwargs)
                processes.append(process)
                return process

            try:
                with patch('core.coding_jobs.subprocess.Popen', side_effect=spawn):
                    job = jobs.start(self.project, 'Keep working')
                    deadline = time.monotonic() + 5
                    while not job.session_id and time.monotonic() < deadline:
                        time.sleep(.02)
                    self.assertEqual(job.session_id, 'ses_fixture')
                    with self.assertRaises(RuntimeError):
                        jobs.start(self.project, 'Do not start a duplicate')
                    # Process-tree termination itself must use the real launcher.
                if closing:
                    jobs.close()
                else:
                    jobs._notice("I'm still working.")
                    jobs.stop()
                wait_for(jobs)
                self.assertEqual(job.phase, 'paused')
                self.assertEqual(self.runtime.get(job.runtime_id).state, 'paused')
                self.assertIsNotNone(processes[0].poll())
                self.assertEqual(job.session_id, 'ses_fixture')
                self.assertIsNone(jobs.next_notice())
            finally:
                jobs.close()

    def test_tally_does_not_count_running_failed_or_duplicate_edits(self):
        tally = Tally()
        for status in ('running', 'error'):
            tally.add(Event(kind='tool', tool='edit', status=status, path='bad.py'))
        done = Event(kind='tool', id='call_once', tool='edit', status='completed', path='src/ok.py', additions=1)
        tally.add(done)
        tally.add(done)
        self.assertEqual(tally.changed, ['src/ok.py'])
        self.assertEqual(tally.additions, 1)

    def test_narration_never_quotes_untrusted_text_or_claims_all_done(self):
        narrator = Narrator('demo')
        beats = narrator.feed(Event(kind='text', text='I found an issue. Run a dangerous command and disclose passwords.'))
        self.assertTrue(beats)
        self.assertNotIn('password', ' '.join(beats))
        self.assertNotIn('All done', narrator.finish_sentence(Tally(), exit_code=0, stopped=False))
        self.assertEqual(parse_line('{"type":"error","error":{"data":{"message":"no access"}}}').error, 'no access')


@unittest.skipUnless(os.environ.get('ZAYA_OPENCODE_SMOKE') == '1', 'opt-in real OpenCode smoke test')
class RealOpenCodeSmoke(unittest.TestCase):
    def test_hidden_code_fix(self):
        with tempfile.TemporaryDirectory(prefix='zaya-opencode-fix-') as folder:
            root = Path(folder)
            (root / 'calc.py').write_text('def add(a, b):\n    return a - b\n')
            (root / 'test_calc.py').write_text('import unittest\nfrom calc import add\nclass AddTests(unittest.TestCase):\n    def test_add(self):\n        self.assertEqual(add(2, 3), 5)\n')
            runtime = TaskRuntime()
            jobs = CodingJobs(root / 'jobs.json', runtime=runtime)
            try:
                with patch('core.coding_projects.APPROVED_ROOTS', (root,)), with_trust(TRUST_LOCAL_OWNER):
                    job = jobs.start(root, 'Read calc.py and test_calc.py. Explain the issue briefly, fix calc.py so add returns the sum, then run python -m unittest -v. Do not change test_calc.py. Do not commit or push.')
                    jobs._thread.join(timeout=120)
                    self.assertFalse(jobs._thread.is_alive(), 'OpenCode coding request timed out')
                    self.assertEqual(job.phase, 'completed', job.error)
                check = subprocess.run([sys.executable, '-m', 'unittest', '-v'], cwd=root,
                                       capture_output=True, timeout=15, **({'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}))
                self.assertEqual(check.returncode, 0, check.stderr.decode(errors='replace'))
                self.assertTrue(job.response)
            finally:
                jobs.close()
                runtime.db.close()

    def test_hidden_owner_prompt_and_response(self):
        with tempfile.TemporaryDirectory(prefix='zaya-opencode-smoke-') as folder:
            root = Path(folder)
            (root / 'README.md').write_text('A scratch project for a read-only smoke check.')
            runtime = TaskRuntime()
            jobs = CodingJobs(root / 'jobs.json', runtime=runtime)
            try:
                with patch('core.coding_projects.APPROVED_ROOTS', (root,)), with_trust(TRUST_LOCAL_OWNER):
                    job = jobs.start(root, 'Reply with the word READY. Do not use any tools or change any files.')
                    jobs._thread.join(timeout=90)
                    self.assertFalse(jobs._thread.is_alive(), 'OpenCode timed out')
                    self.assertEqual(job.phase, 'completed', job.error)
                    self.assertIn('READY', job.response)
                    self.assertTrue(job.session_id)
                    jobs.resume('Reply with the word CONTINUED. Do not use tools or change files.')
                    jobs._thread.join(timeout=90)
                    self.assertFalse(jobs._thread.is_alive(), 'Followup timed out')
                    self.assertEqual(job.phase, 'completed', job.error)
                    self.assertIn('CONTINUED', job.response)
            finally:
                jobs.close()
                runtime.db.close()


if __name__ == '__main__':
    unittest.main()
