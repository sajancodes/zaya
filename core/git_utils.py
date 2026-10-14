"""Structured Git operations with explicit paths and verified remote heads."""
from __future__ import annotations
import re
from pathlib import Path
from core.execution_policy import require_owner
from core.shell_session import sessions
from core.tool_result import ToolResult

SECRET_PATH = re.compile(r'(?i)(^|/)(\.env(?:\..*)?|api_keys\.json|.*(?:credentials|client_secret|token).*\.json|.*\.(?:key|pem)|long_term\.json|.*\.db(?:-wal|-shm)?|(?:certs|whatsapp_web|hermes|sessions)(?:/|$))')
SECRET_CONTENT = re.compile(r'(?:AIza[\w-]{30,}|gh[pousr]_[\w]{30,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)')


def resolve_repo(path: str) -> Path:
    candidate = Path(path).expanduser()
    if not candidate.is_dir():
        from memory.project_index import resolve_project
        candidate = resolve_project(path)
    result = sessions.run_argv(['git', 'rev-parse', '--show-toplevel'], candidate.resolve(), timeout=15)
    if result.status != 'success':
        raise ValueError(f'Not a Git repository: {candidate}')
    return Path(result.data['stdout'].strip()).resolve()


class GitRepo:
    def __init__(self, path: str | Path) -> None:
        self.path = resolve_repo(str(path))

    def run(self, *args: str, timeout: int = 60) -> ToolResult:
        return sessions.run_argv(['git', *args], self.path, timeout)

    def text(self, *args: str) -> str:
        result = self.run(*args)
        if result.status != 'success':
            raise RuntimeError(result.data.get('stderr') or result.summary)
        return result.data['stdout'].strip()

    def branch(self, name: str) -> str:
        if name.startswith('-') or self.run('check-ref-format', '--branch', name).status != 'success':
            raise ValueError('Invalid branch name.')
        return name

    def safe_paths(self, paths: list[str]) -> list[str]:
        if not paths:
            raise ValueError('Specify intended files explicitly before staging.')
        checked = []
        for value in paths:
            path = (self.path / value).resolve()
            if not path.is_relative_to(self.path) or value.startswith('-') or any(c in value for c in '*?['):
                raise ValueError('Paths must be explicit and inside the repository.')
            checked.append(path.relative_to(self.path).as_posix())
        candidates = self.text('ls-files', '-z', '--cached', '--others', '--exclude-standard', '--', *checked).split('\0')
        for name in filter(None, candidates):
            if SECRET_PATH.search(name):
                raise ValueError(f'Refusing to stage private file: {name}')
            file = self.path / name
            if file.is_symlink():
                raise ValueError(f'Inspect symbolic link manually: {name}')
            if file.is_file() and file.stat().st_size < 2_000_000:
                if SECRET_CONTENT.search(file.read_text(encoding='utf-8', errors='ignore')):
                    raise ValueError(f'Possible secret in {name}; inspect before staging.')
        return checked

    def verify_push(self, remote: str = 'origin', branch: str | None = None) -> ToolResult:
        if not re.fullmatch(r'[\w.-]+', remote) or remote.startswith('-'):
            raise ValueError('Use a configured remote name.')
        branch = self.branch(branch or self.text('symbolic-ref', '--short', 'HEAD'))
        head = self.text('rev-parse', 'HEAD')
        result = self.run('ls-remote', '--exit-code', remote, f'refs/heads/{branch}')
        if result.status != 'success':
            return ToolResult('partial', 'Remote verification could not be completed.', result.data,
                              [{'local_sha': head, 'remote_verified': False}])
        remote_sha = result.data['stdout'].split()[0] if result.data['stdout'].split() else None
        ok = head == remote_sha
        return ToolResult('success' if ok else 'failed', 'Remote branch matches local HEAD.' if ok else 'Remote branch does not match local HEAD.',
                          {'branch': branch, 'remote': remote, 'local_sha': head, 'remote_sha': remote_sha},
                          [{'local_sha': head, 'remote_sha': remote_sha, 'match': ok}])

    def operate(self, operation: str, parameters: dict) -> ToolResult:
        require_owner()
        branch, remote = parameters.get('branch'), parameters.get('remote', 'origin')
        readonly = {'repo_info': ('status', '--porcelain=v1', '-b'), 'status': ('status', '--porcelain=v1', '-b'),
                    'diff': ('diff', '--no-ext-diff'), 'diff_staged': ('diff', '--cached', '--no-ext-diff'),
                    'branches': ('branch', '-avv'), 'log': ('log', '-10', '--oneline'), 'remote': ('remote', '-v')}
        if operation in readonly:
            result = self.run(*readonly[operation])
            result.side_effect = False
            return result
        if operation in {'checkout', 'create_branch'}:
            return self.run('switch', *(['-c'] if operation == 'create_branch' else []), self.branch(branch or ''))
        if operation in {'fetch', 'pull', 'push', 'verify_push'}:
            if not re.fullmatch(r'[\w.-]+', remote) or remote.startswith('-'):
                raise ValueError('Use a configured remote name.')
            if operation == 'verify_push':
                return self.verify_push(remote, branch)
            if operation == 'fetch':
                return self.run('fetch', remote)
            if operation == 'pull':
                return self.run('pull', '--ff-only', remote, self.branch(branch or self.text('symbolic-ref', '--short', 'HEAD')))
            active = self.text('symbolic-ref', '--short', 'HEAD')
            if branch and branch != active:
                raise ValueError('Push verifies the checked-out branch; switch branches first.')
            result = self.run('push', '-u', remote, self.branch(active), timeout=120)
            if result.status != 'success':
                return result
            verified = self.verify_push(remote, active)
            verified.side_effect = True
            verified.evidence.insert(0, {'push_exit_code': 0})
            return verified
        if operation == 'stage':
            paths = self.safe_paths(parameters.get('paths', []))
            result = self.run('add', '--', *paths)
            if result.status == 'success':
                result.data['staged_diff'] = self.text('diff', '--cached', '--stat')
            return result
        if operation == 'unstage':
            paths = parameters.get('paths', [])
            if not paths:
                raise ValueError('Specify files to unstage.')
            return self.run('restore', '--staged', '--', *self.safe_paths(paths))
        if operation == 'commit':
            message = parameters.get('message', '').strip()
            if not message:
                raise ValueError('A commit message is required.')
            names = self.text('diff', '--cached', '--name-only', '-z').split('\0')
            if not any(names):
                return ToolResult('failed', 'There are no staged changes to commit.')
            for name in filter(None, names):
                if SECRET_PATH.search(name):
                    raise ValueError(f'Private file in index: {name}')
                blob = self.run('show', f':{name}')
                if blob.status == 'success' and SECRET_CONTENT.search(blob.data['stdout']):
                    raise ValueError(f'Possible secret in staged file: {name}')
            check = self.run('diff', '--cached', '--check')
            if check.status != 'success':
                return check
            result = self.run('commit', '-m', message)
            if result.status == 'success':
                result.evidence.append({'commit_sha': self.text('rev-parse', 'HEAD')})
            return result
        if operation == 'open_remote':
            from core.site_registry import normalize_git_remote
            from actions.browser_control import browser_control
            url = normalize_git_remote(self.text('remote', 'get-url', remote))
            return browser_control({'action': 'go_to', 'url': url}, None)
        raise ValueError(f'Unsupported Git operation: {operation}')
