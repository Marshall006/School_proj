"""Appairage des appareils et synchronisation hors ligne."""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any

from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import (
    CurrentDevice,
    CurrentParent,
    CurrentWriter,
    DbSession,
    DeviceChild,
    load_child,
    load_device,
)
from app.core.clock import assess_device_clock
from app.core.clock import now as clock_now
from app.core.config import settings
from app.core.errors import ConflictError, NotFoundError
from app.core.security import create_token, generate_pairing_code, hash_opaque
from app.core.unlock_protocol import generate_device_secret
from app.models.access import UnlockCode
from app.models.device import Device, PairingRequest
from app.models.enums import DeviceStatus, UnlockCodeStatus
from app.schemas.device import (
    DeviceClaimRequest,
    DeviceCredentials,
    DeviceOut,
    DeviceSyncRequest,
    DeviceSyncResponse,
    PairingCodeOut,
    PairingCodeRequest,
)
from app.services import audit, lockouts, screen_time
from app.services.policy import resolve_policy

router = APIRouter(tags=["Appareils"])


# ---------------------------------------------------------------------------
# Cote parent
# ---------------------------------------------------------------------------


@router.post("/devices/pairing-code", response_model=PairingCodeOut, status_code=201)
async def create_pairing_code(
    db: DbSession, parent: CurrentWriter, payload: PairingCodeRequest
) -> PairingCodeOut:
    """Genere un code d'appairage a usage unique, a saisir sur la tablette."""
    child = await load_child(db, parent, payload.child_id)
    code = generate_pairing_code()
    expires_at = clock_now() + timedelta(minutes=payload.ttl_minutes)
    db.add(
        PairingRequest(
            child_id=child.id,
            created_by_parent_id=parent.id,
            code_hash=hash_opaque(code),
            expires_at=expires_at,
            suggested_name=payload.suggested_name,
        )
    )
    await audit.record(
        db,
        family_id=parent.family_id,
        action="device.pairing_code_created",
        actor_type="parent",
        actor_id=parent.id,
        target_type="child",
        target_id=child.id,
    )
    await db.commit()
    return PairingCodeOut(code=code, expires_at=expires_at, child_id=child.id)


@router.get("/devices", response_model=list[DeviceOut])
async def list_devices(db: DbSession, parent: CurrentParent) -> list[Device]:
    from app.models.family import Child

    return list(
        (
            await db.execute(
                select(Device)
                .join(Child, Child.id == Device.child_id)
                .where(Child.family_id == parent.family_id)
                .order_by(Device.created_at)
            )
        ).scalars()
    )


@router.post("/devices/{device_id}/revoke", response_model=DeviceOut)
async def revoke_device(db: DbSession, parent: CurrentWriter, device_id: uuid.UUID) -> Device:
    """Coupe l'acces d'un appareil : jeton invalide et session en cours arretee."""
    device = await load_device(db, parent, device_id)
    device.status = DeviceStatus.REVOKED
    session = await screen_time.active_session_for_device(db, device.id)
    if session:
        await screen_time.end_session(db, session, reason="revoked")
    await audit.record(
        db,
        family_id=parent.family_id,
        action="device.revoked",
        actor_type="parent",
        actor_id=parent.id,
        target_type="device",
        target_id=device.id,
    )
    await db.commit()
    return device


@router.post("/devices/{device_id}/unlock-attempts/reset", response_model=DeviceOut)
async def reset_attempts(db: DbSession, parent: CurrentWriter, device_id: uuid.UUID) -> Device:
    """Le parent debloque la saisie apres trop de codes errones."""
    device = await load_device(db, parent, device_id)
    device.failed_code_attempts = 0
    device.code_locked_until = None
    await db.commit()
    return device


# ---------------------------------------------------------------------------
# Cote appareil
# ---------------------------------------------------------------------------


@router.post("/devices/claim", response_model=DeviceCredentials, status_code=201)
async def claim_device(db: DbSession, payload: DeviceClaimRequest) -> DeviceCredentials:
    """L'appareil echange le code d'appairage contre ses identifiants durables.

    Le `device_secret` n'est transmis qu'ici : il permet ensuite de valider les
    codes de deverrouillage **sans reseau**.
    """
    now = clock_now()
    request = (
        await db.execute(
            select(PairingRequest).where(
                PairingRequest.code_hash == hash_opaque(payload.pairing_code.strip().upper())
            )
        )
    ).scalar_one_or_none()
    if request is None:
        raise NotFoundError("Code d'appairage inconnu.", code="pairing_code_unknown")
    if request.consumed_at is not None:
        raise ConflictError("Ce code d'appairage a deja ete utilise.")
    if request.expires_at < now:
        raise ConflictError("Ce code d'appairage a expire.", code="pairing_code_expired")

    device = Device(
        child_id=request.child_id,
        name=payload.name or request.suggested_name or "Tablette",
        platform=payload.platform,
        status=DeviceStatus.ACTIVE,
        device_secret=generate_device_secret(),
        app_version=payload.app_version,
        os_version=payload.os_version,
        hardware_id=payload.hardware_id,
        boot_id=payload.boot_id,
        last_seen_at=now,
        last_sync_at=now,
    )
    db.add(device)
    await db.flush()

    request.consumed_at = now
    request.device_id = device.id

    from app.models.family import Child

    child = await db.get(Child, device.child_id)
    token = create_token(
        str(device.id),
        "device",
        claims={"child_id": str(device.child_id), "family_id": str(child.family_id)},
    )
    await audit.record(
        db,
        family_id=child.family_id,
        action="device.paired",
        actor_type="device",
        actor_id=device.id,
        target_type="child",
        target_id=child.id,
        payload={"platform": payload.platform.value, "name": device.name},
    )
    await db.commit()
    return DeviceCredentials(
        device_id=device.id,
        child_id=device.child_id,
        device_token=token,
        device_secret=device.device_secret,
        accepted_counter=device.accepted_counter,
        server_time=now,
    )


@router.post("/device/sync", response_model=DeviceSyncResponse)
async def sync(
    db: DbSession,
    device: CurrentDevice,
    child: DeviceChild,
    payload: DeviceSyncRequest,
) -> DeviceSyncResponse:
    """Battement de synchronisation : regles, carence, session, revocations.

    C'est l'appel que l'application enfant emet regulierement, y compris quand
    l'ecran est verrouille. Il sert aussi a mesurer la derive d'horloge.
    """
    now = clock_now()
    messages: list[str] = []

    verdict = assess_device_clock(
        device_wall_ms=payload.device_wall_ms or int(now.timestamp() * 1000),
        server_time=now,
        tolerance_ms=settings.max_clock_skew_ms,
    )
    device.clock_skew_ms = verdict.skew_ms
    if verdict.tampered:
        device.tamper_score = min(5.0, device.tamper_score + 0.5)
        messages.append(
            "L'heure de cet appareil est incoherente : le decompte utilise l'horloge du serveur."
        )
    device.last_sync_at = now
    device.last_seen_at = now
    if payload.boot_id:
        device.boot_id = payload.boot_id
    if payload.app_version:
        device.app_version = payload.app_version
    if payload.os_version:
        device.os_version = payload.os_version

    policy = await resolve_policy(db, child, now)
    lockout = await lockouts.active_lockout(db, child.id, at=now)
    session = await screen_time.active_session_for_device(db, device.id)

    revoked = list(
        (
            await db.execute(
                select(UnlockCode.fingerprint).where(
                    UnlockCode.device_id == device.id,
                    UnlockCode.status == UnlockCodeStatus.REVOKED,
                    UnlockCode.created_at >= now - timedelta(days=7),
                )
            )
        ).scalars()
    )

    session_payload: dict[str, Any] | None = None
    if session:
        session_payload = {
            "id": str(session.id),
            "state": session.state.value,
            "remaining_ms": session.remaining_ms,
            "granted_ms": session.total_ms,
            "consumed_ms": session.consumed_ms,
            "started_at": session.started_at.isoformat(),
            "wall_deadline_at": session.wall_deadline_at.isoformat(),
        }

    await db.commit()
    return DeviceSyncResponse(
        server_time=now,
        clock_skew_ms=verdict.skew_ms,
        clock_trustworthy=verdict.trustworthy,
        child={
            "id": str(child.id),
            "display_name": child.display_name,
            "grade_code": child.grade_code,
            "country_code": child.country_code,
            "avatar": child.avatar,
            "xp_balance": child.xp_balance,
            "streak_days": child.streak_days,
        },
        policy=policy.to_dict(),
        lockout=lockouts.describe(lockout, now) if lockout else None,
        active_session=session_payload,
        revoked_code_fingerprints=list(revoked),
        accepted_counter=device.accepted_counter,
        lookahead_window=settings.unlock_lookahead_window,
        heartbeat_interval_seconds=settings.heartbeat_interval_seconds,
        should_lock=session is None or not session.is_live,
        messages=messages,
    )
