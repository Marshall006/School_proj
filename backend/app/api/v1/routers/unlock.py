"""Deverrouillage : codes parentaux, consommation, conversion d'XP, minuteur."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.api.deps import (
    CurrentDevice,
    CurrentParent,
    CurrentWriter,
    DbSession,
    DeviceChild,
    load_child,
)
from app.core import unlock_protocol as proto
from app.core.clock import now as clock_now
from app.core.errors import ConflictError, NotFoundError, PolicyForbidsError
from app.models.access import ScreenSession, UnlockCode
from app.models.device import Device
from app.models.enums import DeviceStatus, XPReason
from app.schemas.access import (
    ExtendRequest,
    HeartbeatRequest,
    HeartbeatResponse,
    ParentUnlockRequest,
    RedeemRequest,
    RedeemResponse,
    ScreenSessionOut,
    UnlockCodeOut,
    UnlockCodeRecordOut,
    XPConversionQuote,
    XPConversionRequest,
)
from app.services import audit, screen_time, unlock, xp
from app.services.policy import resolve_policy

router = APIRouter(tags=["Déverrouillage et temps d'écran"])


async def _pick_device(db, child_id: uuid.UUID, device_id: uuid.UUID | None) -> Device:
    """Appareil designe, ou le seul appareil actif de l'enfant."""
    if device_id is not None:
        device = await db.get(Device, device_id)
        if device is None or device.child_id != child_id:
            raise NotFoundError("Appareil introuvable pour cet enfant.")
        return device
    devices = list(
        (
            await db.execute(
                select(Device).where(
                    Device.child_id == child_id, Device.status == DeviceStatus.ACTIVE
                )
            )
        ).scalars()
    )
    if not devices:
        raise NotFoundError("Aucun appareil appaire pour cet enfant.", code="no_paired_device")
    if len(devices) > 1:
        raise ConflictError(
            "Plusieurs appareils sont appaires : precise lequel deverrouiller.",
            code="device_ambiguous",
            details={"devices": [{"id": str(d.id), "name": d.name} for d in devices]},
        )
    return devices[0]


# ---------------------------------------------------------------------------
# Deverrouillage parental direct
# ---------------------------------------------------------------------------


@router.post("/unlock/parent-code", response_model=UnlockCodeOut, status_code=201)
async def issue_parent_code(
    db: DbSession, parent: CurrentWriter, payload: ParentUnlockRequest
) -> UnlockCodeOut:
    """Les devoirs sont faits : le parent genere un code a dicter a l'enfant.

    Le code fonctionne meme si la tablette est hors ligne.
    """
    child = await load_child(db, parent, payload.child_id)
    device = await _pick_device(db, child.id, payload.device_id)
    policy = await resolve_policy(db, child)

    if not policy.allow_parent_direct_unlock:
        raise PolicyForbidsError(
            "Le déverrouillage direct est désactivé pour la période en cours "
            f"({policy.period_type.value}). Modifie les regles pour l'autoriser.",
            details={"period_type": policy.period_type.value},
        )

    issued = await unlock.issue_code(
        db,
        child=child,
        device=device,
        duration_minutes=payload.duration_minutes,
        kind=proto.UnlockKind.PARENT_DIRECT,
        issued_by_parent_id=parent.id,
        note=payload.note,
        ttl_minutes=payload.ttl_minutes,
    )
    await db.commit()
    return UnlockCodeOut(
        id=issued.record.id,
        code=issued.code,
        formatted=issued.formatted,
        kind=issued.record.kind,
        duration_minutes=issued.record.duration_minutes,
        expires_at=issued.record.expires_at,
        device_id=device.id,
        child_id=child.id,
    )


@router.post("/unlock/bonus-code", response_model=UnlockCodeOut, status_code=201)
async def issue_bonus_code(
    db: DbSession, parent: CurrentWriter, payload: ParentUnlockRequest
) -> UnlockCodeOut:
    """Rallonge exceptionnelle : passe outre le profil de periode, pas le plafond."""
    child = await load_child(db, parent, payload.child_id)
    device = await _pick_device(db, child.id, payload.device_id)
    issued = await unlock.issue_code(
        db,
        child=child,
        device=device,
        duration_minutes=payload.duration_minutes,
        kind=proto.UnlockKind.PARENT_BONUS,
        issued_by_parent_id=parent.id,
        note=payload.note or "Bonus parental",
        ttl_minutes=payload.ttl_minutes,
    )
    await db.commit()
    return UnlockCodeOut(
        id=issued.record.id,
        code=issued.code,
        formatted=issued.formatted,
        kind=issued.record.kind,
        duration_minutes=issued.record.duration_minutes,
        expires_at=issued.record.expires_at,
        device_id=device.id,
        child_id=child.id,
    )


@router.get("/unlock/codes", response_model=list[UnlockCodeRecordOut])
async def list_codes(
    db: DbSession,
    parent: CurrentParent,
    child_id: uuid.UUID,
    limit: int = Query(default=20, ge=1, le=100),
) -> list[UnlockCode]:
    child = await load_child(db, parent, child_id)
    return list(
        (
            await db.execute(
                select(UnlockCode)
                .where(UnlockCode.child_id == child.id)
                .order_by(UnlockCode.created_at.desc())
                .limit(limit)
            )
        ).scalars()
    )


@router.post("/unlock/codes/{code_id}/revoke", response_model=UnlockCodeRecordOut)
async def revoke_code(db: DbSession, parent: CurrentWriter, code_id: uuid.UUID) -> UnlockCode:
    record = await db.get(UnlockCode, code_id)
    if record is None:
        raise NotFoundError("Code introuvable.")
    await load_child(db, parent, record.child_id)
    await unlock.revoke_code(db, record, parent_id=parent.id, family_id=parent.family_id)
    await db.commit()
    return record


# ---------------------------------------------------------------------------
# Consommation d'un code (cote appareil)
# ---------------------------------------------------------------------------


@router.post("/unlock/redeem", response_model=RedeemResponse)
async def redeem(
    db: DbSession,
    device: CurrentDevice,
    child: DeviceChild,
    payload: RedeemRequest,
) -> RedeemResponse:
    """Valide un code saisi sur la tablette et ouvre le temps d'ecran.

    L'appareil peut aussi avoir valide le code hors ligne : il transmet alors
    `consumed_offline_at` et le temps deja consomme, que le serveur reconcilie.
    """
    policy = await resolve_policy(db, child)
    result = await unlock.redeem_code(
        db,
        device=device,
        child=child,
        code=payload.code,
        policy=policy,
        boot_id=payload.boot_id,
        consumed_offline_at=payload.consumed_offline_at,
        reported_offline_ms=payload.offline_active_ms,
    )
    await db.commit()
    return RedeemResponse(**result.to_dict())


# ---------------------------------------------------------------------------
# Conversion des XP en minutes
# ---------------------------------------------------------------------------


@router.post("/unlock/xp/quote", response_model=XPConversionQuote)
async def quote_xp(
    db: DbSession, parent: CurrentParent, payload: XPConversionRequest
) -> XPConversionQuote:
    child = await load_child(db, parent, payload.child_id)
    policy = await resolve_policy(db, child)
    used = await screen_time.minutes_granted_today(db, child.id)
    quote = xp.quote_conversion(
        xp_balance=child.xp_balance,
        xp_to_spend=payload.xp_to_spend,
        minutes_per_100_xp=policy.minutes_per_100_xp,
        daily_bonus_used_minutes=max(0, used - policy.reward_minutes),
        daily_bonus_cap_minutes=policy.xp_daily_bonus_cap_minutes,
    )
    return XPConversionQuote(
        minutes=quote.minutes,
        xp_spent=quote.xp_spent,
        xp_remaining=quote.xp_remaining,
        capped_by_daily_limit=quote.capped_by_daily_limit,
        reason=quote.reason,
        minutes_per_100_xp=policy.minutes_per_100_xp,
    )


@router.post("/unlock/xp/redeem", response_model=RedeemResponse)
async def redeem_xp(
    db: DbSession,
    device: CurrentDevice,
    child: DeviceChild,
    payload: XPConversionRequest,
) -> RedeemResponse:
    """L'enfant convertit ses XP en minutes supplementaires.

    Les XP viennent des evaluations facultatives : l'effort volontaire se
    transforme en temps d'ecran, sans jamais depasser le plafond du jour.
    """
    policy = await resolve_policy(db, child)
    used = await screen_time.minutes_granted_today(db, child.id)
    quote = xp.quote_conversion(
        xp_balance=child.xp_balance,
        xp_to_spend=payload.xp_to_spend,
        minutes_per_100_xp=policy.minutes_per_100_xp,
        daily_bonus_used_minutes=max(0, used - policy.reward_minutes),
        daily_bonus_cap_minutes=policy.xp_daily_bonus_cap_minutes,
    )
    if not quote.ok:
        raise ConflictError(
            quote.reason or "Conversion impossible.",
            code="xp_conversion_unavailable",
            details={"xp_balance": child.xp_balance, "minutes": quote.minutes},
        )

    await xp.record_xp(
        db,
        child,
        [
            xp.XPGrant(
                amount=-quote.xp_spent,
                reason=XPReason.REDEEM,
                label=f"Conversion en {quote.minutes} minutes d'écran",
                meta={"minutes": quote.minutes},
            )
        ],
        ref_type="xp_redeem",
    )
    issued = await unlock.issue_code(
        db,
        child=child,
        device=device,
        duration_minutes=quote.minutes,
        kind=proto.UnlockKind.XP_REDEEM,
        note=f"{quote.xp_spent} XP convertis",
    )
    result = await unlock.redeem_code(
        db, device=device, child=child, code=issued.code, policy=policy
    )
    await db.commit()
    return RedeemResponse(**result.to_dict())


# ---------------------------------------------------------------------------
# Minuteur
# ---------------------------------------------------------------------------


@router.get("/screen/current", response_model=ScreenSessionOut | None)
async def current_session(db: DbSession, device: CurrentDevice) -> ScreenSession | None:
    return await screen_time.active_session_for_device(db, device.id)


@router.post("/screen/sessions/{session_id}/heartbeat", response_model=HeartbeatResponse)
async def heartbeat(
    db: DbSession,
    device: CurrentDevice,
    session_id: uuid.UUID,
    payload: HeartbeatRequest,
) -> HeartbeatResponse:
    """Battement du minuteur : consomme le temps ecoule, detecte les anomalies."""
    session = await screen_time.get_session_or_404(db, session_id)
    if session.device_id != device.id:
        raise NotFoundError("Session introuvable pour cet appareil.")

    result = await screen_time.heartbeat(
        db,
        session,
        monotonic_ms=payload.monotonic_ms,
        device_wall_ms=payload.device_wall_ms,
        screen_on=payload.screen_on,
        boot_id=payload.boot_id,
    )
    if payload.device_wall_ms is not None:
        device.clock_skew_ms = int(payload.device_wall_ms - clock_now().timestamp() * 1000)
    if result.anomalies:
        device.tamper_score = min(5.0, device.tamper_score + 0.25 * len(result.anomalies))
    await db.commit()
    return HeartbeatResponse(**result.to_dict())


@router.post("/screen/sessions/{session_id}/pause", response_model=ScreenSessionOut)
async def pause(db: DbSession, device: CurrentDevice, session_id: uuid.UUID) -> ScreenSession:
    session = await screen_time.get_session_or_404(db, session_id)
    if session.device_id != device.id:
        raise NotFoundError("Session introuvable pour cet appareil.")
    await screen_time.pause_session(db, session)
    await db.commit()
    return session


@router.post("/screen/sessions/{session_id}/resume", response_model=ScreenSessionOut)
async def resume(
    db: DbSession,
    device: CurrentDevice,
    session_id: uuid.UUID,
    monotonic_ms: int | None = None,
) -> ScreenSession:
    session = await screen_time.get_session_or_404(db, session_id)
    if session.device_id != device.id:
        raise NotFoundError("Session introuvable pour cet appareil.")
    await screen_time.resume_session(db, session, monotonic_ms=monotonic_ms)
    await db.commit()
    return session


@router.post("/screen/sessions/{session_id}/end", response_model=ScreenSessionOut)
async def end(db: DbSession, device: CurrentDevice, session_id: uuid.UUID) -> ScreenSession:
    session = await screen_time.get_session_or_404(db, session_id)
    if session.device_id != device.id:
        raise NotFoundError("Session introuvable pour cet appareil.")
    await screen_time.end_session(db, session, reason="child_stop")
    await db.commit()
    return session


@router.post("/screen/sessions/{session_id}/extend", response_model=ScreenSessionOut)
async def extend(
    db: DbSession, parent: CurrentWriter, session_id: uuid.UUID, payload: ExtendRequest
) -> ScreenSession:
    """Rallonge parentale sur une session deja ouverte."""
    session = await screen_time.get_session_or_404(db, session_id)
    await load_child(db, parent, session.child_id)
    await screen_time.extend_session(db, session, minutes=payload.minutes)
    await audit.record(
        db,
        family_id=parent.family_id,
        action="screen_session.extended",
        actor_type="parent",
        actor_id=parent.id,
        target_type="screen_session",
        target_id=session.id,
        payload={"minutes": payload.minutes, "reason": payload.reason},
    )
    await db.commit()
    return session


@router.post("/screen/sessions/{session_id}/stop", response_model=ScreenSessionOut)
async def stop(db: DbSession, parent: CurrentWriter, session_id: uuid.UUID) -> ScreenSession:
    """Coupure immediate a distance."""
    session = await screen_time.get_session_or_404(db, session_id)
    await load_child(db, parent, session.child_id)
    await screen_time.end_session(db, session, reason="parent_stop")
    await audit.record(
        db,
        family_id=parent.family_id,
        action="screen_session.stopped",
        actor_type="parent",
        actor_id=parent.id,
        target_type="screen_session",
        target_id=session.id,
    )
    await db.commit()
    return session


@router.get("/children/{child_id}/screen-sessions", response_model=list[ScreenSessionOut])
async def list_sessions(
    db: DbSession,
    parent: CurrentParent,
    child_id: uuid.UUID,
    limit: int = Query(default=20, ge=1, le=100),
) -> list[ScreenSession]:
    child = await load_child(db, parent, child_id)
    return list(
        (
            await db.execute(
                select(ScreenSession)
                .where(ScreenSession.child_id == child.id)
                .order_by(ScreenSession.started_at.desc())
                .limit(limit)
            )
        ).scalars()
    )


@router.get("/screen/sessions/{session_id}/events")
async def session_events(
    db: DbSession, parent: CurrentParent, session_id: uuid.UUID
) -> dict[str, Any]:
    """Journal detaille d'une session : utile pour comprendre une anomalie."""
    from app.models.access import ScreenEvent

    session = await screen_time.get_session_or_404(db, session_id)
    await load_child(db, parent, session.child_id)
    events = list(
        (
            await db.execute(
                select(ScreenEvent)
                .where(ScreenEvent.session_id == session.id)
                .order_by(ScreenEvent.created_at)
            )
        ).scalars()
    )
    return {
        "session_id": str(session.id),
        "state": session.state.value,
        "integrity_score": round(session.integrity_score, 2),
        "events": [
            {
                "type": event.type.value,
                "at": event.created_at.isoformat(),
                "delta_ms": event.delta_ms,
                "monotonic_ms": event.monotonic_ms,
                "skew_ms": event.skew_ms,
                "screen_on": event.screen_on,
                "meta": event.meta,
            }
            for event in events
        ],
    }
