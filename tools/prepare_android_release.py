"""Package a signed APK and bounded metadata for the public update channel."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil


def prepare(apk, metadata, destination):
    apk, metadata, destination = Path(apk), Path(metadata), Path(destination)
    element = json.loads(metadata.read_text(encoding='utf-8'))['elements'][0]
    code, name = int(element['versionCode']), str(element['versionName'])
    if code <= 0 or not 0 < apk.stat().st_size <= 100 * 1024 * 1024:
        raise ValueError('Invalid APK version or size')
    destination.mkdir(parents=True, exist_ok=True)
    with apk.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    manifest = {'version_code': code, 'version_name': name,
                'sha256': digest, 'size': apk.stat().st_size}
    shutil.copyfile(apk, destination / 'Zaya-Companion.apk')
    (destination / 'update.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    (destination / 'notes.md').write_text(
        f'Zaya Companion {name}\n\n'
        'Install Zaya-Companion.apk to upgrade your existing app. Pairing and settings stay in place.\n\n'
        'The app checks for future releases automatically and offers Update now. '
        'Android asks before installation.\n', encoding='utf-8')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--apk', required=True)
    parser.add_argument('--metadata', required=True)
    parser.add_argument('--output', required=True)
    arguments = parser.parse_args()
    result = prepare(arguments.apk, arguments.metadata, arguments.output)
    print(f"Prepared Android {result['version_name']} (code {result['version_code']})")
