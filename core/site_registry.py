"""Canonical site names, repository URLs, and navigation postconditions."""
from __future__ import annotations
import re
from urllib.parse import urlsplit, urlunsplit

SITES = {'github': 'https://github.com/', 'whatsapp': 'https://web.whatsapp.com/',
         'whatsapp web': 'https://web.whatsapp.com/', 'gmail': 'https://mail.google.com/',
         'youtube': 'https://www.youtube.com/'}
browser_state: dict = {}


def resolve_url(value: str) -> str:
    value = SITES.get(value.strip().casefold(), value.strip())
    if not value:
        return 'about:blank'
    if value == 'about:blank':
        return value
    if value.startswith('git@'):
        return normalize_git_remote(value)
    if '://' not in value:
        value = 'https://' + value
    parts = urlsplit(value)
    if parts.scheme not in {'http', 'https'} or not parts.hostname or parts.username or parts.password or re.search(r'\s', parts.netloc):
        raise ValueError('A valid HTTP(S) URL without embedded credentials is required.')
    if '.' not in parts.hostname and parts.hostname != 'localhost':
        raise ValueError('Unknown site name; provide an exact URL or use search.')
    # Accessing port validates malformed numeric ports.
    _ = parts.port
    return value


def normalize_git_remote(value: str) -> str:
    match = re.fullmatch(r'git@([^:]+):([^\s]+)', value)
    if match:
        value = 'https://' + match[1] + '/' + match[2]
    if value.startswith('ssh://git@'):
        value = 'https://' + value[len('ssh://git@'):]
    value = resolve_url(value)
    parts = urlsplit(value)
    if len(parts.path.strip('/').split('/')) < 2:
        raise ValueError('Remote URL does not identify a repository.')
    return urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip('/').removesuffix('.git'), '', ''))


def matches(expected: str, actual: str) -> bool:
    a, b = urlsplit(expected), urlsplit(actual)
    return (a.hostname, a.port, a.path.rstrip('/')) == (b.hostname, b.port, b.path.rstrip('/')) and b.scheme in {'http', 'https'}
