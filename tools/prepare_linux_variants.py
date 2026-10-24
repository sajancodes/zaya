"""Package the verified native payload as Fedora RPM and a portable archive."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import platform
import re
import shlex
import shutil
import subprocess
import sys
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.prepare_linux_release import assert_clean_payload

RPM_DEPENDENCIES = (
    'glibc >= 2.35', 'libportaudio.so.2()(64bit)', 'libasound.so.2()(64bit)',
    'alsa-plugins-pulseaudio', 'libpulse.so.0()(64bit)', 'libEGL.so.1()(64bit)',
    'libGLESv2.so.2()(64bit)', 'libGL.so.1()(64bit)', 'libdbus-1.so.3()(64bit)',
    'libxcb-cursor.so.0()(64bit)', 'libxcb-icccm.so.4()(64bit)',
    'libxcb-keysyms.so.1()(64bit)', 'libxcb-xinerama.so.0()(64bit)',
    'libxkbcommon-x11.so.0()(64bit)', 'gnome-keyring', 'xdg-utils', 'xclip', 'ffmpeg-free',
)

PORTABLE_GUIDE = '''Zaya experimental portable Linux beta (x86-64)

Extract the archive, then run ./Zaya/Zaya as your normal desktop user.
Requires glibc 2.35 or newer, a desktop session and the OS libraries below.
Desktop automation requires X11; Wayland control is not fully supported.
Secure credentials require an unlocked Secret Service keyring.

Dependencies: PortAudio, ALSA with its PulseAudio plugin, libpulse, EGL/GLES/GL,
D-Bus, xcb cursor/icccm/keysyms/xinerama, xkbcommon-x11, gnome-keyring,
xdg-utils, xclip and FFmpeg. Package names vary by distribution.
Use the .deb on Ubuntu/Mint or the .rpm on Fedora for dependency installation.
This archive does not install dependencies or create a desktop launcher.

Settings, archives and credentials remain in ~/.zaya. Replacing the extracted
program folder does not remove that user data. Linux updates are manual.
This is unsigned beta software, not a certified release for every distribution.
Physical microphone/camera and desktop automation need real-device testing.
Older RHEL/Rocky/Alma releases with glibc below 2.35 are not compatible.
Official downloads and checksums: https://zayaxyz.vercel.app/download
Created and developed by Sajan Rai. Preserve bundled upstream credits/notices.
'''


def prepare(app: Path, output: Path):
    if sys.platform != 'linux' or platform.machine() != 'x86_64':
        raise RuntimeError('Build Linux x86-64 packages on Linux x86-64.')
    app, output = app.resolve(), output.resolve()
    assert_clean_payload(app)
    if any(char in str(output) for char in '\n\r%'):
        raise ValueError('RPM build paths cannot contain newlines or percent signs.')
    version = json.loads((ROOT / 'version.json').read_text())['version']
    if not re.fullmatch(r'\d+\.\d+\.\d+', version):
        raise ValueError('RPM variants require a numeric canonical version.')
    output.mkdir(parents=True, exist_ok=True)
    artifacts = [output / 'Zaya.rpm', output / 'Zaya-linux-x86_64.tar.gz']
    if any(path.exists() for path in [*artifacts, output / 'linux-variants.json']):
        raise FileExistsError('Refusing to overwrite Linux artifacts or metadata.')
    with tempfile.TemporaryDirectory(prefix='zaya-rpm-', dir=output) as temp:
        base = Path(temp)
        payload = base / 'payload'
        shutil.copytree(app, payload / 'opt/zaya', symlinks=True)
        for directory in ('usr/bin', 'usr/share/applications', 'usr/share/icons/hicolor/256x256/apps'):
            (payload / directory).mkdir(parents=True)
        launcher = payload / 'usr/bin/zaya'
        launcher.write_text('#!/bin/sh\nexec /opt/zaya/Zaya "$@"\n')
        launcher.chmod(0o755)
        (payload / 'usr/share/applications/zaya.desktop').write_text('[Desktop Entry]\nType=Application\nName=Zaya\nExec=/usr/bin/zaya\nIcon=zaya\nTerminal=false\nCategories=Utility;\n')
        from PIL import Image
        with Image.open(ROOT / 'assets/standby.png') as image:
            image.thumbnail((256, 256))
            image.save(payload / 'usr/share/icons/hicolor/256x256/apps/zaya.png')
        spec = base / 'zaya.spec'
        for directory in ('BUILD', 'BUILDROOT', 'RPMS', 'SOURCES', 'SPECS', 'SRPMS'):
            (base / 'rpmbuild' / directory).mkdir(parents=True, exist_ok=True)
        spec.write_text(f'''%global __os_install_post %{{nil}}
%global _build_id_links none
%global debug_package %{{nil}}
%global _binary_payload w3.zstdio
Name: zaya
Version: {version}
Release: 0.beta.2
Summary: Zaya desktop AI assistant (experimental Linux beta)
License: CC-BY-NC-4.0
URL: https://zayaxyz.vercel.app
Packager: Sajan Rai <ab4290025@gmail.com>
BuildArch: x86_64
AutoReqProv: no
''' + ''.join('Requires: ' + dependency + '\n' for dependency in RPM_DEPENDENCIES) + f'''
%description
Experimental unsigned native Linux beta. Requires glibc 2.35 or newer.
Desktop automation requires X11. Physical hardware testing remains necessary.
Created and developed by Sajan Rai; see bundled upstream and dependency credits.

%install
mkdir -p "%{{buildroot}}"
cp -a {shlex.quote(str(payload))}/. "%{{buildroot}}/"

%files
%defattr(-,root,root,-)
/opt/zaya
/usr/bin/zaya
/usr/share/applications/zaya.desktop
/usr/share/icons/hicolor/256x256/apps/zaya.png
''')
        subprocess.run(['rpmbuild', '-bb', '--define', f'_topdir {base / "rpmbuild"}',
                        '--define', '_buildhost zaya-builder', str(spec)], check=True)
        built = list((base / 'rpmbuild/RPMS/x86_64').glob('*.rpm'))
        if len(built) != 1:
            raise RuntimeError('Expected one native RPM artifact.')
        shutil.copyfile(built[0], artifacts[0])
    def clean_metadata(info):
        info.uid = info.gid = 0
        info.uname = info.gname = 'root'
        return info
    with tarfile.open(artifacts[1], 'w:gz', compresslevel=3) as archive:
        archive.add(app, arcname='Zaya', filter=clean_metadata)
        data = PORTABLE_GUIDE.encode()
        info = clean_metadata(tarfile.TarInfo('Zaya/LINUX-PORTABLE-README.txt'))
        info.size, info.mode = len(data), 0o644
        archive.addfile(info, io.BytesIO(data))
    manifest = {'version': version, 'channel': 'beta', 'architecture': 'x86_64',
                'minimum_glibc': '2.35', 'public_release_verified': False, 'artifacts': []}
    for artifact in artifacts:
        with artifact.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        manifest['artifacts'].append({'filename': artifact.name, 'sha256': digest, 'size': artifact.stat().st_size})
    (output / 'linux-variants.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=ROOT / 'dist/linux-variants')
    args = parser.parse_args()
    prepare(args.app_dir, args.output)
