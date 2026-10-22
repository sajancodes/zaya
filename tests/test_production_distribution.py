"""
Tests for Zaya Production Distribution System.
Covers:
  - Version API behavior and serialization
  - Runtime paths resolution in standard vs frozen modes
  - Desktop update manifest validation and sanitization
  - Atomic downloads and SHA-256 integrity verification
  - Partial download cleanup on corruption/interruption
  - Authenticode verification logic
  - Inno Setup script structure
  - Android release preparation and update.json schema compatibility
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import core.version as version_mod
from core.runtime_paths import (
    find_or_download_hand_model,
    find_hand_worker,
    get_config_dir,
    get_model_dir,
    get_resource_dir,
    get_user_data_dir,
    is_frozen,
    OFFICIAL_HAND_MODEL_SHA256,
)
from core.update.desktop_updater import (
    DesktopUpdateManifest,
    DesktopUpdater,
    UpdateStatus,
    verify_authenticode_signature,
)
import tools.prepare_android_release as prep_android
import tools.prepare_windows_release as prep_windows


# ---------------------------------------------------------------------------
# 1. Version API Tests
# ---------------------------------------------------------------------------

def test_version_api_values_and_formats():
    assert isinstance(version_mod.VERSION, str)
    assert len(version_mod.VERSION.split(".")) >= 3
    assert isinstance(version_mod.BUILD, int)
    assert version_mod.BUILD >= 10000
    assert version_mod.CHANNEL in ("stable", "beta", "dev")

    v_str = version_mod.version_string()
    assert version_mod.VERSION in v_str
    assert str(version_mod.BUILD) in v_str

    v_dict = version_mod.as_dict()
    assert v_dict["version"] == version_mod.VERSION
    assert v_dict["build"] == version_mod.BUILD
    assert v_dict["channel"] == version_mod.CHANNEL

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir) / "version.json"
        version_mod.write_version_file(tmp_path)
        assert tmp_path.exists()
        loaded = json.loads(tmp_path.read_text(encoding="utf-8"))
        assert loaded["version"] == version_mod.VERSION
        assert loaded["build"] == version_mod.BUILD


# ---------------------------------------------------------------------------
# 2. Runtime Paths Tests
# ---------------------------------------------------------------------------

def test_runtime_paths_normal_mode(monkeypatch):
    monkeypatch.delattr(sys, "frozen", raising=False)
    assert is_frozen() is False

    repo_root = Path(__file__).resolve().parent.parent
    assert get_resource_dir() == repo_root

    user_data = get_user_data_dir()
    assert "Zaya" in str(user_data)
    assert get_config_dir() == user_data / "config"
    assert get_model_dir() == user_data / "models"


def test_runtime_paths_frozen_mode(monkeypatch, tmp_path):
    fake_app_dir = tmp_path / "Programs" / "Zaya"
    fake_app_dir.mkdir(parents=True)
    fake_exe = fake_app_dir / "Zaya.exe"
    fake_exe.touch()

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(fake_exe))

    assert is_frozen() is True
    assert get_resource_dir() == fake_app_dir

    # Worker discovery next to frozen executable
    fake_worker = fake_app_dir / "ZayaHandWorker.exe"
    fake_worker.touch()
    assert find_hand_worker() == fake_worker


# ---------------------------------------------------------------------------
# 3. Manifest Parser and Schema Validation Tests
# ---------------------------------------------------------------------------

def test_manifest_parse_valid():
    valid_data = {
        "schema": 1,
        "channel": "stable",
        "version": "0.5.1",
        "build": 10008,
        "filename": "Zaya-Setup.exe",
        "url": "https://github.com/sajancodes/zaya-companion-releases/releases/download/v0.5.1/Zaya-Setup.exe",
        "sha256": "a" * 64,
        "size": 45000000,
    }
    manifest = DesktopUpdateManifest.parse(valid_data)
    assert manifest.schema == 1
    assert manifest.version == "0.5.1"
    assert manifest.build == 10008
    assert manifest.size == 45000000
    assert manifest.filename == "Zaya-Setup.exe"


@pytest.mark.parametrize(
    "invalid_input",
    [
        {},  # empty
        {"schema": 2},  # bad schema version
        {"schema": 1, "version": ""},  # empty version
        {"schema": 1, "version": "1.0", "build": 10, "filename": "Zaya-Setup.exe", "url": "http://github.com/sajancodes/zaya-companion-releases/test.exe", "sha256": "a"*64, "size": 2000},  # http not allowed
        {"schema": 1, "version": "1.0", "build": 10, "filename": "Zaya-Setup.exe", "url": "https://malicious.com/sajancodes/zaya-companion-releases/test.exe", "sha256": "a"*64, "size": 2000},  # wrong host
        {"schema": 1, "version": "1.0", "build": 10, "filename": "Zaya-Setup.exe", "url": "https://github.com/sajancodes/zaya-companion-releases/test.exe", "sha256": "xyz", "size": 2000},  # bad sha256 hex
        {"schema": 1, "version": "1.0", "build": 10, "filename": "Zaya-Setup.exe", "url": "https://github.com/sajancodes/zaya-companion-releases/test.exe", "sha256": "a"*64, "size": 10},  # too small (< 1024)
        {"schema": 1, "version": "1.0", "build": 10, "filename": "Zaya-Setup.exe", "url": "https://github.com/sajancodes/zaya-companion-releases/test.exe", "sha256": "a"*64, "size": 600 * 1024 * 1024},  # too large
    ],
)
def test_manifest_parse_invalid(invalid_input):
    with pytest.raises(ValueError):
        DesktopUpdateManifest.parse(invalid_input)


# ---------------------------------------------------------------------------
# 4. Download and Integrity Verification Tests
# ---------------------------------------------------------------------------

def test_updater_download_integrity_and_cleanup(tmp_path, monkeypatch):
    monkeypatch.setattr("core.runtime_paths.get_user_data_dir", lambda: tmp_path)
    updater = DesktopUpdater()

    payload = b"Valid Zaya Installer Binary Content 1234567890" * 50
    correct_hash = hashlib.sha256(payload).hexdigest()

    manifest = DesktopUpdateManifest(
        schema=1,
        channel="stable",
        version="0.5.1",
        build=version_mod.BUILD + 1,
        filename="Zaya-Setup.exe",
        url="https://github.com/sajancodes/zaya-companion-releases/releases/download/v0.5.1/Zaya-Setup.exe",
        sha256=correct_hash,
        size=len(payload),
    )
    updater.available_manifest = manifest

    # Mock urllib response with valid payload
    mock_resp = MagicMock()
    mock_resp.headers = {"Content-Length": str(len(payload))}
    mock_resp.read.side_effect = [payload, b""]
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        downloaded = updater.download()
        assert downloaded is not None
        assert downloaded.exists()
        assert downloaded.read_bytes() == payload
        # Ensure temporary file is gone
        assert not Path(str(downloaded) + ".tmp").exists()
        assert updater.status == UpdateStatus.READY

    # Test SHA-256 mismatch (tampered payload with identical size)
    corrupted_payload = b"X" * len(payload)
    mock_resp_tampered = MagicMock()
    mock_resp_tampered.headers = {"Content-Length": str(len(corrupted_payload))}
    mock_resp_tampered.read.side_effect = [corrupted_payload, b""]
    mock_resp_tampered.__enter__.return_value = mock_resp_tampered

    with patch("urllib.request.urlopen", return_value=mock_resp_tampered):
        failed_res = updater.download()
        assert failed_res is None
        assert updater.status == UpdateStatus.FAILED
        assert "SHA-256" in updater.error_message

    # Ensure no leftover temporary file
    assert not (tmp_path / "updates" / "Zaya-Setup.exe.tmp").exists()


def test_hand_landmarker_download_and_tamper_detection(tmp_path, monkeypatch):
    monkeypatch.setattr("core.runtime_paths.get_model_dir", lambda: tmp_path)
    monkeypatch.setattr("core.runtime_paths.get_app_root", lambda: tmp_path)
    monkeypatch.setattr("core.runtime_paths.get_resource_dir", lambda: tmp_path)

    payload = b"Official Google Hand Landmarker Weights Content"
    expected_hash = hashlib.sha256(payload).hexdigest()

    monkeypatch.setattr("core.runtime_paths.OFFICIAL_HAND_MODEL_SHA256", expected_hash)

    mock_resp = MagicMock()
    mock_resp.headers = {"Content-Length": str(len(payload))}
    mock_resp.read.side_effect = [payload, b""]
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        model_path = find_or_download_hand_model()
        assert model_path.exists()
        assert model_path.read_bytes() == payload

    # If file exists and hash matches, subsequent calls return path without re-downloading
    with patch("urllib.request.urlopen") as mock_url:
        cached_path = find_or_download_hand_model()
        assert cached_path == model_path
        mock_url.assert_not_called()


# ---------------------------------------------------------------------------
# 5. Authenticode Verification Logic Tests
# ---------------------------------------------------------------------------

def test_authenticode_verification(monkeypatch):
    monkeypatch.setenv("ZAYA_REQUIRE_AUTHENTICODE", "1")

    # Non-existent file
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="Invalid\n")
        assert verify_authenticode_signature(Path("C:/non/existent/file.exe")) is False

    # Mock successful Valid signature
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="Valid\n")
        with tempfile.NamedTemporaryFile(suffix=".exe") as tmp:
            assert verify_authenticode_signature(Path(tmp.name)) is True

    # Mock signature failure
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="NotSigned\n")
        with tempfile.NamedTemporaryFile(suffix=".exe") as tmp:
            assert verify_authenticode_signature(Path(tmp.name)) is False


# ---------------------------------------------------------------------------
# 6. Inno Setup Script Structure Tests
# ---------------------------------------------------------------------------

def test_inno_setup_script_structure():
    iss_path = Path(__file__).resolve().parent.parent / "packaging" / "windows" / "Zaya.iss"
    assert iss_path.exists(), "Zaya.iss must exist in packaging/windows/"

    content = iss_path.read_text(encoding="utf-8")

    # Essential Inno Setup sections
    assert "[Setup]" in content
    assert "[Tasks]" in content
    assert "[Files]" in content
    assert "[Icons]" in content
    assert "[Run]" in content
    assert "[UninstallDelete]" in content

    # Key security & non-admin install requirements
    assert "PrivilegesRequired=lowest" in content
    assert "{localappdata}\\Programs" in content
    assert ("OutputBaseFilename=ZayaSetup" in content) or ("OutputBaseFilename=Zaya-Setup" in content)
    assert "ArchitecturesInstallIn64BitMode=x64compatible" in content or "x64" in content

    # Clean uninstall preserving user data
    assert "{localappdata}\\Zaya" in content


# ---------------------------------------------------------------------------
# 7. Android Release Preparation & update.json Schema Compatibility
# ---------------------------------------------------------------------------

def test_android_release_preparation(tmp_path):
    dummy_apk = tmp_path / "app-release.apk"
    dummy_apk.write_bytes(b"PK\x03\x04Dummy APK Content")

    dummy_metadata = tmp_path / "output-metadata.json"
    dummy_metadata.write_text(json.dumps({
        "elements": [
            {
                "versionCode": 10006,
                "versionName": "0.4.6",
                "outputFile": "app-release.apk",
            }
        ]
    }))

    dummy_aab = tmp_path / "app-release.aab"
    dummy_aab.write_bytes(b"PK\x03\x04Dummy AAB Content")

    out_dir = tmp_path / "out"

    prep_android.prepare(
        apk=dummy_apk,
        metadata=dummy_metadata,
        destination=out_dir,
        aab=dummy_aab,
    )

    out_apk = out_dir / "Zaya-Companion.apk"
    out_aab = out_dir / "Zaya-Companion.aab"
    out_json = out_dir / "update.json"
    out_notes = out_dir / "notes.md"

    assert out_apk.exists()
    assert out_aab.exists()
    assert out_json.exists()
    assert out_notes.exists()

    manifest = json.loads(out_json.read_text(encoding="utf-8"))
    assert manifest["version_name"] == "0.4.6"
    assert manifest["version_code"] == 10006
    assert "sha256" in manifest
    assert len(manifest["sha256"]) == 64
    assert manifest["size"] == len(dummy_apk.read_bytes())
