"""Stage a native Debian candidate. Public promotion requires Linux verification."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def assert_clean_payload(app: Path):
    if not (app / 'Zaya').is_file() or not (app / 'ZayaHandWorker').is_file():
        raise ValueError('Both native application and hand worker binaries are required')
    for binary in ('Zaya', 'ZayaHandWorker'):
        with (app / binary).open('rb') as stream:
            if stream.read(4) != b'\x7fELF':
                raise ValueError('Linux packages require native ELF binaries, never Windows executables')
    forbidden = {'.env', 'config.json', 'settings.json', 'installation.json', 'service-account.json'}
    for path in app.rglob('*'):
        if path.is_symlink() and not path.resolve().is_relative_to(app.resolve()):
            raise ValueError('Packaged symlinks must remain inside the application payload')
        if path.name.lower() in forbidden or path.suffix.lower() in {'.db', '.sqlite', '.sqlite3', '.log', '.jks', '.pfx', '.dpapi'}:
            raise ValueError('Private runtime data or signing material found in candidate payload')


def prepare(app: Path, output: Path):
    if sys.platform != 'linux':
        raise RuntimeError('Linux release candidates must be assembled and tested on Linux')
    app, output = app.resolve(), output.resolve()
    assert_clean_payload(app)
    data = json.loads((ROOT / 'version.json').read_text(encoding='utf-8'))
    version, build = data['version'], data['build']
    if not re.fullmatch(r'\d+\.\d+\.\d+(?:-[A-Za-z0-9.-]+)?', version):
        raise ValueError('Invalid canonical Linux version')
    deb_version = version.replace('-', '~', 1)
    architecture = subprocess.check_output(['dpkg', '--print-architecture'], text=True).strip()
    if architecture != 'amd64':
        raise ValueError('Only the Linux amd64 candidate has a configured build path')
    output.mkdir(parents=True, exist_ok=True)
    artifact = output / 'Zaya.deb'
    if artifact.exists():
        raise FileExistsError('Refusing to overwrite a Linux artifact')
    with tempfile.TemporaryDirectory(prefix='zaya-deb-', dir=output) as temporary:
        stage = Path(temporary)
        shutil.copytree(app, stage / 'opt' / 'zaya', symlinks=True)
        def write(relative, text, executable=False):
            path = stage / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding='utf-8')
            path.chmod(0o755 if executable else 0o644)
        write('DEBIAN/control', f'Package: zaya\nVersion: {deb_version}\nArchitecture: amd64\nMaintainer: Sajan Rai <ab4290025@gmail.com>\nSection: utils\nPriority: optional\nDepends: libportaudio2, libasound2 | libasound2t64, libasound2-plugins, libpulse0, libegl1, libgles2, libgl1, libdbus-1-3, libxcb-cursor0, libxcb-icccm4, libxcb-keysyms1, libxcb-xinerama0, libxkbcommon-x11-0, gnome-keyring, xdg-utils, xclip, ffmpeg\nHomepage: https://zayaxyz.vercel.app\nDescription: Zaya personal AI assistant by Sajan Rai\n Native Linux candidate. Desktop automation requires a supported X11 session.\n Camera, microphone, keyring and clean installation require native verification.\n')
        write('usr/bin/zaya', '#!/bin/sh\nexec /opt/zaya/Zaya "$@"\n', executable=True)
        write('usr/share/applications/zaya.desktop', '[Desktop Entry]\nType=Application\nName=Zaya\nComment=Personal AI assistant by Sajan Rai\nExec=/usr/bin/zaya\nIcon=zaya\nTerminal=false\nCategories=Utility;\n')
        icon = stage / 'usr/share/icons/hicolor/256x256/apps/zaya.png'
        icon.parent.mkdir(parents=True)
        from PIL import Image
        with Image.open(ROOT / 'assets' / 'standby.png') as image:
            image.thumbnail((256, 256))
            image.save(icon, format='PNG')
        subprocess.run(['dpkg-deb', '-Zxz', '-z3', '--root-owner-group', '--build', str(stage), str(artifact)], check=True)
    with artifact.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    manifest = {'platform':'linux', 'version':version, 'build':build, 'channel':data['channel'],
                'filename':artifact.name, 'size':artifact.stat().st_size,
                'sha256':digest,
                'public_release_verified':False,
                'required_checks':['clean install', 'first startup', 'microphone', 'keyring', 'camera/worker', 'upgrade', 'uninstall preserving user data']}
    (output / 'linux-candidate.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=ROOT / 'dist/linux-candidate')
    args = parser.parse_args()
    prepare(args.app_dir, args.output)
