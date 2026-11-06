from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Any
from uuid import uuid4

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

password_hasher = PasswordHasher()
JWT_ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return password_hasher.verify(password_hash, password)
    except (InvalidHashError, VerificationError):
        return False


def create_access_token(
    subject: str,
    secret_key: str,
    expires_in_minutes: int = 15,
    token_version: int = 0,
) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": subject,
        "iat": now,
        "exp": now + timedelta(minutes=expires_in_minutes),
        "type": "access",
        "ver": token_version,
        "jti": uuid4().hex,
    }
    return jwt.encode(payload, secret_key, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str, secret_key: str) -> str:
    return decode_access_claims(token, secret_key)["sub"]


def decode_access_claims(token: str, secret_key: str) -> dict[str, Any]:
    payload = jwt.decode(
        token,
        secret_key,
        algorithms=[JWT_ALGORITHM],
        options={"require": ["exp", "iat", "sub", "ver", "jti"]},
    )
    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject or payload.get("type") != "access":
        raise jwt.InvalidTokenError("Invalid access token.")
    if type(payload["ver"]) is not int or payload["ver"] < 0:
        raise jwt.InvalidTokenError("Invalid token version.")
    if not isinstance(payload["jti"], str) or not payload["jti"]:
        raise jwt.InvalidTokenError("Invalid token identifier.")
    return payload


def token_digest(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()
