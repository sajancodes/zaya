"""Tests for Zaya public distribution website, telemetry, onboarding, and key vault.
Created and developed by Sajan Rai.
"""
from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from core.onboarding.wizard import probe_provider_connection
from core.security.key_vault import (
    decrypt_secret,
    delete_provider_key,
    encrypt_secret,
    list_configured_providers,
    load_provider_key,
    mask_secret,
    store_provider_key,
)
from core.startup import get_target_executable_path, is_startup_enabled, set_startup_enabled
from core.telemetry import (
    get_or_create_installation_info,
    is_telemetry_enabled,
    report_heartbeat_event,
    report_install_event,
    set_telemetry_enabled,
)
from web.auth import (
    create_session,
    hash_password,
    revoke_session,
    validate_session,
    verify_admin_credentials,
    verify_password,
)
import web.database as db
from web.server import app
from web.telemetry_service import is_rate_limited, validate_telemetry_payload


# ---------------------------------------------------------------------------
# 1. Key Vault Tests
# ---------------------------------------------------------------------------
def test_key_vault_encryption_roundtrip():
    secret = "AIzaSyTestApiKey9876543210"
    encrypted = encrypt_secret(secret)
    assert encrypted != secret
    assert encrypted.startswith("dpapi:") or encrypted.startswith("b64:")

    decrypted = decrypt_secret(encrypted)
    assert decrypted == secret

    # Empty string handling
    assert encrypt_secret("") == ""
    assert decrypt_secret("") == ""

    # Legacy plain key fallback
    legacy_plain = "AIzaSyLegacyKeyWithoutPrefix"
    assert decrypt_secret(legacy_plain) == legacy_plain


def test_key_masking():
    assert mask_secret("") == "Not configured"
    assert mask_secret("1234") == "••••"
    masked = mask_secret("AIzaSyVeryLongSecretKey1234", visible_suffix_len=4)
    assert masked.endswith("1234")
    assert "AIzaSy" not in masked
    assert "•" in masked


def test_provider_key_store_load_delete(tmp_path, monkeypatch):
    monkeypatch.setattr("core.security.key_vault.get_config_dir", lambda: tmp_path)

    store_provider_key("gemini", "AIzaSyGeminiTestKey")
    assert load_provider_key("gemini") == "AIzaSyGeminiTestKey"
    assert "gemini" in list_configured_providers()

    store_provider_key("openai", "sk-proj-OpenAITestKey")
    assert load_provider_key("openai") == "sk-proj-OpenAITestKey"
    assert "openai" in list_configured_providers()

    # Verify keys are encrypted on disk
    config_file = tmp_path / "api_keys.json"
    assert config_file.is_file()
    disk_data = json.loads(config_file.read_text(encoding="utf-8"))
    assert "AIzaSyGeminiTestKey" not in json.dumps(disk_data)

    # Delete key
    assert delete_provider_key("openai") is True
    assert load_provider_key("openai") == ""
    assert "openai" not in list_configured_providers()


# ---------------------------------------------------------------------------
# 2. Telemetry Client Tests
# ---------------------------------------------------------------------------
def test_telemetry_installation_info_creation_and_preservation(tmp_path, monkeypatch):
    monkeypatch.setattr("core.telemetry.get_user_data_dir", lambda: tmp_path)

    info1 = get_or_create_installation_info()
    assert "installation_id" in info1
    assert len(info1["installation_id"]) == 36  # UUIDv4 format
    # By default on fresh install, telemetry is disabled until explicit user consent
    assert info1["telemetry_enabled"] is False

    # Calling again preserves same UUID
    info2 = get_or_create_installation_info()
    assert info2["installation_id"] == info1["installation_id"]

    # Toggle preference
    set_telemetry_enabled(True)
    assert is_telemetry_enabled() is True
    set_telemetry_enabled(False)
    assert is_telemetry_enabled() is False


def test_telemetry_reporting(tmp_path, monkeypatch):
    monkeypatch.setattr("core.telemetry.get_user_data_dir", lambda: tmp_path)
    # Enable telemetry for reporting tests
    set_telemetry_enabled(True)

    with patch("core.telemetry._post_json", return_value=True) as mock_post:
        assert report_install_event("https://test.zaya.codes") is True
        mock_post.assert_called_once()

        # Subsequent call does not duplicate install event
        mock_post.reset_mock()
        assert report_install_event("https://test.zaya.codes") is True
        mock_post.assert_not_called()

    # Heartbeat event
    with patch("core.telemetry._post_json", return_value=True) as mock_post:
        assert report_heartbeat_event("https://test.zaya.codes", force=True) is True
        mock_post.assert_called_once()


# ---------------------------------------------------------------------------
# 3. Windows Startup Helper Tests
# ---------------------------------------------------------------------------
def test_startup_helpers():
    exe_path = get_target_executable_path()
    assert exe_path is not None
    assert isinstance(is_startup_enabled(), bool)


# ---------------------------------------------------------------------------
# 4. Onboarding Connection Probe Tests
# ---------------------------------------------------------------------------
def test_probe_provider_connection_empty_or_short():
    ok, msg = probe_provider_connection("gemini", "short")
    assert ok is False
    assert "valid" in msg.lower()


def test_probe_provider_connection_mock_gemini():
    mock_client = MagicMock()
    mock_client.models.list.return_value = ["gemini-2.5-flash"]

    with patch("google.genai.Client", return_value=mock_client):
        ok, msg = probe_provider_connection("gemini", "AIzaSyValidDummyTestKey1234567")
        assert ok is True
        assert "connected successfully" in msg


# ---------------------------------------------------------------------------
# 5. Database & Admin Auth Tests
# ---------------------------------------------------------------------------
def test_database_and_auth_operations(tmp_path):
    test_db = tmp_path / "test_analytics.db"
    db.init_db(test_db)

    conn = db.get_connection(test_db)
    assert conn is not None
    conn.close()

    # Password hashing
    pwd = "SecretOwnerPassword123!"
    h = hash_password(pwd)
    assert verify_password(pwd, h) is True
    assert verify_password("wrong", h) is False

    # Admin sessions
    with patch("web.auth.get_connection", lambda: db.get_connection(test_db)):
        token = create_session("owner")
        assert len(token) == 64
        assert validate_session(token) is True

        revoke_session(token)
        assert validate_session(token) is False


# ---------------------------------------------------------------------------
# 6. Web API Endpoints Tests
# ---------------------------------------------------------------------------
@pytest.fixture
def client(tmp_path, monkeypatch):
    test_db = tmp_path / "web_test.db"
    monkeypatch.setattr("web.database.get_db_path", lambda: test_db)
    monkeypatch.setattr("web.database.DEFAULT_DB_PATH", test_db)
    db.init_db(test_db)

    with TestClient(app) as test_client:
        yield test_client


def test_api_telemetry_install_and_heartbeat(client):
    # Valid install payload
    payload = {
        "installation_id": "c1f7b8a2-3d4e-4f5a-8b9c-0d1e2f3a4b5c",
        "platform": "windows",
        "version": "0.5.0",
    }
    resp = client.post("/api/telemetry/install", json=payload)
    assert resp.status_code == 201
    assert resp.json()["status"] == "ok"
    assert resp.json()["unique_install"] is True

    # Same install ID again should report existing (unique_install=False)
    resp2 = client.post("/api/telemetry/install", json=payload)
    assert resp2.status_code == 201
    assert resp2.json()["unique_install"] is False

    # Heartbeat
    resp3 = client.post("/api/telemetry/heartbeat", json=payload)
    assert resp3.status_code == 200
    assert resp3.json()["status"] == "ok"

    # Invalid payload (not UUID)
    bad_payload = {"installation_id": "invalid-id", "platform": "windows", "version": "1.0"}
    resp4 = client.post("/api/telemetry/install", json=bad_payload)
    assert resp4.status_code == 400


def test_api_download_event(client):
    resp = client.post("/api/downloads/event", json={"platform": "windows", "version": "0.5.0"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_api_releases_endpoints(client):
    # Upsert releases for both Windows and Android at same version (tests composite key uniqueness)
    db.upsert_release(
        version="0.5.5",
        platform="windows",
        filename="ZayaSetup.exe",
        url="https://github.com/sajancodes/zaya-companion-releases/releases/download/v0.5.5/ZayaSetup.exe",
        sha256="aabbccddeeff00112233445566778899aabbccddeeff00112233445566778899",
        size=45000000,
        release_notes="Windows release notes",
    )
    db.upsert_release(
        version="0.5.5",
        platform="android",
        filename="Zaya-Companion.apk",
        url="https://github.com/sajancodes/zaya-companion-releases/releases/download/v0.5.5/Zaya-Companion.apk",
        sha256="112233445566778899aabbccddeeff00112233445566778899aabbccddeeff00",
        size=23000000,
        release_notes="Android companion notes",
    )

    resp = client.get("/api/releases")
    assert resp.status_code == 200
    releases = resp.json()
    assert isinstance(releases, list)
    assert len(releases) == 2

    latest_win = client.get("/api/releases/latest?platform=windows")
    assert latest_win.status_code == 200
    assert latest_win.json()["platform"] == "windows"
    assert latest_win.json()["version"] == "0.5.5"

    latest_droid = client.get("/api/releases/latest?platform=android")
    assert latest_droid.status_code == 200
    assert latest_droid.json()["platform"] == "android"
    assert latest_droid.json()["version"] == "0.5.5"


def test_admin_metrics_authentication(client, monkeypatch):
    # 1. Without strong ADMIN_PASSWORD configured, /admin is disabled (503 Service Unavailable)
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    resp_disabled = client.get("/api/admin/metrics")
    assert resp_disabled.status_code == 503

    # Disallowed default password must also fail
    monkeypatch.setenv("ADMIN_PASSWORD", "ZayaOwner2026!")
    resp_disallowed = client.get("/api/admin/metrics")
    assert resp_disallowed.status_code == 503

    # 2. Configure strong secret (minimum 12 chars)
    strong_pw = "SuperSecureOwnerSecret2026!#%"
    monkeypatch.setenv("ADMIN_USER", "owner")
    monkeypatch.setenv("ADMIN_PASSWORD", strong_pw)

    # Unauthenticated access to metrics rejected (401)
    resp_unauth = client.get("/api/admin/metrics")
    assert resp_unauth.status_code == 401

    # Login with invalid password fails (401)
    resp_bad = client.post("/api/admin/login", json={"username": "owner", "password": "wrongpassword"})
    assert resp_bad.status_code == 401

    # Login with valid credentials succeeds (200)
    resp_login = client.post("https://testserver/api/admin/login", json={"username": "owner", "password": strong_pw})
    assert resp_login.status_code == 200
    # Cookie must be marked secure
    set_cookie = resp_login.headers.get("set-cookie", "")
    assert "HttpOnly" in set_cookie
    assert "Secure" in set_cookie

    # Authenticated metrics access over HTTPS client preserves Secure cookie
    resp_metrics = client.get("https://testserver/api/admin/metrics")
    assert resp_metrics.status_code == 200
    data = resp_metrics.json()
    assert "downloads" in data
    assert "installations" in data
    assert "active" in data
    assert "version_distribution" in data


def test_seo_endpoints(client):
    robots = client.get("/robots.txt")
    assert robots.status_code == 200
    assert "Disallow: /admin" in robots.text

    sitemap = client.get("/sitemap.xml")
    assert sitemap.status_code == 200
    assert "<loc>https://zaya.sajan.codes/download</loc>" in sitemap.text
