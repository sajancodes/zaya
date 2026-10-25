"""Linux vault envelopes must fail closed without touching the owner's keyring."""
import pytest
from cryptography.fernet import Fernet
from core.security import key_vault


def test_linux_envelope_roundtrip_and_tampering(monkeypatch):
    key = Fernet.generate_key().decode('ascii')
    monkeypatch.setattr(key_vault, '_IS_WINDOWS', False)
    monkeypatch.setattr(key_vault, '_secret_service_key', lambda create=False: key)
    encrypted = key_vault.encrypt_secret('private-test-value')
    assert encrypted.startswith('secretservice:')
    assert 'private-test-value' not in encrypted
    assert key_vault.decrypt_secret(encrypted) == 'private-test-value'
    assert key_vault.decrypt_secret(encrypted[:-5] + 'wrong') == ''


def test_missing_linux_keyring_never_writes_base64(monkeypatch):
    monkeypatch.setattr(key_vault, '_IS_WINDOWS', False)
    def locked(create=False):
        raise RuntimeError('Keyring locked')
    monkeypatch.setattr(key_vault, '_secret_service_key', locked)
    with pytest.raises(RuntimeError):
        key_vault.encrypt_secret('private-test-value')
    assert key_vault.decrypt_secret('secretservice:invalid') == ''
    # Read compatibility remains for owners migrating existing local data.
    assert key_vault.decrypt_secret('b64:bGVnYWN5') == 'legacy'
