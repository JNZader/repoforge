"""AES-256-GCM encryption for provider API keys.

Uses HKDF to derive per-user keys from a master key, then encrypts/decrypts
with AESGCM. Storage format: nonce(12B) || ciphertext || tag(16B).
"""

import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

_NONCE_SIZE = 12  # bytes
_KEY_INFO = b"repoforge-key-encryption"


def derive_user_key(master_key: bytes, user_id: str) -> bytes:
    """Derive a per-user 256-bit encryption key via HKDF.

    Args:
        master_key: 32-byte master key.
        user_id: User identifier used as HKDF salt.

    Returns:
        32-byte derived key.
    """
    hkdf = HKDF(
        algorithm=SHA256(),
        length=32,
        salt=user_id.encode(),
        info=_KEY_INFO,
    )
    return hkdf.derive(master_key)


def encrypt_key(plaintext: str, encryption_key: bytes) -> bytes:
    """Encrypt an API key with AES-256-GCM.

    Args:
        plaintext: The API key in cleartext.
        encryption_key: 32-byte derived key.

    Returns:
        Bytes in format ``nonce(12) || ciphertext || tag(16)``.
    """
    nonce = os.urandom(_NONCE_SIZE)
    aesgcm = AESGCM(encryption_key)
    ct = aesgcm.encrypt(nonce, plaintext.encode(), None)
    return nonce + ct  # nonce(12) || ciphertext || tag(16)


def decrypt_key(ciphertext: bytes, encryption_key: bytes) -> str:
    """Decrypt an API key from AES-256-GCM blob.

    Args:
        ciphertext: Bytes in format ``nonce(12) || ciphertext || tag(16)``.
        encryption_key: 32-byte derived key.

    Returns:
        Decrypted API key string.

    Raises:
        cryptography.exceptions.InvalidTag: If decryption fails.
    """
    nonce = ciphertext[:_NONCE_SIZE]
    ct = ciphertext[_NONCE_SIZE:]
    aesgcm = AESGCM(encryption_key)
    return aesgcm.decrypt(nonce, ct, None).decode()


def mask_key(key: str) -> str:
    """Mask an API key for safe display.

    Shows the first 3 characters and last 4 characters, separated by ``...``.
    Returns ``"****"`` for very short keys.

    Args:
        key: Full API key.

    Returns:
        Masked key string, e.g. ``"sk-...a3Fx"``.
    """
    if len(key) <= 8:
        return "****"
    prefix = key[:3]
    suffix = key[-4:]
    return f"{prefix}...{suffix}"
