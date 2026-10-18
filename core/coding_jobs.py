"""Owner-started OpenCode sessions, with durable state and local voice notices.

OpenCode runs with its installed settings. Zaya owns the prompt and reads the
JSON response stream; this module does not inject permissions or auto-approve.
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
from core.coding_projects import resolve_project
from core.execution_policy import get_trust, require_owner
from core.opencode_events import Tally, parse_line
from core.opencode_narrator import Narrator
from core.shell_session import terminate_tree
from core.task_runtime import get_runtime

STORE_PATH = Path(__file__).resolve().parent.parent / 'memory' / 'coding_jobs.json'
ACTIVE = {'starting', 'working'}
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

    def public(self):
        return audit.redact(asdict(self))


class CodingJobs:
    def __init__(self, store_path=None, *, runtime=None):
        self._path = Path(store_path) if store_path else STORE_PATH
        self._runtime = runtime
        self._lock = threading.RLock()
        self._jobs = {}
        self._process = None
        self._thread = None
        self._stop = threading.Event()
        self._closed = False
        self._notices = deque(maxlen=16)
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
            temp.write_text(json.dumps({'version': 1, 'jobs': [j.public() for j in self._jobs.values()]}), encoding='utf-8')
            temp.replace(self._path)

    def all(self):
        with self._lock:
            return sorted(self._jobs.values(), key=lambda j: j.updated_at, reverse=True)

    def active(self):
        return next((j for j in self.all() if j.phase in ACTIVE), None)

    def latest(self):
        return next(iter(self.all()), None)

    def _notice(self, text):
        with self._lock:
            if not self._closed:
                self._notices.append({'id': uuid.uuid4().hex, 'summary': text, 'at': time.monotonic()})

    def next_notice(self):
        with self._lock:
            now = time.monotonic()
            while self._notices and now - self._notices[0]['at'] > 180:
                self._notices.popleft()
            if not self._notices or now - self._last_notice < 5:
                return None
            return dict(self._notices[0])

    def delivered(self, item):
        with self._lock:
            if self._notices and self._notices[0]['id'] == item['id']:
                self._notices.popleft()
                self._last_notice = time.monotonic()

    def _available(self):
        if self._closed:
            raise RuntimeError('Zaya is closing.')
        if self._thread is not None and self._thread.is_alive():
            raise RuntimeError('I am already working on a coding request. Ask me to stop it first.')

    def start(self, project, goal, *, agent='', model=''):
        require_owner()
        project = resolve_project(str(project))
        if not goal.strip():
            raise ValueError('Tell me what you want done in the project.')
        with self._lock:
            self._available()
            job = CodingJob(uuid.uuid4().hex[:12], str(project), goal, agent=agent, model=model)
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
            resolve_project(job.project)
            if task.strip():
                job.goal = task.strip()
            elif job.phase == 'completed':
                raise ValueError('That request finished. Tell me what to do next in this session.')
            else:
                job.goal = 'Continue the unfinished request. Inspect current files and previous results before repeating any action.'
            self._begin(job)
        return job

    def _begin(self, job):
        self._stop.clear()
        self._notices.clear()
        job.phase, job.response, job.error, job.exit_code = 'starting', '', '', None
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
        process = None
        diagnostics = ''
        try:
            info = opencode_cli.resolve()
            if self._stop.is_set():
                return
            argv = [str(info.path), 'run', '--format', 'json']
            if opencode_cli.version_key(info.version)[0] >= 2:
                argv.append('--standalone')
            if job.session_id:
                argv += ['--session', job.session_id]
            if job.agent:
                argv += ['--agent', job.agent]
            if job.model:
                argv += ['--model', job.model]
            # The only prompt is Zaya's owner-authorized request, passed as data.
            argv += ['--', job.goal]
            process = subprocess.Popen(argv, cwd=job.project, stdin=subprocess.DEVNULL,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                       encoding='utf-8', errors='replace', bufsize=1, **_HIDDEN)
            with self._lock:
                self._process = process
                job.phase = 'working'
                job.progress = 'reading the project'
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
                    beat = narrator.heartbeat()
                    if beat and not self._stop.is_set():
                        self._notice(beat)
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
                job.changed_files = list(tally.changed)
                for beat in narrator.feed(event):
                    job.progress = narrator.progress
                    self._notice(beat)
                job.updated_at = time.time()
                if time.monotonic() - last_save > 1:
                    self._save()
                    last_save = time.monotonic()
            for reader in readers:
                reader.join(timeout=1)
            process.wait(timeout=10)
            job.exit_code = process.returncode
            if not self._stop.is_set():
                job.phase = 'completed' if process.returncode == 0 and job.response and not job.error else 'failed'
                if job.phase == 'failed' and not job.error:
                    job.error = diagnostics or ('OpenCode ended without a response.' if process.returncode == 0 else 'OpenCode exited with an error.')
                job.progress = 'response received' if job.phase == 'completed' else 'could not finish'
                self._notice(narrator.finish_sentence(tally, exit_code=0 if job.phase == 'completed' else 1, stopped=False))
        except Exception as error:
            job.phase, job.error = 'failed', audit.redact(str(error))[:2000]
            job.progress = 'could not finish'
            self._notice("I couldn't finish the coding request. I've kept the session details so I can check it.")
        finally:
            if process is not None:
                terminate_tree(process)
                process.wait(timeout=10)
            with self._lock:
                self._process = None
                if self._stop.is_set():
                    job.phase, job.progress = 'paused', 'stopped; ask me to continue'
                job.updated_at = time.time()
                self._save()
            state = 'paused' if job.phase == 'paused' else job.phase
            self.runtime.transition(job.runtime_id, state,
                                    error=job.error or None,
                                    evidence=[{'session_id': job.session_id, 'exit_code': job.exit_code,
                                               'changed_files': job.changed_files}])

    def stop(self):
        require_owner()
        with self._lock:
            job = self.active()
            if job is None:
                raise ValueError('There is no coding work to stop.')
            self._stop.set()
            self._notices.clear()
            process = self._process
        if process is not None:
            terminate_tree(process)
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
