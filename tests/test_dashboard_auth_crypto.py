import pytest
import time
import secrets
from starlette.testclient import TestClient

from dashboard.server import DashboardServer, _derive_key, _encrypt_gcm, _decrypt_gcm, _KEY_CHARS


def test_new_pairing_keys_entropy():
    server = DashboardServer()
    pin, qr_secret = server.new_pairing_keys()

    assert len(pin) == 6
    assert all(c in _KEY_CHARS for c in pin)
    # 32 urlsafe bytes provides 256 bits of entropy (well >= 128 bits)
    assert len(qr_secret) >= 32
    assert pin in server._pending_keys
    assert qr_secret in server._pending_keys


def test_one_time_linked_consumption():
    server = DashboardServer()
    pin, qr_secret = server.new_pairing_keys()

    # Consuming the PIN should invalidate both the PIN and the QR secret
    assert server._consume_key(pin) is True
    assert server._consume_key(pin) is False
    assert server._consume_key(qr_secret) is False

    # Similarly, consuming QR secret invalidates the PIN
    pin2, qr_secret2 = server.new_pairing_keys()
    assert server._consume_key(qr_secret2) is True
    assert server._consume_key(pin2) is False


def test_pbkdf2_key_derivation():
    salt1 = secrets.token_bytes(16)
    salt2 = secrets.token_bytes(16)
    k1 = _derive_key("TESTKEY", salt1, iterations=1000)
    k2 = _derive_key("TESTKEY", salt2, iterations=1000)

    assert len(k1) == 32
    assert len(k2) == 32
    assert k1 != k2


def test_aes_gcm_roundtrip_and_no_cbc_fallback():
    key = secrets.token_bytes(32)
    plaintext = "Hello Zaya Voice & Live Stream"

    enc = _encrypt_gcm(key, plaintext)
    dec = _decrypt_gcm(key, enc)
    assert dec == plaintext

    # Tampered ciphertext fails
    tampered = enc[:-4] + "AAAA"
    with pytest.raises(Exception):
        _decrypt_gcm(key, tampered)

    # CBC-style payload without GCM tag should fail length check or decryption
    import base64
    fake_cbc = base64.b64encode(b"0" * 32).decode("ascii")
    with pytest.raises(Exception):
        _decrypt_gcm(key, fake_cbc)


def test_login_and_decrypt_flow():
    server = DashboardServer()
    client = TestClient(server.app)

    pin, _ = server.new_pairing_keys()

    # Successful login with PIN
    res = client.post("/login", json={"pin": pin})
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    token = data["token"]
    assert "salt" in data

    # Authenticated command with AES-GCM
    msg = "echo test command"
    salt_bytes = bytes.fromhex(data["salt"])
    aes_k = _derive_key(pin, salt_bytes)
    enc_cmd = _encrypt_gcm(aes_k, msg)

    res_cmd = client.post("/api/command", json={"enc": enc_cmd}, headers={"Authorization": f"Bearer {token}"})
    assert res_cmd.status_code == 200
    assert res_cmd.json()["ok"] is True


def test_auto_login_rate_limit():
    server = DashboardServer()
    client = TestClient(server.app)

    # Exceed rate limit (limit is 5 attempts per window)
    for _ in range(5):
        res = client.get("/auto-login?key=INVALIDKEY")
        assert res.status_code in (200, 401)  # Invalid key returns "Link Expired" HTML

    # 6th attempt must be 429
    res6 = client.get("/auto-login?key=INVALIDKEY")
    assert res6.status_code == 429
