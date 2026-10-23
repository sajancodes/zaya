"""Validate public artifact metadata before any download redirect."""
import re
from urllib.parse import urlparse


def validate_release(data):
    allowed = {'windows': ('ZayaSetup.exe', 'Zaya-Setup.exe'),
               'android': ('Zaya-Companion.apk',), 'linux': ('Zaya.AppImage', 'Zaya.deb')}
    if data.get('platform') not in allowed or data.get('filename') not in allowed[data['platform']]:
        raise ValueError('Unsupported release platform/filename.')
    url = urlparse(data.get('url', ''))
    if (url.scheme != 'https' or url.netloc != 'github.com'
            or not url.path.startswith('/sajancodes/zaya-companion-releases/releases/download/')
            or url.path.rsplit('/', 1)[-1] != data['filename'] or url.query or url.fragment):
        raise ValueError('An immutable official HTTPS artifact URL is required.')
    if not re.fullmatch(r'[0-9a-fA-F]{64}', data.get('sha256', '')) or not 1024 < int(data.get('size', 0)) <= 2_000_000_000:
        raise ValueError('Valid checksum and artifact size are required.')
    if not re.fullmatch(r'(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?', data.get('version', '')):
        raise ValueError('Invalid release version.')
    if data.get('channel', 'stable') not in ('stable', 'beta'):
        raise ValueError('Invalid release channel.')
    return data
