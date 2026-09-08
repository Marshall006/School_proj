"""Dependances FastAPI : authentification parent, authentification appareil, acces enfant.

Deux identites coexistent :

- le **parent**, authentifie par mot de passe (ou Firebase) sur le tableau de
  bord web, porteur d'un jeton court + jeton de rafraichissement ;
- l'**appareil** de l'enfant, authentifie par un jeton d'appairage de longue
  duree emis une seule fois. Il n'a acces qu'a son propre enfant.
"""

from __future__ import annotations

import uuid
from typing import Annotated

import jwt
from fastapi import Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import now as clock_now
from app.core.errors import AuthenticationError, NotFoundError, PermissionDeniedError
from app.core.security import decode_token
from app.db.session import get_session
from app.models.device import Device
from app.models.enums import DeviceStatus, ParentRole
from app.models.family import Child, Family, Parent

DbSession = Annotated[AsyncSession, Depends(get_session)]


def _bearer(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise AuthenticationError("Jeton d'acces manquant.")
    return authorization.split(" ", 1)[1].strip()


async def current_parent(
    db: DbSession,
    authorization: Annotated[str | None, Header()] = None,
) -> Parent:
    token = _bearer(authorization)
    try:
        payload = decode_token(token, expected_type="access")
    except jwt.ExpiredSignatureError as exc:
        raise AuthenticationError("Session expiree, reconnecte-toi.", code="token_expired") from exc
    except jwt.InvalidTokenError as exc:
        raise AuthenticationError("Jeton invalide.") from exc

    parent = await db.get(Parent, uuid.UUID(payload["sub"]))
    if parent is None or not parent.is_active:
        raise AuthenticationError("Compte introuvable ou desactive.")
    return parent


CurrentParent = Annotated[Parent, Depends(current_parent)]


async def current_writer(parent: CurrentParent) -> Parent:
    """Refuse les comptes en lecture seule pour toute action modifiante."""
    if parent.role == ParentRole.VIEWER:
        raise PermissionDeniedError("Ce compte est en lecture seule.")
    return parent


CurrentWriter = Annotated[Parent, Depends(current_writer)]


async def current_family(db: DbSession, parent: CurrentParent) -> Family:
    family = await db.get(Family, parent.family_id)
    if family is None:
        raise NotFoundError("Foyer introuvable.")
    return family


CurrentFamily = Annotated[Family, Depends(current_family)]


async def current_device(
    db: DbSession,
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
    x_device_token: Annotated[str | None, Header()] = None,
) -> Device:
    token = x_device_token or _bearer(authorization)
    try:
        payload = decode_token(token, expected_type="device")
    except jwt.InvalidTokenError as exc:
        raise AuthenticationError("Appareil non reconnu.", code="device_unauthenticated") from exc

    device = await db.get(Device, uuid.UUID(payload["sub"]))
    if device is None:
        raise AuthenticationError("Appareil introuvable.")
    if device.status != DeviceStatus.ACTIVE:
        raise PermissionDeniedError(
            "Cet appareil a ete revoque par le parent.", code="device_revoked"
        )
    device.last_seen_at = clock_now()
    request.state.device_id = str(device.id)
    return device


CurrentDevice = Annotated[Device, Depends(current_device)]


async def device_child(db: DbSession, device: CurrentDevice) -> Child:
    child = await db.get(Child, device.child_id)
    if child is None:
        raise NotFoundError("Enfant introuvable.")
    return child


DeviceChild = Annotated[Child, Depends(device_child)]


async def load_child(db: AsyncSession, parent: Parent, child_id: uuid.UUID) -> Child:
    """Charge un enfant en verifiant qu'il appartient bien au foyer du parent."""
    child = await db.get(Child, child_id)
    if child is None:
        raise NotFoundError("Enfant introuvable.")
    if child.family_id != parent.family_id:
        raise PermissionDeniedError("Cet enfant n'appartient pas a votre foyer.")
    return child


async def load_device(db: AsyncSession, parent: Parent, device_id: uuid.UUID) -> Device:
    device = await db.get(Device, device_id)
    if device is None:
        raise NotFoundError("Appareil introuvable.")
    await load_child(db, parent, device.child_id)
    return device
