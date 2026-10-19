"""Owner-started OpenCode sessions, with durable state and local voice notices.

OpenCode runs with its installed settings. Zaya prepares the prompt, reads the
JSON stream, reviews results and sends bounded follow-ups in the same session.
This module does not inject permissions or auto-approve.
"""
from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass, field
import json
import os
from pathlib import Path
import queue
import subprocess
import threading
import time
import uuid

from core import audit, opencode_cli
from core.coding_projects import prepare_workspace, resolve_project
from core.coding_supervisor import Supervisor, MAX_PASSES, initial_prompt, followup_prompt
from core.execution_policy import get_trust, require_owner
from core.opencode_events import Tally, parse_line
from core.opencode_narrator import Narrator
from core.shell_session import terminate_tree
from core.task_runtime import get_runtime

STORE_PATH = Path(__file__).resolve().parent.parent / 'memory' / 'coding_jobs.json'
ACTIVE = {'starting', 'planning', 'working', 'reviewing'}
_HIDDEN = ({'creationflags': subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP}
           if os.name == 'nt' else {'start_new_session': True})


@dataclass
class CodingJob:
    id: str
    project: str
    goal: str
    phase: str = 'starting'
    session_id: str = ''
    runtime_id: str = ''
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    progress: str = 'starting'
    response: str = ''
    error: str = ''
    changed_files: list[str] = field(default_factory=list)
    exit_code: int | None = None
    agent: str = ''
    model: str = ''
    requirements: list[str] = field(default_factory=list)
    checks: list[str] = field(default_factory=list)
    prompt: str = ''
    pass_number: int = 0
    passes: list[dict] = field(default_factory=list)
    observations: list[dict] = field(default_factory=list)
    review: str = ''
    purpose: str = 'coding'

    def public(self):
        return audit.redact(asdict(self))


class CodingJobs:
    def __init__(self, store_path=None, *, runtime=None, supervisor=None, clock=time.monotonic):
        self._path = Path(store_path) if store_path else STORE_PATH
        self._runtime = runtime
        self._supervisor = supervisor or Supervisor()
        self._lock = threading.RLock()
        self._jobs = {}
        self._process = None
        self._thread = None
        self._stop = threading.Event()
        self._closed = False
        self._clock = clock
        self.updates_enabled = True
        self.update_interval = 150
        self._notices = deque(maxlen=16)
        self._notice_seen = set()
        self._notice_retry_at = 0.0
        self._last_notice = 0.0
        self._load()

    @property
    def runtime(self):
        if self._runtime is None:
            self._runtime = get_runtime()
        return self._runtime

    def _load(self):
        try:
            payload = json.loads(self._path.read_text(encoding='utf-8'))
            if isinstance(payload, dict):
                settings = payload.get('updates', {})
                self.updates_enabled = settings.get('enabled') is not False
                self.update_interval = max(120, min(180, int(settings.get('interval_seconds', 150))))
            rows = payload.get('jobs', []) if isinstance(payload, dict) else []
            for row in rows if isinstance(rows, list) else []:
                if not isinstance(row, dict):
                    continue
                try:
                    job = CodingJob(**{k: v for k, v in row.items() if k in CodingJob.__dataclass_fields__})
                except TypeError:
                    continue
                if job.phase in ACTIVE:
                    job.phase = 'paused'
                    job.progress = 'paused when Zaya closed; ask me to continue'
                self._jobs[job.id] = job
        except (OSError, ValueError):
            pass

    def _save(self):
        with self._lock:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            temp = self._path.with_suffix('.tmp')
            temp.write_text(json.dumps({'version': 1, 'updates': self.update_settings(),
                                        'jobs': [j.public() for j in self._jobs.values()]}), encoding='utf-8')
            temp.replace(self._path)

    def all(self):
        with self._lock:
            return sorted(self._jobs.values(), key=lambda j: j.updated_at, reverse=True)

    def active(self):
        return next((j for j in self.all() if j.phase in ACTIVE), None)

    def latest(self):
        return next(iter(self.all()), None)

    def update_settings(self):
        return {'enabled': self.updates_enabled, 'interval_seconds': self.update_interval}

    def configure_updates(self, *, enabled=None, interval_seconds=None):
        require_owner()
        if interval_seconds is not None and not 120 <= float(interval_seconds) <= 180:
            raise ValueError('Coding updates must be two to three minutes apart.')
        with self._lock:
            if enabled is not None:
                self.updates_enabled = bool(enabled)
            if interval_seconds is not None:
                self.update_interval = int(interval_seconds)
            self._notices.clear()
            self._last_notice = self._clock()
            self._save()
        return self.update_settings()

    def _notice(self, text, *, kind='progress'):
        with self._lock:
            if self._closed or self._stop.is_set() or not self.updates_enabled or text in self._notice_seen:
                return
            self._notice_seen.add(text)
            # Keep the newest development, not a backlog of narration beats.
            self._notices.clear()
            self._notices.append({'id': uuid.uuid4().hex, 'summary': text, 'kind': kind,
                                  'at': self._clock(), 'attempts': 0})

    def notice_current(self, item):
        with self._lock:
            return (not self._closed and not self._stop.is_set() and self.updates_enabled
                    and any(row['id'] == item.get('id') for row in self._notices))

    def notice_failed(self, item):
        with self._lock:
            for row in list(self._notices):
                if row['id'] == item.get('id'):
                    row['attempts'] += 1
                    self._notice_retry_at = self._clock() + self.update_interval
                    if row['attempts'] >= 2:
                        self._notices.remove(row)

    def next_notice(self):
        with self._lock:
            now = self._clock()
            while self._notices and now - self._notices[0]['at'] > 600:
                self._notices.popleft()
            if (not self._notices or not self.updates_enabled or self._stop.is_set()
                    or now - self._last_notice < self.update_interval or now < self._notice_retry_at):
                return None
            return dict(self._notices[0])

    def delivered(self, item):
        with self._lock:
            if self._notices and self._notices[0]['id'] == item['id']:
                self._notices.popleft()
                self._last_notice = self._clock()

    def execution_status(self):
        with self._lock:
            running = self._process is not None and self._process.poll() is None
            return {'process_running': running, 'pid': self._process.pid if running else None,
                    'worker_running': self._thread is not None and self._thread.is_alive(),
                    'cancellation_requested': self._stop.is_set(), 'updates': self.update_settings()}

    def _available(self):
        if self._closed:
            raise RuntimeError('Zaya is closing.')
        if self._thread is not None and self._thread.is_alive():
            raise RuntimeError('I am already working on a coding request. Ask me to stop it first.')

    def start(self, project, goal, *, agent='', model='', create_project=False, purpose='coding'):
        require_owner()
        if not goal.strip():
            raise ValueError('Tell me what you want done in the project.')
        with self._lock:
            self._available()
            project = prepare_workspace(str(project), purpose=purpose, create=create_project)
            # "auto"/"default" mean installed CLI settings, not model IDs.
            agent = '' if agent.strip().lower() in {'auto', 'default'} else agent.strip()
            model = '' if model.strip().lower() in {'auto', 'default'} else model.strip()
            job = CodingJob(uuid.uuid4().hex[:12], str(project), goal, agent=agent, model=model, purpose=purpose)
            self._jobs[job.id] = job
            self._begin(job)
        return job

    def resume(self, task=''):
        require_owner()
        with self._lock:
            self._available()
            job = self.latest()
            if job is None or not job.session_id:
                raise ValueError('There is no saved coding session to continue.')
            if job.purpose == 'coding':
                resolve_project(job.project, allow_empty=True)
            else:
                prepare_workspace(job.project, purpose=job.purpose)
            if task.strip():
                job.goal += '\nOwner follow-up: ' + task.strip()
            elif job.phase == 'completed':
                raise ValueError('That request finished. Tell me what to do next in this session.')
            self._begin(job)
        return job

    def _begin(self, job):
        self._stop.clear()
        self._notices.clear()
        self._notice_seen.clear()
        self._last_notice = self._clock()
        self._notice_retry_at = 0.0
        job.phase, job.response, job.error, job.exit_code = 'planning', '', '', None
        job.pass_number, job.passes, job.observations = 0, [], []
        job.requirements, job.checks, job.review, job.prompt = [], [], '', ''
        job.updated_at = time.time()
        task = self.runtime.create(job.goal, source='coding_job', trust_level=get_trust())
        job.runtime_id = task.id
        self.runtime.transition(task.id, 'executing', active_step='opencode')
        self._save()
        self._thread = threading.Thread(target=self._run, args=(job,), name='zaya-coding', daemon=True)
        self._thread.start()

    @staticmethod
    def _pump(stream, kind, output):
        try:
            for line in stream:
                output.put((kind, line))
        finally:
            stream.close()
            output.put((kind, None))

    def _run(self, job):
        narrator, tally = Narrator(Path(job.project).name), Tally()
        try:
            brief = self._supervisor.prepare(job.goal, job.project)
            if self._stop.is_set():
                return
            job.requirements, job.checks = brief.requirements, brief.checks
            job.prompt = initial_prompt(job.goal, job.project, brief)
            info = opencode_cli.resolve()
            for number in range(1, MAX_PASSES + 1):
                if self._stop.is_set():
                    break
                job.pass_number = number
                job.response, job.error = '', ''
                job.phase, job.progress = 'working', f'working on pass {number}'
                self.runtime.transition(job.runtime_id, 'executing', active_step=f'opencode pass {number}')
                self._save()
                self._run_pass(job, info, narrator, tally)
                if self._stop.is_set():
                    break
                job.passes.append({'pass': number, 'prompt': audit.redact(job.prompt),
                                   'response': job.response, 'exit_code': job.exit_code})
                if job.exit_code != 0 or job.error or not job.response:
                    job.phase = 'failed'
                    job.error = job.error or 'OpenCode ended without a usable response.'
                    self._notice("OpenCode reported a failure. I have the error details ready.", kind='error')
                    break
                job.phase, job.progress = 'reviewing', 'checking the result against your request'
                self.runtime.transition(job.runtime_id, 'verifying', active_step=f'review pass {number}')
                self._save()
                review = self._supervisor.review(job.goal, brief, job.response, job.observations)
                if self._stop.is_set():
                    break
                job.review = review.get('decision', 'blocked')
                job.passes[-1]['review'] = review
                if job.review == 'complete':
                    job.phase, job.progress = 'completed', 'reviewed against the request brief'
                    self._notice("OpenCode returned a result that passed the brief review. I have the reported changes and check results ready.", kind='complete')
                    break
                if job.review != 'continue' or number == MAX_PASSES:
                    job.phase = 'waiting_owner'
                    job.progress = 'needs owner input or further review'
                    job.error = ('The automatic review limit was reached; I have kept the remaining work.'
                                 if job.review == 'continue' else
                                 'The review needs owner input or could not be completed reliably.')
                    self._notice("I've kept the result, sir. I need your input before taking this further.", kind='blocked')
                    break
                if not job.session_id:
                    raise RuntimeError('OpenCode returned no session ID for a safe follow-up.')
                job.prompt = followup_prompt(brief, review)
        except Exception as error:
            job.phase, job.error = 'failed', audit.redact(str(error))[:2000]
            job.progress = 'could not finish'
            self._notice("The OpenCode request failed. I have the error details ready.", kind='error')
        finally:
            with self._lock:
                if self._stop.is_set():
                    job.phase, job.progress = 'paused', 'stopped; ask me to continue'
                job.updated_at = time.time()
                self._save()
            self.runtime.transition(job.runtime_id,
                                    'waiting_external' if job.phase == 'waiting_owner' else job.phase,
                                    error=job.error or None,
                                    evidence=[{'session_id': job.session_id, 'exit_code': job.exit_code,
                                               'changed_files': job.changed_files, 'passes': job.pass_number,
                                               'review': job.review}])

    def _run_pass(self, job, info, narrator, tally):
        argv = [str(info.path), 'run', '--format', 'json']
        if opencode_cli.version_key(info.version)[0] >= 2:
            argv.append('--standalone')
        if job.session_id:
            argv += ['--session', job.session_id]
        if job.agent:
            argv += ['--agent', job.agent]
        if job.model:
            argv += ['--model', job.model]
        argv += ['--', job.prompt]
        process = None
        diagnostics = ''
        try:
            if self._stop.is_set():
                return
            process = subprocess.Popen(argv, cwd=job.project, stdin=subprocess.DEVNULL,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                       encoding='utf-8', errors='replace', bufsize=1, **_HIDDEN)
            with self._lock:
                self._process = process
            messages = queue.Queue()
            readers = [threading.Thread(target=self._pump, args=(stream, kind, messages), daemon=True)
                       for stream, kind in ((process.stdout, 'out'), (process.stderr, 'err'))]
            for reader in readers:
                reader.start()
            closed, last_save = 0, 0.0
            while closed < 2:
                if self._stop.is_set():
                    terminate_tree(process)
                try:
                    kind, line = messages.get(timeout=.2)
                except queue.Empty:
                    continue
                if line is None:
                    closed += 1
                    continue
                if kind == 'err':
                    diagnostics = audit.redact((diagnostics + line)[-2000:])
                    continue
                event = parse_line(line)
                if event is None:
                    continue
                tally.add(event)
                if event.session_id:
                    job.session_id = event.session_id
                if event.kind == 'text':
                    job.response = audit.redact((job.response + '\n' + event.text)[-6000:]).strip()
                if event.kind == 'error':
                    job.error = audit.redact(event.error)
                if event.kind == 'tool' and event.status in {'completed', 'error'}:
                    job.observations = (job.observations + [audit.redact({
                        'tool': event.tool, 'status': event.status, 'path': event.path,
                        'command': event.command, 'exit_code': event.exit_code,
                        'error': event.error[:500]})])[-40:]
                job.changed_files = list(tally.changed)
                for beat in narrator.feed(event):
                    job.progress = narrator.progress
                    # Search, read, planning and heartbeat ticks stay silent.
                    if (event.failed or (event.kind == 'tool' and event.status == 'completed'
                            and (event.is_change or (event.tool in {'shell', 'bash'} and narrator.tests is not None)))):
                        self._notice(beat)
                job.updated_at = time.time()
                if time.monotonic() - last_save > 1:
                    self._save()
                    last_save = time.monotonic()
            for reader in readers:
                reader.join(timeout=1)
            process.wait(timeout=10)
            job.exit_code = process.returncode
            if process.returncode != 0 and not job.error:
                job.error = diagnostics or 'OpenCode exited with an error.'
        finally:
            if process is not None:
                terminate_tree(process)
                process.wait(timeout=10)
            with self._lock:
                self._process = None

    def stop(self):
        require_owner()
        with self._lock:
            self._stop.set()
            self._notices.clear()
            job = self.active()
            process = self._process
        if process is not None:
            terminate_tree(process)
        if self._thread is not None:
            self._thread.join(timeout=1)
        return job

    def close(self):
        with self._lock:
            self._closed = True
            self._stop.set()
            process = self._process
            self._notices.clear()
        if process is not None:
            terminate_tree(process)
        if self._thread is not None:
            self._thread.join(timeout=3)


_jobs = None
_jobs_lock = threading.Lock()


def get_jobs():
    global _jobs
    with _jobs_lock:
        if _jobs is None:
            _jobs = CodingJobs()
        return _jobs


def close_jobs():
    # Closing the app must not instantiate a registry or replay a saved job.
    if _jobs is not None:
        _jobs.close()
