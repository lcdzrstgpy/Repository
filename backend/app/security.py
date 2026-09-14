import base64
import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt


_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1


def hash_password(password: str) -> str:
    if len(password) < 8:
        raise ValueError("密码至少 8 位")
    salt = os.urandom(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P
    )
    return "scrypt${}${}${}${}${}".format(
        _SCRYPT_N,
        _SCRYPT_R,
        _SCRYPT_P,
        base64.urlsafe_b64encode(salt).decode("ascii"),
        base64.urlsafe_b64encode(digest).decode("ascii"),
    )


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, n, r, p, salt_b64, digest_b64 = encoded.split("$", 5)
        if algorithm != "scrypt":
            return False
        salt = base64.urlsafe_b64decode(salt_b64)
        expected = base64.urlsafe_b64decode(digest_b64)
        actual = hashlib.scrypt(
            password.encode("utf-8"), salt=salt, n=int(n), r=int(r), p=int(p)
        )
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def create_access_token(
    *, subject: str, role: str, secret: str, algorithm: str, minutes: int
) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=minutes),
    }
    return jwt.encode(payload, secret, algorithm=algorithm)


def decode_access_token(token: str, *, secret: str, algorithm: str) -> dict[str, Any]:
    return jwt.decode(token, secret, algorithms=[algorithm])
