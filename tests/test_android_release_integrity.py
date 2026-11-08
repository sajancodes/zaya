import json
import tempfile
from pathlib import Path
import pytest

from tools.prepare_android_release import (
    EXPECTED_SIGNER_SHA256,
    extract_apk_v2_signing_cert_sha256,
    prepare,
)


def test_android_release_apk_signer_matches_production():
    apk_path = Path("dist/android-release/Zaya-Companion.apk")
    if not apk_path.exists():
        pytest.skip("dist/android-release/Zaya-Companion.apk not found")

    fingerprint = extract_apk_v2_signing_cert_sha256(apk_path)
    assert fingerprint is not None
    assert fingerprint == EXPECTED_SIGNER_SHA256


def test_prepare_android_release_rejects_mismatched_signer(tmp_path: Path):
    apk_path = Path("dist/android-release/Zaya-Companion.apk")
    if not apk_path.exists():
        pytest.skip("dist/android-release/Zaya-Companion.apk not found")

    metadata = tmp_path / "metadata.json"
    metadata.write_text(json.dumps({
        "elements": [{"versionCode": 10008, "versionName": "0.4.8"}]
    }), encoding="utf-8")

    out_dir = tmp_path / "out"

    # Expecting a different signer must raise ValueError
    with pytest.raises(ValueError, match="signing certificate mismatch"):
        prepare(
            apk=apk_path,
            metadata=metadata,
            destination=out_dir,
            expected_signer="0000000000000000000000000000000000000000000000000000000000000000",
        )


def test_prepare_android_release_success(tmp_path: Path):
    apk_path = Path("dist/android-release/Zaya-Companion.apk")
    if not apk_path.exists():
        pytest.skip("dist/android-release/Zaya-Companion.apk not found")

    metadata = tmp_path / "metadata.json"
    metadata.write_text(json.dumps({
        "elements": [{"versionCode": 10008, "versionName": "0.4.8"}]
    }), encoding="utf-8")

    out_dir = tmp_path / "out"
    manifest = prepare(
        apk=apk_path,
        metadata=metadata,
        destination=out_dir,
        expected_signer=EXPECTED_SIGNER_SHA256,
    )

    assert manifest["version_code"] == 10008
    assert manifest["version_name"] == "0.4.8"
    assert (out_dir / "update.json").exists()
    assert (out_dir / "Zaya-Companion.apk").exists()
    assert (out_dir / "notes.md").exists()
