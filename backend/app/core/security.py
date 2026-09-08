"""Mots de passe, jetons JWT, codes d'appairage et NIP enfant."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import jwt

from app.core.config import settings

TokenType = Literal["access", "refresh", "device", "pairing"]

_PBKDF2_PREFIX = "pbkdf2_sha256"


# ---------------------------------------------------------------------------
# Mots de passe (PBKDF2-HMAC-SHA256 : uniquement la bibliotheque standard,
# donc aucun risque de rupture de build sur ARM ou Alpine)
# ---------------------------------------------------------------------------


def hash_password(password: str, *, iterations: int | None = None) -> str:
    if not password or len(password) < 8:
        raise ValueError("Le mot de passe doit contenir au moins 8 caracteres.")
    iterations = iterations or settings.pbkdf2_iterations
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return f"{_PBKDF2_PREFIX}${iterations}${base64.b64encode(salt).decode()}${base64.b64encode(dk).decode()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iterations, salt_b64, hash_b64 = stored.split("$")
        if algo != _PBKDF2_PREFIX:
            return False
        dk = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), base64.b64decode(salt_b64), int(iterations)
        )
        return hmac.compare_digest(dk, base64.b64decode(hash_b64))
    except (ValueError, TypeError):
        return False


def hash_pin(pin: str) -> str:
    """NIP enfant a 4-6 chiffres : meme primitive, moins d'iterations (UX)."""
    if not (pin.isdigit() and 4 <= len(pin) <= 6):
        raise ValueError("Le NIP doit comporter 4 a 6 chiffres.")
    return hash_password(pin.ljust(8, "0"), iterations=60_000)


def verify_pin(pin: str, stored: str) -> bool:
    if not pin.isdigit():
        return False
    return verify_password(pin.ljust(8, "0"), stored)


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------


def create_token(
    subject: str,
    token_type: TokenType,
    *,
    expires_delta: timedelta | None = None,
    claims: dict[str, Any] | None = None,
) -> str:
    now = datetime.now(UTC)
    if expires_delta is None:
        expires_delta = {
            "access": timedelta(minutes=settings.access_token_ttl_minutes),
            "refresh": timedelta(days=settings.refresh_token_ttl_days),
            "device": timedelta(days=settings.device_token_ttl_days),
            "pairing": timedelta(minutes=15),
        }[token_type]
    payload: dict[str, Any] = {
        "sub": str(subject),
        "typ": token_type,
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
        "jti": uuid.uuid4().hex,
        "iss": settings.app_name,
        **(claims or {}),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str, *, expected_type: TokenType | None = None) -> dict[str, Any]:
    payload = jwt.decode(
        token,
        settings.secret_key,
        algorithms=[settings.jwt_algorithm],
        issuer=settings.app_name,
        options={"require": ["exp", "sub", "typ"]},
    )
    if expected_type and payload.get("typ") != expected_type:
        raise jwt.InvalidTokenError(
            f"Type de jeton inattendu : {payload.get('typ')!r} au lieu de {expected_type!r}"
        )
    return payload


# ---------------------------------------------------------------------------
# Codes d'appairage d'appareil (lisibles a voix haute, sans caracteres ambigus)
# ---------------------------------------------------------------------------

_PAIRING_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # ni I, ni O, ni 0, ni 1


def generate_pairing_code(length: int = 8) -> str:
    raw = "".join(secrets.choice(_PAIRING_ALPHABET) for _ in range(length))
    return f"{raw[: length // 2]}-{raw[length // 2 :]}"


def hash_opaque(value: str) -> str:
    """Empreinte des secrets opaques (codes d'appairage, jetons de rafraichissement)."""
    return hashlib.sha256(f"{settings.secret_key}|{value}".encode()).hexdigest()


def constant_time_equals(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())
