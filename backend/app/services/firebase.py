"""Verification optionnelle des jetons Firebase (authentification par telephone).

Le tableau de bord parent peut s'appuyer sur Firebase Authentication (numero de
telephone, e-mail). L'API accepte alors un jeton Firebase et le convertit en
jeton KODA. Si `KODA_FIREBASE_PROJECT_ID` n'est pas defini, la fonctionnalite
est simplement desactivee : le produit reste utilisable avec l'authentification
locale.
"""

from __future__ import annotations

import time
from typing import Any

import httpx
import jwt
from jwt.algorithms import RSAAlgorithm

from app.core.config import settings
from app.core.errors import AuthenticationError

_certs_cache: dict[str, Any] = {"fetched_at": 0.0, "keys": {}}
CERTS_TTL_SECONDS = 3600


def is_enabled() -> bool:
    return bool(settings.firebase_project_id)


async def _public_keys() -> dict[str, Any]:
    now = time.time()
    if _certs_cache["keys"] and now - _certs_cache["fetched_at"] < CERTS_TTL_SECONDS:
        return _certs_cache["keys"]
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(settings.firebase_certs_url)
        response.raise_for_status()
        certificates = response.json()
    keys = {kid: RSAAlgorithm.from_jwk(_pem_to_jwk(pem)) for kid, pem in certificates.items()}
    _certs_cache.update({"fetched_at": now, "keys": keys})
    return keys


def _pem_to_jwk(pem: str) -> str:  # pragma: no cover - dependant du reseau
    """Google publie des certificats X.509 ; PyJWT attend une cle publique."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.x509 import load_pem_x509_certificate

    certificate = load_pem_x509_certificate(pem.encode())
    public_key = certificate.public_key()
    return public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()


async def verify_id_token(id_token: str) -> dict[str, Any]:
    """Valide un jeton Firebase et renvoie ses revendications."""
    if not is_enabled():
        raise AuthenticationError(
            "L'authentification Firebase n'est pas configuree sur ce serveur.",
            code="firebase_disabled",
        )
    try:
        header = jwt.get_unverified_header(id_token)
        keys = await _public_keys()
        key = keys.get(header.get("kid"))
        if key is None:
            raise AuthenticationError("Certificat Firebase inconnu.")
        project = settings.firebase_project_id
        return jwt.decode(
            id_token,
            key=key,
            algorithms=["RS256"],
            audience=project,
            issuer=f"https://securetoken.google.com/{project}",
        )
    except AuthenticationError:
        raise
    except Exception as exc:  # pragma: no cover - erreurs reseau ou jeton casse
        raise AuthenticationError(f"Jeton Firebase invalide : {exc}") from exc
