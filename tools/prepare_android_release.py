"""Package a signed APK, optional Play Store AAB, and bounded metadata for the public update channel."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import struct
from pathlib import Path

# Production Companion signing certificate fingerprint (matches existing public releases)
EXPECTED_SIGNER_SHA256 = "b54d592e8e1e7da30cc07a6937cb9a399e012dbfc0aa7634d2fd19248c86a8e2"


def extract_apk_v2_signing_cert_sha256(apk_path: str | Path) -> str | None:
    """Extract the SHA-256 fingerprint of the primary signing certificate from the APK v2 signature block."""
    with open(apk_path, "rb") as f:
        data = f.read()
    eocd_pos = data.rfind(b"PK\x05\x06")
    if eocd_pos == -1:
        return None
    cd_offset = struct.unpack("<I", data[eocd_pos + 16:eocd_pos + 20])[0]
    magic = data[cd_offset - 16:cd_offset]
    if magic != b"APK Sig Block 42":
        return None
    block_size = struct.unpack("<Q", data[cd_offset - 24:cd_offset - 16])[0]
    block_start = cd_offset - 8 - block_size
    pos = block_start + 8
    while pos < cd_offset - 24:
        length, id_ = struct.unpack("<QI", data[pos:pos + 12])
        if id_ == 0x7109871a:  # APK Signature Scheme v2
            v2 = data[pos + 12:pos + 8 + length]
            signers_len = struct.unpack("<I", v2[:4])[0]
            v2_signers = v2[4:4 + signers_len]
            s_len = struct.unpack("<I", v2_signers[:4])[0]
            s = v2_signers[4:4 + s_len]
            sd_len = struct.unpack("<I", s[:4])[0]
            sig_data = s[4:4 + sd_len]
            digests_len = struct.unpack("<I", sig_data[:4])[0]
            certs_in_sd = sig_data[4 + digests_len:]
            certs_len = struct.unpack("<I", certs_in_sd[:4])[0]
            cert_1_len = struct.unpack("<I", certs_in_sd[4:8])[0]
            cert_1 = certs_in_sd[8:8 + cert_1_len]
            return hashlib.sha256(cert_1).hexdigest()
        pos += 8 + length
    return None


def prepare(
    apk: str | Path,
    metadata: str | Path,
    destination: str | Path,
    aab: str | Path | None = None,
    expected_signer: str | None = None,
) -> dict:
    apk, metadata, destination = Path(apk), Path(metadata), Path(destination)
    element = json.loads(metadata.read_text(encoding="utf-8"))["elements"][0]
    code, name = int(element["versionCode"]), str(element["versionName"])
    if code <= 0 or not 0 < apk.stat().st_size <= 100 * 1024 * 1024:
        raise ValueError("Invalid APK version or size")

    # Enforce signing certificate continuity
    if expected_signer:
        actual_signer = extract_apk_v2_signing_cert_sha256(apk)
        if actual_signer != expected_signer:
            raise ValueError(
                f"APK signing certificate mismatch! Expected {expected_signer}, but APK is signed with {actual_signer}. "
                "Publishing this APK would break in-app updates for all existing installations."
            )

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
    parser.add_argument("--expected-signer", default=EXPECTED_SIGNER_SHA256, help="Expected signing certificate SHA-256")
    arguments = parser.parse_args()
    result = prepare(
        arguments.apk,
        arguments.metadata,
        arguments.output,
        aab=arguments.aab,
        expected_signer=arguments.expected_signer,
    )
    print(f"Prepared Android {result['version_name']} (code {result['version_code']})")
