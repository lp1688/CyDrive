import os
from typing import Optional

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False

class CyCrypto:
    """Zero-Knowledge AES-256-GCM File & Metadata Encryption Engine."""

    SALT_SIZE = 16
    NONCE_SIZE = 12
    KEY_SIZE = 32

    def __init__(self, password: Optional[str] = None):
        self.password = password

    def _derive_key(self, password: str, salt: bytes) -> bytes:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=self.KEY_SIZE,
            salt=salt,
            iterations=100_000
        )
        return kdf.derive(password.encode("utf-8"))

    def encrypt_file(self, input_path: str, output_path: str) -> bool:
        """Encrypts a file with AES-256-GCM."""
        if not self.password:
            raise ValueError("Encryption password is not configured.")

        salt = os.urandom(self.SALT_SIZE)
        nonce = os.urandom(self.NONCE_SIZE)
        key = self._derive_key(self.password, salt)
        aesgcm = AESGCM(key)

        with open(input_path, "rb") as f:
            plaintext = f.read()

        ciphertext = aesgcm.encrypt(nonce, plaintext, None)

        with open(output_path, "wb") as f:
            # Header format: [SALT (16B)] + [NONCE (12B)] + [CIPHERTEXT]
            f.write(salt)
            f.write(nonce)
            f.write(ciphertext)

        return True

    def decrypt_file(self, input_path: str, output_path: str) -> bool:
        """Decrypts an AES-256-GCM encrypted file."""
        if not self.password:
            raise ValueError("Encryption password is not configured.")

        with open(input_path, "rb") as f:
            salt = f.read(self.SALT_SIZE)
            nonce = f.read(self.NONCE_SIZE)
            ciphertext = f.read()

        key = self._derive_key(self.password, salt)
        aesgcm = AESGCM(key)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)

        with open(output_path, "wb") as f:
            f.write(plaintext)

        return True
