"""Erreurs metier.

Chaque erreur porte un `code` stable (exploitable par les clients pour afficher
le bon ecran) et un message deja redige en francais pour l'utilisateur final.
`details` transporte ce dont l'interface a besoin : instant de fin de carence,
minutes restantes, notions a reviser...
"""

from __future__ import annotations

from typing import Any


class DomainError(Exception):
    """Erreur fonctionnelle : jamais un bug, toujours une regle du produit."""

    status_code = 400
    code = "domain_error"

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        status_code: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if code:
            self.code = code
        if status_code:
            self.status_code = status_code
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        return {"error": {"code": self.code, "message": self.message, "details": self.details}}


class NotFoundError(DomainError):
    status_code = 404
    code = "not_found"


class PermissionDeniedError(DomainError):
    status_code = 403
    code = "permission_denied"


class AuthenticationError(DomainError):
    status_code = 401
    code = "unauthenticated"


class ConflictError(DomainError):
    status_code = 409
    code = "conflict"


class RateLimitedError(DomainError):
    status_code = 429
    code = "rate_limited"


# --- Regles specifiques au produit ----------------------------------------


class CooldownActiveError(DomainError):
    """Temps de carence en cours : l'enfant doit reviser avant de retenter."""

    status_code = 423
    code = "cooldown_active"


class InvalidUnlockCodeError(DomainError):
    status_code = 400
    code = "invalid_unlock_code"


class DeviceLockedError(DomainError):
    """Trop d'essais de code : saisie bloquee temporairement."""

    status_code = 423
    code = "device_locked"


class CurfewError(DomainError):
    status_code = 423
    code = "curfew"


class DailyCapReachedError(DomainError):
    status_code = 423
    code = "daily_cap_reached"


class PolicyForbidsError(DomainError):
    status_code = 403
    code = "policy_forbids"


class NoContentAvailableError(DomainError):
    status_code = 409
    code = "no_content_available"
