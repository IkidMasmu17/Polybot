"""Security module — Fernet encryption for private keys."""
import os
import base64

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from loguru import logger


class KeyVault:
    """Encrypts/decrypts sensitive values using Fernet symmetric encryption."""

    def __init__(self, fernet_key: str | None = None):
        self._fernet_key = fernet_key or os.getenv("FERNET_KEY")
        if not self._fernet_key:
            logger.warning("FERNET_KEY not set — secrets will be stored in plaintext")
        self._cipher = Fernet(self._fernet_key.encode()) if self._fernet_key else None

    def encrypt(self, plaintext: str) -> str:
        """Encrypt a string. Returns plaintext if no key configured."""
        if not self._cipher:
            return plaintext
        return self._cipher.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        """Decrypt a string. Returns as-is if no key or decryption fails."""
        if not self._cipher:
            return ciphertext
        try:
            return self._cipher.decrypt(ciphertext.encode()).decode()
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            return ciphertext

    @staticmethod
    def generate_key() -> str:
        """Generate a new Fernet key. Run once, save to .env."""
        return Fernet.generate_key().decode()


# Module-level instance
vault = KeyVault()
