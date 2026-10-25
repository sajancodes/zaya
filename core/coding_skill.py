"""Optional, pinned OpenCode installation from its official GitHub release."""
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import urllib.request
import zipfile

from core.runtime_paths import get_user_data_dir

VERSION = '1.19.2'
URL = 'https://github.com/anomalyco/opencode/releases/download/v1.19.2/opencode-windows-x64.zip'
SHA256 = '86e6279183d5fc68e2c1c66160943551a427cf45bf700d6e492f03603db35f05'


def executable():
    return get_user_data_dir() / 'coding' / 'opencode.exe'


def status():
    path = executable()
    if not path.is_file():
        return 'Not installed'
    try:
        result = subprocess.run([str(path), '--version'], capture_output=True, text=True,
                                timeout=10, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        return 'Installed · ' + result.stdout.strip()[:50] if result.returncode == 0 else 'Error'
    except (OSError, subprocess.TimeoutExpired):
        return 'Error'


def install():
    if os.name != 'nt':
        raise RuntimeError('The managed Coding Skill package currently supports Windows x64 only.')
    target = executable()
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='zaya-coding-') as temporary:
        archive = Path(temporary) / 'opencode.zip'
        digest = hashlib.sha256()
        size = 0
        with urllib.request.urlopen(URL, timeout=60) as response, archive.open('wb') as output:
            while chunk := response.read(65536):
                size += len(chunk)
                if size > 100_000_000:
                    raise ValueError('Coding Skill archive exceeds its size limit.')
                digest.update(chunk); output.write(chunk)
        if digest.hexdigest() != SHA256:
            raise ValueError('Coding Skill checksum failed; nothing was installed.')
        with zipfile.ZipFile(archive) as package:
            entries = [entry for entry in package.infolist() if Path(entry.filename).name == 'opencode.exe']
            if len(entries) != 1 or entries[0].file_size > 250_000_000:
                raise ValueError('Unexpected official Coding Skill package layout.')
            staged = target.with_suffix('.tmp')
            with package.open(entries[0]) as source, staged.open('wb') as output:
                import shutil
                shutil.copyfileobj(source, output, 65536)
            staged.replace(target)
    return status()


def remove():
    # Only Zaya's managed binary is removed. Existing global installations,
    # provider authentication and projects are preserved.
    executable().unlink(missing_ok=True)
    return 'Not installed'
