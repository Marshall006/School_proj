"""Emission et consommation des codes de deverrouillage.

Deux chemins mènent au code, comme le veut le modele "Learn-to-Play" :

- **Deverrouillage parental direct** (periode scolaire) : les devoirs sont
  faits, le parent genere un code depuis son tableau de bord et le dicte.
- **Deverrouillage par evaluation** (vacances, revisions) : l'enfant obtient le
  code automatiquement en depassant le seuil exige.

Dans les deux cas, le code est verifiable hors ligne (voir
`app.core.unlock_protocol`) et consommable une seule fois.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import unlock_protocol as proto
from app.core.clock import now as clock_now
from app.core.config import settings
from app.core.errors import (
    ConflictError,
    CurfewError,
    DailyCapReachedError,
    DeviceLockedError,
    InvalidUnlockCodeError,
    PolicyForbidsError,
)
from app.models.access import ScreenSession, UnlockCode
from app.models.device import Device
from app.models.enums import DeviceStatus, LockoutReason, UnlockCodeStatus
from app.models.family import Child
from app.services import audit, lockouts, screen_time
from app.services.policy import EffectivePolicy, is_within_curfew, next_curfew_end

#: Codes que l'enfant declenche lui-meme : soumis a la carence et au couvre-feu.
CHILD_INITIATED = {proto.UnlockKind.ASSESSMENT_REWARD, proto.UnlockKind.XP_REDEEM}


@dataclass(slots=True)
class IssuedCode:
    code: str
    record: UnlockCode

    @property
    def formatted(self) -> str:
        return proto.format_code(self.code)

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "formatted": self.formatted,
            "kind": self.record.kind,
            "duration_minutes": self.record.duration_minutes,
            "expires_at": self.record.expires_at.isoformat(),
            "id": str(self.record.id),
        }


@dataclass(slots=True)
class RedeemResult:
    session: ScreenSession
    code_record: UnlockCode | None
    granted_minutes: int
    truncated_by_cap: bool
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": str(self.session.id),
            "granted_minutes": self.granted_minutes,
            "granted_ms": self.session.total_ms,
            "remaining_ms": self.session.remaining_ms,
            "started_at": self.session.started_at.isoformat(),
            "wall_deadline_at": self.session.wall_deadline_at.isoformat(),
            "truncated_by_cap": self.truncated_by_cap,
            "warnings": self.warnings,
            "heartbeat_interval_seconds": settings.heartbeat_interval_seconds,
        }


# ---------------------------------------------------------------------------
# Emission
# ---------------------------------------------------------------------------


def snap_duration(minutes: int) -> int:
    """Arrondit au pas de 5 minutes, dans les bornes transportables par un code."""
    step = proto.DURATION_STEP_MINUTES
    minutes = max(step, int(minutes))
    minutes -= minutes % step
    return min(minutes, proto.MAX_DURATION_UNITS * step)


async def issue_code(
    db: AsyncSession,
    *,
    child: Child,
    device: Device,
    duration_minutes: int,
    kind: proto.UnlockKind = proto.UnlockKind.PARENT_DIRECT,
    issued_by_parent_id: uuid.UUID | None = None,
    assessment_id: uuid.UUID | None = None,
    note: str | None = None,
    at: datetime | None = None,
    ttl_minutes: int | None = None,
) -> IssuedCode:
    """Genere un code et en conserve l'empreinte (jamais le code en clair)."""
    at = at or clock_now()
    if device.status != DeviceStatus.ACTIVE:
        raise ConflictError("Cet appareil n'est plus actif.", code="device_inactive")

    minutes = snap_duration(duration_minutes)
    device.unlock_counter += 1
    counter = device.unlock_counter

    code = proto.issue_code(
        secret_hex=device.device_secret,
        device_id=str(device.id),
        counter=counter,
        duration_minutes=minutes,
        kind=kind,
        now=at.timestamp(),
    )

    record = UnlockCode(
        child_id=child.id,
        device_id=device.id,
        kind=kind.name.lower(),
        status=UnlockCodeStatus.ISSUED,
        counter=counter,
        duration_minutes=minutes,
        fingerprint=proto.code_fingerprint(code, str(device.id)),
        issued_by_parent_id=issued_by_parent_id,
        assessment_id=assessment_id,
        expires_at=at + timedelta(minutes=ttl_minutes or settings.unlock_code_ttl_minutes),
        note=note,
    )
    db.add(record)
    await db.flush()

    await audit.record(
        db,
        family_id=child.family_id,
        action="unlock_code.issued",
        actor_type="parent" if issued_by_parent_id else "system",
        actor_id=issued_by_parent_id,
        target_type="device",
        target_id=device.id,
        payload={
            "kind": kind.name.lower(),
            "duration_minutes": minutes,
            "counter": counter,
            "child_id": str(child.id),
            "assessment_id": str(assessment_id) if assessment_id else None,
        },
    )
    return IssuedCode(code=code, record=record)


async def revoke_code(
    db: AsyncSession,
    record: UnlockCode,
    *,
    parent_id: uuid.UUID | None = None,
    family_id: uuid.UUID | None = None,
    at: datetime | None = None,
) -> UnlockCode:
    at = at or clock_now()
    if record.status == UnlockCodeStatus.CONSUMED:
        raise ConflictError("Ce code a deja ete utilise.")
    record.status = UnlockCodeStatus.REVOKED
    record.revoked_at = at
    if family_id:
        await audit.record(
            db,
            family_id=family_id,
            action="unlock_code.revoked",
            actor_type="parent",
            actor_id=parent_id,
            target_type="unlock_code",
            target_id=record.id,
        )
    return record


# ---------------------------------------------------------------------------
# Consommation
# ---------------------------------------------------------------------------


async def _register_failed_attempt(
    db: AsyncSession, device: Device, child: Child, at: datetime
) -> None:
    device.failed_code_attempts += 1
    penalty = proto.lockout_seconds_for(device.failed_code_attempts)
    if penalty:
        device.code_locked_until = at + timedelta(seconds=penalty)
        await lockouts.open_lockout(
            db,
            child_id=child.id,
            reason=LockoutReason.CODE_BRUTEFORCE,
            minutes=max(1, penalty // 60),
            message="Trop de codes errones saisis sur l'appareil.",
            at=at,
        )
        await audit.record(
            db,
            family_id=child.family_id,
            action="unlock_code.bruteforce_lockout",
            actor_type="device",
            actor_id=device.id,
            payload={"failed_attempts": device.failed_code_attempts, "penalty_seconds": penalty},
        )
    # Le compteur doit survivre a l'exception qui suit : sans validation
    # explicite, la transaction serait annulee et la force brute redeviendrait
    # gratuite.
    await db.commit()


async def redeem_code(
    db: AsyncSession,
    *,
    device: Device,
    child: Child,
    code: str,
    policy: EffectivePolicy,
    at: datetime | None = None,
    boot_id: str | None = None,
    consumed_offline_at: datetime | None = None,
    reported_offline_ms: int = 0,
) -> RedeemResult:
    """Valide un code saisi sur l'appareil et ouvre la session de temps d'ecran."""
    at = at or clock_now()
    warnings: list[str] = []

    if device.status != DeviceStatus.ACTIVE:
        raise ConflictError("Cet appareil n'est plus actif.", code="device_inactive")

    if device.code_locked_until and device.code_locked_until > at:
        remaining = int((device.code_locked_until - at).total_seconds())
        raise DeviceLockedError(
            "Trop d'essais : la saisie est bloquee temporairement.",
            details={
                "retry_at": device.code_locked_until.isoformat(),
                "remaining_seconds": remaining,
                "failed_attempts": device.failed_code_attempts,
            },
        )

    # --- Verification cryptographique (identique hors ligne) ---------------
    reference_time = (consumed_offline_at or at).timestamp()
    try:
        payload = proto.verify_code(
            code=code,
            secret_hex=device.device_secret,
            device_id=str(device.id),
            last_counter=device.accepted_counter,
            lookahead=settings.unlock_lookahead_window,
            now=reference_time,
        )
    except proto.UnlockProtocolError as exc:
        await _register_failed_attempt(db, device, child, at)
        raise InvalidUnlockCodeError(
            str(exc),
            details={"failed_attempts": device.failed_code_attempts},
        ) from exc

    # --- Verifications metier ---------------------------------------------
    record = (
        await db.execute(
            select(UnlockCode).where(
                UnlockCode.device_id == device.id,
                UnlockCode.fingerprint == proto.code_fingerprint(code, str(device.id)),
            )
        )
    ).scalar_one_or_none()

    if record is None:
        warnings.append("code_sans_trace_serveur")
    else:
        if record.status == UnlockCodeStatus.CONSUMED:
            await _register_failed_attempt(db, device, child, at)
            raise InvalidUnlockCodeError("Ce code a deja ete utilise.")
        if record.status == UnlockCodeStatus.REVOKED:
            await _register_failed_attempt(db, device, child, at)
            raise InvalidUnlockCodeError("Ce code a ete annule par le parent.")
        if record.expires_at < at and consumed_offline_at is None:
            record.status = UnlockCodeStatus.EXPIRED
            await _register_failed_attempt(db, device, child, at)
            raise InvalidUnlockCodeError("Ce code a expire.")

    kind = payload.kind
    if kind == proto.UnlockKind.PARENT_DIRECT and not policy.allow_parent_direct_unlock:
        raise PolicyForbidsError(
            "Le deverrouillage direct est desactive pour cette periode : "
            "l'evaluation est le seul chemin.",
            details={"period_type": policy.period_type.value},
        )

    if kind in CHILD_INITIATED:
        blocking = await lockouts.active_lockout(db, child.id, at=at)
        if blocking:
            raise ConflictError(
                "Un temps de carence est en cours.",
                code="cooldown_active",
                details=lockouts.describe(blocking, at),
            )
        if is_within_curfew(policy, at):
            raise CurfewError(
                "Nous sommes en dehors des horaires autorises.",
                details={
                    "curfew_start": policy.curfew_start,
                    "curfew_end": policy.curfew_end,
                    "resumes_at": (next_curfew_end(policy, at) or at).isoformat(),
                },
            )

    # --- Plafond quotidien -------------------------------------------------
    granted = payload.duration_minutes
    truncated = False
    used_today = await screen_time.minutes_granted_today(db, child.id, at=at)
    remaining_cap = max(0, policy.daily_cap_minutes - used_today)
    if kind != proto.UnlockKind.EMERGENCY and remaining_cap <= 0:
        raise DailyCapReachedError(
            "Le temps d'ecran maximum de la journee est atteint.",
            details={"daily_cap_minutes": policy.daily_cap_minutes, "used_today": used_today},
        )
    if kind != proto.UnlockKind.EMERGENCY and granted > remaining_cap:
        granted, truncated = remaining_cap, True
        warnings.append("duree_reduite_par_plafond_quotidien")

    # --- Consommation ------------------------------------------------------
    device.accepted_counter = payload.counter  # tue tous les codes anterieurs
    device.failed_code_attempts = 0
    device.code_locked_until = None
    device.last_seen_at = at
    if boot_id:
        device.boot_id = boot_id

    if record is not None:
        record.status = UnlockCodeStatus.CONSUMED
        record.consumed_at = consumed_offline_at or at
        record.consumed_offline = consumed_offline_at is not None

    session = await screen_time.start_session(
        db,
        child_id=child.id,
        device=device,
        duration_minutes=granted,
        unlock_code_id=record.id if record else None,
        at=consumed_offline_at or at,
        boot_id=boot_id,
        meta={
            "kind": kind.name.lower(),
            "counter": payload.counter,
            "offline": consumed_offline_at is not None,
        },
    )

    if reported_offline_ms > 0:
        await screen_time.reconcile_offline(
            db, session, reported_active_ms=reported_offline_ms, at=at
        )

    await audit.record(
        db,
        family_id=child.family_id,
        action="unlock_code.redeemed",
        actor_type="device",
        actor_id=device.id,
        target_type="screen_session",
        target_id=session.id,
        payload={
            "kind": kind.name.lower(),
            "granted_minutes": granted,
            "truncated_by_cap": truncated,
            "offline": consumed_offline_at is not None,
            "warnings": warnings,
        },
    )

    return RedeemResult(
        session=session,
        code_record=record,
        granted_minutes=granted,
        truncated_by_cap=truncated,
        warnings=warnings,
    )


async def expire_stale_codes(db: AsyncSession, *, at: datetime | None = None) -> int:
    at = at or clock_now()
    stale = list(
        (
            await db.execute(
                select(UnlockCode).where(
                    UnlockCode.status == UnlockCodeStatus.ISSUED,
                    UnlockCode.expires_at <= at,
                )
            )
        ).scalars()
    )
    for record in stale:
        record.status = UnlockCodeStatus.EXPIRED
    return len(stale)
