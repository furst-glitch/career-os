import base64

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.core.config import settings

_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        raw = settings.encryption_key.strip()
        try:
            # Happy path: already a valid Fernet key (44-char URL-safe base64)
            _fernet = Fernet(raw.encode())
        except ValueError:
            # ENCRYPTION_KEY is a passphrase/arbitrary string — derive a proper
            # 256-bit key via HKDF so any non-empty value works on Render.
            derived = base64.urlsafe_b64encode(
                HKDF(
                    algorithm=hashes.SHA256(),
                    length=32,
                    salt=b"careeros-v1",
                    info=b"fernet-byok",
                ).derive(raw.encode())
            )
            _fernet = Fernet(derived)
    return _fernet


def encrypt(plaintext: str) -> str:
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    return _get_fernet().decrypt(ciphertext.encode()).decode()
