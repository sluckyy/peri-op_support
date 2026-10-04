"""Real username/password authentication for staff/clinician access to
session data -- see periop_api.app for exactly which endpoints this
gates and why (patients submit their own data without an account;
anyone viewing session data or taking a clinical/Model-Layer action
needs a verified identity instead of a free-text name).

Scope honestly stated: single-factor username/password only. No email
verification, no password-reset flow, no MFA, and no account-lockout/
rate-limiting on repeated login attempts -- a real deployment needs all
of these. What's here is the actual cryptographic mechanism (a real,
salted, memory-hard password hash and unguessable session tokens), not
a demo stand-in for it -- this is not a shortcut to be replaced later,
unlike the rest of this repo's documented demo shortcuts.

Password hashing uses hashlib.scrypt (stdlib, no extra dependency): a
memory-hard KDF, deliberately not a fast general-purpose hash like
SHA-256, which would make brute-forcing a leaked hash cheap.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from pydantic import BaseModel, Field

_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1
_SCRYPT_DKLEN = 32

SESSION_TOKEN_BYTES = 32
SESSION_LIFETIME = timedelta(hours=12)

MIN_PASSWORD_LENGTH = 8


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def hash_password(password: str) -> str:
    """Returns 'salt_hex$hash_hex'. A fresh random salt every call --
    never reuse a salt across users or across re-hashes of the same
    password, or identical passwords would produce identical hashes."""
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"password must be at least {MIN_PASSWORD_LENGTH} characters")
    salt = os.urandom(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=_SCRYPT_DKLEN
    )
    return f"{salt.hex()}${digest.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Constant-time comparison (hmac.compare_digest): a naive `==` on
    the recomputed digest would leak timing information about how many
    leading bytes matched."""
    try:
        salt_hex, digest_hex = stored_hash.split("$", 1)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
    except (ValueError, AttributeError):
        return False
    actual = hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=len(expected)
    )
    return hmac.compare_digest(actual, expected)


def generate_session_token() -> str:
    """High-entropy opaque token (256 bits) -- not a JWT, so logout can
    actually revoke it server-side rather than just expiring."""
    return secrets.token_urlsafe(SESSION_TOKEN_BYTES)


class User(BaseModel):
    user_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    username: str
    password_hash: str
    created_at: datetime = Field(default_factory=_utcnow)


class AuthSession(BaseModel):
    token: str
    user_id: uuid.UUID
    created_at: datetime = Field(default_factory=_utcnow)
    expires_at: datetime

    def is_expired(self, now: datetime | None = None) -> bool:
        current = now or _utcnow()
        expires = self.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        return current >= expires


def new_session(user_id: uuid.UUID) -> AuthSession:
    now = _utcnow()
    return AuthSession(
        token=generate_session_token(),
        user_id=user_id,
        created_at=now,
        expires_at=now + SESSION_LIFETIME,
    )
