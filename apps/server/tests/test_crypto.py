"""Tests for the crypto service (AES-256-GCM encryption)."""

import pytest
from app.services.crypto import decrypt_key, derive_user_key, encrypt_key, mask_key

# Use a fixed 32-byte test key
_TEST_MASTER_KEY = bytes.fromhex(
    "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
)


def test_encrypt_decrypt_roundtrip():
    """Encrypting then decrypting should return the original plaintext."""
    user_key = derive_user_key(_TEST_MASTER_KEY, "user-123")
    original = "sk-ant-api03-abc123xyz"
    encrypted = encrypt_key(original, user_key)
    decrypted = decrypt_key(encrypted, user_key)
    assert decrypted == original


def test_different_users_get_different_keys():
    """Different user IDs should produce different derived keys."""
    key_a = derive_user_key(_TEST_MASTER_KEY, "user-alice")
    key_b = derive_user_key(_TEST_MASTER_KEY, "user-bob")
    assert key_a != key_b


def test_same_user_gets_same_key():
    """Same user ID should always produce the same derived key."""
    key_1 = derive_user_key(_TEST_MASTER_KEY, "user-123")
    key_2 = derive_user_key(_TEST_MASTER_KEY, "user-123")
    assert key_1 == key_2


def test_wrong_key_fails_decrypt():
    """Decrypting with a wrong key should raise an error."""
    key_a = derive_user_key(_TEST_MASTER_KEY, "user-alice")
    key_b = derive_user_key(_TEST_MASTER_KEY, "user-bob")
    encrypted = encrypt_key("my-secret-key", key_a)
    with pytest.raises(Exception):  # cryptography.exceptions.InvalidTag
        decrypt_key(encrypted, key_b)


def test_mask_key_standard():
    """mask_key should show first 3 and last 4 characters."""
    result = mask_key("sk-ant-api03-abc123xyz789")
    assert result.startswith("sk-")
    assert result.endswith("z789")
    assert "..." in result
    assert "ant-api03" not in result  # middle part is hidden


def test_mask_key_short():
    """Very short keys should be fully masked."""
    result = mask_key("short")
    assert result == "****"


def test_mask_key_exactly_8():
    """Keys of exactly 8 chars should be fully masked."""
    result = mask_key("12345678")
    assert result == "****"


def test_mask_key_9_chars():
    """Keys of 9 chars should show first 3 and last 4."""
    result = mask_key("123456789")
    assert result == "123...6789"


def test_encrypted_output_format():
    """Encrypted output should be at least nonce(12) + tag(16) bytes."""
    user_key = derive_user_key(_TEST_MASTER_KEY, "user-123")
    encrypted = encrypt_key("test", user_key)
    # nonce(12) + ciphertext(>=1) + tag(16)
    assert len(encrypted) >= 12 + 1 + 16
    assert isinstance(encrypted, bytes)
