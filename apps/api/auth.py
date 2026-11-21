"""Authentication and API Key management."""
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from jose import jwt, JWTError
from datetime import datetime, timedelta, timezone
from customer_keys import KEY_MANAGER
import os
from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv(usecwd=True))

ph = PasswordHasher()
JWT_SECRET = os.environ.get("JWT_SECRET")
if JWT_SECRET in (None, "", "dev-secret-change-me", "change-me-in-production", "replace-with-64-character-random-secret-before-deploying"):
    raise RuntimeError("JWT_SECRET must be configured before starting the API")
JWT_ALGORITHM = "HS256"
JWT_EXPIRES_HOURS = 24

def hash_password(password: str) -> str:
    return ph.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    try:
        ph.verify(hashed, plain)
        return True
    except VerifyMismatchError:
        return False

def create_jwt(user_id: int, email: str) -> str:
    payload = {
        "sub": str(user_id),
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRES_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def decode_jwt(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except JWTError:
        return None
