from app.core.time import utcnow
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta

import jwt

from app.core.config import JWT_SECRET, JWT_ALGORITHM, JWT_EXPIRE_MINUTES


def generate_otp() -> str:
    """Returns a random 6-digit code, e.g. '048213'."""
    return f"{secrets.randbelow(10**6):06d}"


def hash_otp(phone: str, code: str) -> str:
    """Keyed hash so a leaked database does not reveal usable codes."""
    message = f"{phone}:{code}".encode()
    return hmac.new(JWT_SECRET.encode(), message, hashlib.sha256).hexdigest()


def verify_otp_hash(phone: str, code: str, code_hash: str) -> bool:
    return hmac.compare_digest(hash_otp(phone, code), code_hash)


def create_access_token(user_id: int, role: str) -> str:
    payload = {
        "sub": str(user_id),
        "role": role,
        "exp": utcnow() + timedelta(minutes=JWT_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Raises jwt.PyJWTError if the token is invalid or expired."""
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM], options={"require": ["sub", "exp"]})
