import base64
import hashlib
import os
from dotenv import find_dotenv, load_dotenv

from cryptography.fernet import Fernet

load_dotenv(find_dotenv(usecwd=True))

SECRET = os.getenv("JWT_SECRET")
if SECRET in (None, "", "dev-secret-change-me", "change-me-in-production", "replace-with-64-character-random-secret-before-deploying"):
    raise RuntimeError("JWT_SECRET must be configured before loading supplier credentials")
_FERNET = Fernet(base64.urlsafe_b64encode(hashlib.sha256(SECRET.encode()).digest()))


def encrypt_secret(value: str) -> str:
    return _FERNET.encrypt(value.encode()).decode()


def decrypt_secret(value: str) -> str:
    return _FERNET.decrypt(value.encode()).decode()


def secret_suffix(value: str) -> str:
    return value[-4:] if len(value) >= 4 else "****"
