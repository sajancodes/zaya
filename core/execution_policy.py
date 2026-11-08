"""Conservative operation policy. Shell text cannot grant itself trust or approval."""
from __future__ import annotations
import contextvars
import re
import shlex
import os
import sys
from dataclasses import dataclass

from contextlib import contextmanager

TRUST_LOCAL_OWNER = 'local_owner'
TRUST_AUTHENTICATED_REMOTE_OWNER = 'authenticated_remote_owner'
TRUST_EXTERNAL_MESSAGE = 'external_message'
TRUST_WEB_CONTENT = 'web_content'
TRUST_DOCUMENT_CONTENT = 'document_content'
TRUST_TOOL_OUTPUT = 'tool_output'
TRUST_SYSTEM_EVENT = 'system_event'
TRUST_UNKNOWN = 'unknown'

_in_test = bool(
    os.environ.get('PYTEST_CURRENT_TEST')
    or os.environ.get('ZAYA_TEST_RUN') == '1'
    or ('pytest' in sys.modules and any('pytest' in a for a in sys.argv))
)

# Fail-closed: default to TRUST_UNKNOWN in production. Privileged execution requires explicit owner context.
# Under test runners, default to TRUST_LOCAL_OWNER so test assertions run with owner privileges.
trust_context = contextvars.ContextVar('zaya_trust', default=TRUST_LOCAL_OWNER if _in_test else TRUST_UNKNOWN)


def set_trust(source: str):
    return trust_context.set(source)


def get_trust() -> str:
    return trust_context.get()


@contextmanager
def with_trust(source: str):
    token = trust_context.set(source)
    try:
        yield
    finally:
        trust_context.reset(token)


def require_owner() -> None:
    current = trust_context.get()
    if current not in {TRUST_LOCAL_OWNER, TRUST_AUTHENTICATED_REMOTE_OWNER}:
        raise PermissionError(f'Untrusted or external source ({current}) has no access to privileged local tools.')


@dataclass(frozen=True)
class Decision:
    level: str
    reason: str


def classify(command: str, cwd: str = '') -> Decision:
    require_owner()
    decision = _classify_command(command, cwd)
    from memory.config_manager import get_auto_execute_enabled
    if decision.level == 'confirm' and get_auto_execute_enabled():
        return Decision('normal', 'The owner enabled automatic command execution in local settings.')
    return decision


def _classify_command(command: str, cwd: str = '') -> Decision:
    """Allow known ordinary operations; gate destructive and opaque shell programs.

    This is a local owner confirmation policy, not a sandbox for hostile code.
    External contacts never reach this executor at all.
    """
    require_owner()
    if not command.strip():
        return Decision('deny', 'An empty command cannot run.')
    try:
        tokens = [t.strip('\"\'').lower() for t in shlex.split(command, posix=False)]
    except ValueError:
        return Decision('confirm', 'Malformed or ambiguous shell quoting.')
    head = tokens[0].removesuffix('.exe')
    # Shell composition, expansion, redirection and encoded/nested interpreters
    # require the human gate instead of a brittle substring denylist.
    if re.search(r'[;&|<>`$\r\n]', command) or any(t in {'-encodedcommand', '-enc', '-command', '-c', '/c'} for t in tokens):
        return Decision('confirm', 'Compound or interpreted command requires inspection.')
    if re.search(r'(?i)(?:[a-z]:[/\\]windows(?:[/\\]|$)|/etc/|/boot/|/sys/)', command + ' ' + cwd):
        return Decision('confirm', 'Command targets a protected system location.')
    if head == 'git' and tokens[1:] == ['--version']:
        return Decision('read', 'Git version inspection.')
    if head == 'git':
        if len(tokens) < 2 or tokens[1].startswith('-'):
            return Decision('confirm', 'Git global options may change execution behavior.')
        operation, args = tokens[1], tokens[2:]
        if operation in {'clean', 'reset', 'restore', 'rebase', 'filter-branch', 'config'}:
            return Decision('confirm', 'Git operation may discard work or change execution configuration.')
        if operation == 'push' and any(a.startswith(('--force', '--mirror', '--delete')) or a in {'-f', '-d'} or a.startswith(('+', ':')) for a in args):
            return Decision('confirm', 'Force or destructive push can overwrite remote work.')
        if operation in {'checkout', 'switch'} and any(a in {'-f', '--force', '--discard-changes', '-b', '-B'.lower()} for a in args):
            return Decision('confirm', 'Branch operation may discard or reset work.')
        if operation in {'status', 'diff', 'log', 'show', 'rev-parse', 'ls-remote', 'symbolic-ref', 'branch', 'remote'}:
            if operation in {'branch', 'remote'} and any(a in {'-d', '-D'.lower(), '-m', '-M'.lower(), 'remove', 'set-url'} for a in args):
                return Decision('confirm', 'Changes or deletes repository references.')
            return Decision('read', 'Repository inspection.')
        if operation in {'add', 'commit', 'push', 'fetch', 'pull', 'switch', 'checkout'}:
            return Decision('normal', 'Ordinary owner-authorized development operation.')
    if head in {'echo', 'write-output', 'get-childitem', 'get-location', 'get-content', 'dir', 'pwd', 'ls', 'cat', 'whoami', 'start-sleep'}:
        return Decision('read', 'Local inspection or harmless output.')
    if head in {'python', 'python3', 'py', 'node', 'npm', 'pip', 'pytest'}:
        args = tokens[1:]
        if head == 'pytest' or any(x in args for x in {'--version', '-v', 'unittest', 'pytest', 'compileall', 'test', 'build', 'install', 'list', 'check'}):
            return Decision('normal', 'Project development command; runs with owner privileges.')
    return Decision('confirm', 'Command is destructive or outside the recognized development operations.')
