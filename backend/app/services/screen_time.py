"""Moteur de temps d'ecran.

Contraintes reelles :

- l'appareil est souvent hors ligne ;
- l'enfant peut eteindre l'ecran (le minuteur doit se figer) ;
- l'enfant peut changer l'heure systeme, redemarrer, forcer l'arret de l'app.

Principe retenu : **on ne fait jamais confiance a l'horloge murale de
l'appareil**. Le decompte s'appuie sur une horloge *monotone* (temps ecoule
depuis le demarrage, insensible aux reglages) rapportee a chaque battement de
coeur, bornee par le temps reellement ecoule cote serveur. Deux garde-fous :

1. `delta_monotone <= delta_serveur * marge` : impossible de consommer plus de
   temps qu'il n'en est passe (protection contre une horloge acceleree) ;
2. `wall_deadline_at = debut + duree x facteur` : une session ne peut pas etre
   etiree indefiniment en enchainant les pauses.

Toute incoherence produit un evenement `TAMPER` visible dans le tableau de bord
parental : le produit prefere informer le parent plutot que punir l'enfant.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import assess_device_clock
from app.core.clock import now as clock_now
from app.core.config import settings
from app.core.errors import ConflictError, NotFoundError
from app.models.access import ScreenEvent, ScreenSession
from app.models.device import Device
from app.models.enums import ScreenEventType, ScreenSessionState

TAMPER_PENALTY = 0.15


@dataclass(slots=True)
class HeartbeatResult:
    session: ScreenSession
    consumed_delta_ms: int
    remaining_ms: int
    state: ScreenSessionState
    anomalies: list[str]
    should_lock: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": str(self.session.id),
            "state": self.state.value,
            "remaining_ms": self.remaining_ms,
            "remaining_minutes": self.remaining_ms // 60000,
            "consumed_ms": self.session.consumed_ms,
            "granted_ms": self.session.total_ms,
            "should_lock": self.should_lock,
            "anomalies": self.anomalies,
            "server_time": clock_now().isoformat(),
            "wall_deadline_at": self.session.wall_deadline_at.isoformat(),
        }


# ---------------------------------------------------------------------------
# Cycle de vie
# ---------------------------------------------------------------------------


async def start_session(
    db: AsyncSession,
    *,
    child_id: uuid.UUID,
    device: Device,
    duration_minutes: int,
    unlock_code_id: uuid.UUID | None = None,
    at: datetime | None = None,
    boot_id: str | None = None,
    meta: dict[str, Any] | None = None,
) -> ScreenSession:
    """Ouvre une fenetre de temps d'ecran, en fermant proprement la precedente."""
    at = at or clock_now()
    granted_ms = duration_minutes * 60_000

    for existing in await _live_sessions(db, device.id, at=at):
        await end_session(db, existing, reason="superseded", at=at)

    session = ScreenSession(
        child_id=child_id,
        device_id=device.id,
        unlock_code_id=unlock_code_id,
        state=ScreenSessionState.ACTIVE,
        granted_ms=granted_ms,
        started_at=at,
        wall_deadline_at=at
        + timedelta(minutes=duration_minutes * settings.session_wall_stretch_factor),
        last_heartbeat_at=at,
        last_monotonic_ms=0,
        device_boot_id=boot_id or device.boot_id,
        meta=meta or {},
    )
    db.add(session)
    await db.flush()
    await _log(db, session, ScreenEventType.START, meta={"granted_ms": granted_ms})
    return session


def expire_if_due(session: ScreenSession, at: datetime | None = None) -> bool:
    """Ferme une session dont le butoir absolu est depasse ou le temps epuise.

    Une tablette qui ne donne plus signe de vie ne doit pas rester "ouverte"
    indefiniment dans le tableau de bord : sans battement de coeur, c'est le
    butoir qui tranche.
    """
    at = at or clock_now()
    if not session.is_live:
        return False
    if session.remaining_ms > 0 and at < session.wall_deadline_at:
        return False
    session.state = ScreenSessionState.EXPIRED
    session.ended_at = at
    session.end_reason = "time_exhausted" if session.remaining_ms <= 0 else "wall_deadline"
    return True


async def _live_sessions(
    db: AsyncSession, device_id: uuid.UUID, *, at: datetime | None = None
) -> list[ScreenSession]:
    """Sessions reellement vivantes ; les perimees sont fermees au passage."""
    at = at or clock_now()
    rows = list(
        (
            await db.execute(
                select(ScreenSession).where(
                    ScreenSession.device_id == device_id,
                    ScreenSession.state.in_([ScreenSessionState.ACTIVE, ScreenSessionState.PAUSED]),
                )
            )
        ).scalars()
    )
    live: list[ScreenSession] = []
    for session in rows:
        if expire_if_due(session, at):
            await _log(db, session, ScreenEventType.EXPIRE, meta={"reason": session.end_reason})
        else:
            live.append(session)
    return live


async def active_session_for_device(
    db: AsyncSession, device_id: uuid.UUID, *, at: datetime | None = None
) -> ScreenSession | None:
    sessions = await _live_sessions(db, device_id, at=at)
    return sessions[0] if sessions else None


async def active_session_for_child(
    db: AsyncSession, child_id: uuid.UUID, *, at: datetime | None = None
) -> ScreenSession | None:
    """Meme regle, cote tableau de bord parental."""
    at = at or clock_now()
    rows = list(
        (
            await db.execute(
                select(ScreenSession)
                .where(
                    ScreenSession.child_id == child_id,
                    ScreenSession.state.in_([ScreenSessionState.ACTIVE, ScreenSessionState.PAUSED]),
                )
                .order_by(ScreenSession.started_at.desc())
            )
        ).scalars()
    )
    for session in rows:
        if not expire_if_due(session, at):
            return session
    return None


async def _log(
    db: AsyncSession,
    session: ScreenSession,
    event_type: ScreenEventType,
    *,
    monotonic_ms: int = 0,
    device_wall_ms: int | None = None,
    delta_ms: int = 0,
    skew_ms: int = 0,
    screen_on: bool = True,
    meta: dict[str, Any] | None = None,
) -> ScreenEvent:
    event = ScreenEvent(
        session_id=session.id,
        type=event_type,
        monotonic_ms=monotonic_ms,
        device_wall_ms=device_wall_ms,
        delta_ms=delta_ms,
        skew_ms=skew_ms,
        screen_on=screen_on,
        meta=meta or {},
    )
    db.add(event)
    return event


# ---------------------------------------------------------------------------
# Battement de coeur
# ---------------------------------------------------------------------------


async def heartbeat(
    db: AsyncSession,
    session: ScreenSession,
    *,
    monotonic_ms: int,
    device_wall_ms: int | None = None,
    screen_on: bool = True,
    boot_id: str | None = None,
    at: datetime | None = None,
) -> HeartbeatResult:
    """Consomme le temps ecoule depuis le dernier battement et arbitre la suite."""
    at = at or clock_now()
    anomalies: list[str] = []

    if not session.is_live:
        return HeartbeatResult(
            session=session,
            consumed_delta_ms=0,
            remaining_ms=0,
            state=session.state,
            anomalies=["session_closed"],
            should_lock=True,
        )

    server_elapsed_ms = max(
        0, int(((at - (session.last_heartbeat_at or session.started_at)).total_seconds()) * 1000)
    )

    # Redemarrage : l'horloge monotone repart de zero, la base doit etre reinitialisee.
    if boot_id and session.device_boot_id and boot_id != session.device_boot_id:
        anomalies.append("reboot_detected")
        session.device_boot_id = boot_id
        session.last_monotonic_ms = monotonic_ms
        # Hors ligne pendant un redemarrage : on impute le temps serveur ecoule,
        # faute de mieux, mais seulement si l'ecran etait annonce allume.
        session.offline_ms += server_elapsed_ms if screen_on else 0

    raw_delta = monotonic_ms - session.last_monotonic_ms
    if raw_delta < 0:
        anomalies.append("monotonic_rollback")
        session.anomaly_count += 1
        session.integrity_score = max(0.0, session.integrity_score - TAMPER_PENALTY)
        raw_delta = server_elapsed_ms if screen_on else 0
        await _log(db, session, ScreenEventType.TAMPER, meta={"reason": "monotonic_rollback"})

    # Garde-fou : on ne peut pas consommer plus de temps qu'il n'en est passe.
    allowance = int(server_elapsed_ms * 1.05) + 2_000
    if raw_delta > allowance:
        anomalies.append("delta_overflow")
        raw_delta = allowance

    delta_ms = raw_delta if screen_on else 0

    skew_ms = 0
    if device_wall_ms is not None:
        verdict = assess_device_clock(
            device_wall_ms=device_wall_ms,
            server_time=at,
            tolerance_ms=settings.max_clock_skew_ms,
        )
        skew_ms = verdict.skew_ms
        if verdict.tampered:
            anomalies.append("clock_skew")
            session.anomaly_count += 1
            session.integrity_score = max(0.0, session.integrity_score - TAMPER_PENALTY)
            await _log(
                db,
                session,
                ScreenEventType.TAMPER,
                skew_ms=skew_ms,
                meta={"reason": "clock_skew", "detail": verdict.reason},
            )

    session.consumed_ms = min(session.total_ms, session.consumed_ms + delta_ms)
    session.last_monotonic_ms = monotonic_ms
    session.last_heartbeat_at = at

    if screen_on and session.state == ScreenSessionState.PAUSED:
        session.state = ScreenSessionState.ACTIVE
        session.paused_at = None
        await _log(db, session, ScreenEventType.RESUME, monotonic_ms=monotonic_ms)
    elif not screen_on and session.state == ScreenSessionState.ACTIVE:
        session.state = ScreenSessionState.PAUSED
        session.paused_at = at
        await _log(db, session, ScreenEventType.PAUSE, monotonic_ms=monotonic_ms)

    await _log(
        db,
        session,
        ScreenEventType.HEARTBEAT,
        monotonic_ms=monotonic_ms,
        device_wall_ms=device_wall_ms,
        delta_ms=delta_ms,
        skew_ms=skew_ms,
        screen_on=screen_on,
        meta={"anomalies": anomalies} if anomalies else None,
    )

    should_lock = False
    if session.remaining_ms <= 0:
        await _close(db, session, ScreenSessionState.EXPIRED, "time_exhausted", at)
        should_lock = True
    elif at >= session.wall_deadline_at:
        anomalies.append("wall_deadline")
        await _close(db, session, ScreenSessionState.EXPIRED, "wall_deadline", at)
        should_lock = True

    return HeartbeatResult(
        session=session,
        consumed_delta_ms=delta_ms,
        remaining_ms=session.remaining_ms,
        state=session.state,
        anomalies=anomalies,
        should_lock=should_lock,
    )


async def _close(
    db: AsyncSession,
    session: ScreenSession,
    state: ScreenSessionState,
    reason: str,
    at: datetime,
) -> None:
    session.state = state
    session.ended_at = at
    session.end_reason = reason
    await _log(
        db,
        session,
        ScreenEventType.EXPIRE if state == ScreenSessionState.EXPIRED else ScreenEventType.END,
        meta={"reason": reason},
    )


# ---------------------------------------------------------------------------
# Actions explicites
# ---------------------------------------------------------------------------


async def pause_session(
    db: AsyncSession, session: ScreenSession, *, at: datetime | None = None
) -> ScreenSession:
    at = at or clock_now()
    if session.state != ScreenSessionState.ACTIVE:
        return session
    session.state = ScreenSessionState.PAUSED
    session.paused_at = at
    await _log(db, session, ScreenEventType.PAUSE)
    return session


async def resume_session(
    db: AsyncSession,
    session: ScreenSession,
    *,
    monotonic_ms: int | None = None,
    at: datetime | None = None,
) -> ScreenSession:
    at = at or clock_now()
    if session.state != ScreenSessionState.PAUSED:
        return session
    if at >= session.wall_deadline_at:
        await _close(db, session, ScreenSessionState.EXPIRED, "wall_deadline", at)
        return session
    session.state = ScreenSessionState.ACTIVE
    session.paused_at = None
    session.last_heartbeat_at = at
    if monotonic_ms is not None:
        session.last_monotonic_ms = monotonic_ms
    await _log(db, session, ScreenEventType.RESUME, monotonic_ms=monotonic_ms or 0)
    return session


async def end_session(
    db: AsyncSession,
    session: ScreenSession,
    *,
    reason: str = "manual",
    at: datetime | None = None,
) -> ScreenSession:
    at = at or clock_now()
    if not session.is_live:
        return session
    state = (
        ScreenSessionState.REVOKED
        if reason in {"revoked", "parent_stop"}
        else ScreenSessionState.ENDED
    )
    await _close(db, session, state, reason, at)
    return session


async def extend_session(
    db: AsyncSession,
    session: ScreenSession,
    *,
    minutes: int,
    at: datetime | None = None,
    source: str = "parent_bonus",
) -> ScreenSession:
    """Rallonge parentale ou conversion d'XP sur une session deja ouverte."""
    at = at or clock_now()
    if not session.is_live:
        raise ConflictError("Cette session est terminee : il faut un nouveau code.")
    if minutes <= 0:
        raise ConflictError("La rallonge doit etre positive.")
    session.bonus_ms += minutes * 60_000
    session.wall_deadline_at += timedelta(minutes=minutes * settings.session_wall_stretch_factor)
    await _log(db, session, ScreenEventType.EXTEND, meta={"minutes": minutes, "source": source})
    return session


async def reconcile_offline(
    db: AsyncSession,
    session: ScreenSession,
    *,
    reported_active_ms: int,
    at: datetime | None = None,
) -> ScreenSession:
    """Rattrapage apres une periode sans reseau.

    L'appareil declare le temps reellement consomme hors ligne. On le retient,
    borne par le temps ecoule cote serveur : impossible de "rendre" du temps en
    sous-declarant, ni d'en gagner en sur-declarant.
    """
    at = at or clock_now()
    server_gap_ms = max(
        0, int((at - (session.last_heartbeat_at or session.started_at)).total_seconds() * 1000)
    )
    accepted = max(0, min(reported_active_ms, server_gap_ms))
    if accepted < reported_active_ms:
        session.anomaly_count += 1
    session.offline_ms += accepted
    session.consumed_ms = min(session.total_ms, session.consumed_ms + accepted)
    session.last_heartbeat_at = at
    await _log(
        db,
        session,
        ScreenEventType.OFFLINE_GAP,
        delta_ms=accepted,
        meta={"reported_ms": reported_active_ms, "server_gap_ms": server_gap_ms},
    )
    if session.remaining_ms <= 0:
        await _close(db, session, ScreenSessionState.EXPIRED, "time_exhausted", at)
    return session


async def expire_stale_sessions(db: AsyncSession, *, at: datetime | None = None) -> int:
    """Tache de fond : ferme les sessions dont le butoir absolu est depasse."""
    at = at or clock_now()
    stale = list(
        (
            await db.execute(
                select(ScreenSession).where(
                    ScreenSession.state.in_([ScreenSessionState.ACTIVE, ScreenSessionState.PAUSED]),
                    ScreenSession.wall_deadline_at <= at,
                )
            )
        ).scalars()
    )
    for session in stale:
        await _close(db, session, ScreenSessionState.EXPIRED, "wall_deadline", at)
    return len(stale)


# ---------------------------------------------------------------------------
# Quotas
# ---------------------------------------------------------------------------


async def minutes_granted_today(
    db: AsyncSession, child_id: uuid.UUID, *, at: datetime | None = None
) -> int:
    """Total de minutes accordees aujourd'hui (base du plafond quotidien)."""
    at = at or clock_now()
    start = at.replace(hour=0, minute=0, second=0, microsecond=0)
    total_ms = await db.scalar(
        select(func.coalesce(func.sum(ScreenSession.granted_ms + ScreenSession.bonus_ms), 0)).where(
            ScreenSession.child_id == child_id, ScreenSession.started_at >= start
        )
    )
    return int((total_ms or 0) // 60_000)


async def get_session_or_404(db: AsyncSession, session_id: uuid.UUID) -> ScreenSession:
    session = await db.get(ScreenSession, session_id)
    if session is None:
        raise NotFoundError("Session de temps d'ecran introuvable.")
    return session
