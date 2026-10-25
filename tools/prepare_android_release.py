"""Package a signed APK, optional Play Store AAB, and bounded metadata for the public update channel."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path


def prepare(apk: str | Path, metadata: str | Path, destination: str | Path, aab: str | Path | None = None) -> dict:
    apk, metadata, destination = Path(apk), Path(metadata), Path(destination)
    element = json.loads(metadata.read_text(encoding="utf-8"))["elements"][0]
    code, name = int(element["versionCode"]), str(element["versionName"])
    if code <= 0 or not 0 < apk.stat().st_size <= 100 * 1024 * 1024:
        raise ValueError("Invalid APK version or size")
    destination.mkdir(parents=True, exist_ok=True)
    with apk.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    manifest = {
        "version_code": code,
        "version_name": name,
        "sha256": digest,
        "size": apk.stat().st_size,
    }
    shutil.copyfile(apk, destination / "Zaya-Companion.apk")

    if aab:
        aab_path = Path(aab)
        if aab_path.is_file() and 0 < aab_path.stat().st_size <= 150 * 1024 * 1024:
            shutil.copyfile(aab_path, destination / "Zaya-Companion.aab")
            print(f"Included Google Play bundle: Zaya-Companion.aab ({aab_path.stat().st_size} bytes)")

    (destination / "update.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (destination / "notes.md").write_text(
        f"Zaya Companion {name}\n\n"
        "Install Zaya-Companion.apk to upgrade your existing app. Pairing and settings stay in place.\n\n"
        "The app checks for future releases automatically and offers Update now. "
        "Android asks before installation.\n",
        encoding="utf-8",
    )
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apk", required=True)
    parser.add_argument("--metadata", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--aab", default=None, help="Optional path to app-release.aab")
    arguments = parser.parse_args()
    result = prepare(arguments.apk, arguments.metadata, arguments.output, aab=arguments.aab)
    print(f"Prepared Android {result['version_name']} (code {result['version_code']})")
