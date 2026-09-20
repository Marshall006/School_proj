"""Metriques du tableau de bord parental.

Le parent veut trois choses, dans cet ordre :

1. **Ou en est mon enfant maintenant ?** (verrouille ou non, temps restant,
   carence en cours, prochaine tentative possible) ;
2. **Est-ce que le niveau tient ?** (taux de reussite par matiere, evolution,
   notions fragiles) ;
3. **Est-ce que le systeme est contourne ?** (anomalies d'horloge, codes
   errones en rafale, sessions hors ligne).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import now as clock_now
from app.models.access import Lockout, ScreenSession, UnlockCode
from app.models.assessment import Assessment, AssessmentItem
from app.models.content import Subject, Topic
from app.models.device import Device
from app.models.enums import AssessmentStatus, ScreenSessionState
from app.models.family import Child
from app.models.progress import Mastery, XPLedgerEntry
from app.services import adaptive, lockouts, screen_time


async def child_status(
    db: AsyncSession, child: Child, policy: Any, *, at: datetime | None = None
) -> dict[str, Any]:
    """Etat instantane : c'est la premiere carte du tableau de bord."""
    at = at or clock_now()
    session = await screen_time.active_session_for_child(db, child.id, at=at)

    lockout = await lockouts.active_lockout(db, child.id, at=at)
    used_today = await screen_time.minutes_granted_today(db, child.id, at=at)
    pending = list(
        (
            await db.execute(
                select(UnlockCode).where(
                    UnlockCode.child_id == child.id,
                    UnlockCode.status == "issued",
                    UnlockCode.expires_at > at,
                )
            )
        ).scalars()
    )

    return {
        "child_id": str(child.id),
        "display_name": child.display_name,
        "grade_code": child.grade_code,
        "xp_balance": child.xp_balance,
        "streak_days": child.streak_days,
        "screen_state": (
            "unlocked"
            if session and session.state == ScreenSessionState.ACTIVE
            else "paused"
            if session
            else "locked"
        ),
        "session": (
            {
                "id": str(session.id),
                "state": session.state.value,
                "remaining_ms": session.remaining_ms,
                "remaining_minutes": session.remaining_ms // 60000,
                "granted_minutes": session.total_ms // 60000,
                "started_at": session.started_at.isoformat(),
                "wall_deadline_at": session.wall_deadline_at.isoformat(),
                "integrity_score": round(session.integrity_score, 2),
                "anomaly_count": session.anomaly_count,
            }
            if session
            else None
        ),
        "lockout": lockouts.describe(lockout, at) if lockout else None,
        "screen_time_today": {
            "granted_minutes": used_today,
            "cap_minutes": policy.daily_cap_minutes,
            "remaining_minutes": max(0, policy.daily_cap_minutes - used_today),
        },
        "pending_codes": len(pending),
        "period_type": policy.period_type.value,
        "unlock_paths": {
            "parent_direct": policy.allow_parent_direct_unlock,
            "assessment": policy.allow_assessment_unlock,
        },
    }


async def subject_performance(
    db: AsyncSession, child_id: uuid.UUID, *, days: int = 30, at: datetime | None = None
) -> list[dict[str, Any]]:
    """Taux de reussite par matiere : la metrique que reclament les parents."""
    at = at or clock_now()
    since = at - timedelta(days=days)
    rows = (
        await db.execute(
            select(
                AssessmentItem.subject_code,
                func.count(AssessmentItem.id),
                func.sum(case((AssessmentItem.is_correct.is_(True), 1), else_=0)),
                func.avg(AssessmentItem.score),
                func.avg(AssessmentItem.time_spent_ms),
            )
            .join(Assessment, Assessment.id == AssessmentItem.assessment_id)
            .where(
                Assessment.child_id == child_id,
                Assessment.created_at >= since,
                AssessmentItem.is_correct.is_not(None),
            )
            .group_by(AssessmentItem.subject_code)
        )
    ).all()

    labels = {row.code: row.name for row in (await db.execute(select(Subject))).scalars()}
    result = []
    for code, total, correct, avg_score, avg_ms in rows:
        total = int(total or 0)
        result.append(
            {
                "subject_code": code,
                "subject_name": labels.get(code, code),
                "answered": total,
                "correct": int(correct or 0),
                "success_rate": round((correct or 0) / total, 3) if total else None,
                "avg_score": round(float(avg_score or 0), 3),
                "avg_seconds": round(float(avg_ms or 0) / 1000, 1),
            }
        )
    return sorted(result, key=lambda r: r["success_rate"] or 0)


async def mastery_overview(
    db: AsyncSession, child_id: uuid.UUID, *, limit: int = 6
) -> dict[str, Any]:
    """Repartition des notions par palier + les lacunes prioritaires."""
    rows = list((await db.execute(select(Mastery).where(Mastery.child_id == child_id))).scalars())
    bands: dict[str, int] = {}
    for row in rows:
        bands[row.band.value] = bands.get(row.band.value, 0) + 1

    states = [
        adaptive.MasteryState(
            topic_id=row.topic_id,
            subject_code=row.subject_code,
            ability=row.ability,
            ewma=row.ewma,
            attempts=row.attempts,
            correct=row.correct,
            streak=row.streak,
            next_review_at=row.next_review_at,
            last_seen_at=row.last_seen_at,
        )
        for row in rows
    ]
    gaps = adaptive.identify_gaps(states, limit=limit)

    topic_ids = [uuid.UUID(g["topic_id"]) for g in gaps]
    names = {}
    if topic_ids:
        names = {
            str(t.id): t.name
            for t in (await db.execute(select(Topic).where(Topic.id.in_(topic_ids)))).scalars()
        }
    for gap in gaps:
        gap["topic_name"] = names.get(gap["topic_id"], "Notion")

    return {
        "topics_tracked": len(rows),
        "bands": bands,
        "gaps": gaps,
        "due_for_review": sum(1 for s in states if s.is_due()),
    }


async def assessment_history(
    db: AsyncSession, child_id: uuid.UUID, *, limit: int = 10
) -> list[dict[str, Any]]:
    rows = list(
        (
            await db.execute(
                select(Assessment)
                .where(
                    Assessment.child_id == child_id,
                    Assessment.status.in_([AssessmentStatus.GRADED, AssessmentStatus.NEEDS_REVIEW]),
                )
                .order_by(Assessment.created_at.desc())
                .limit(limit)
            )
        ).scalars()
    )
    return [
        {
            "id": str(row.id),
            "kind": row.kind.value,
            "status": row.status.value,
            "score_out_of_20": row.score_out_of_20,
            "passed": row.passed,
            "question_count": row.question_count,
            "reward_minutes": row.reward_minutes,
            "xp_earned": row.xp_earned,
            "duration_seconds": row.duration_seconds,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]


async def screen_time_trend(
    db: AsyncSession, child_id: uuid.UUID, *, days: int = 14, at: datetime | None = None
) -> list[dict[str, Any]]:
    """Minutes reellement consommees, jour par jour."""
    at = at or clock_now()
    since = (at - timedelta(days=days - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
    rows = list(
        (
            await db.execute(
                select(ScreenSession).where(
                    ScreenSession.child_id == child_id, ScreenSession.started_at >= since
                )
            )
        ).scalars()
    )
    buckets: dict[str, dict[str, int]] = {}
    for offset in range(days):
        key = (since + timedelta(days=offset)).date().isoformat()
        buckets[key] = {"granted_minutes": 0, "consumed_minutes": 0, "sessions": 0}
    for row in rows:
        key = row.started_at.date().isoformat()
        if key not in buckets:
            continue
        buckets[key]["granted_minutes"] += row.total_ms // 60000
        buckets[key]["consumed_minutes"] += row.consumed_ms // 60000
        buckets[key]["sessions"] += 1
    return [{"date": key, **value} for key, value in sorted(buckets.items())]


async def integrity_alerts(
    db: AsyncSession, child_id: uuid.UUID, *, days: int = 30, at: datetime | None = None
) -> list[dict[str, Any]]:
    """Signaux de contournement, formules en clair pour un parent non technicien."""
    at = at or clock_now()
    since = at - timedelta(days=days)
    alerts: list[dict[str, Any]] = []

    suspicious = list(
        (
            await db.execute(
                select(ScreenSession).where(
                    ScreenSession.child_id == child_id,
                    ScreenSession.started_at >= since,
                    ScreenSession.anomaly_count > 0,
                )
            )
        ).scalars()
    )
    for session in suspicious:
        alerts.append(
            {
                "severity": "warning" if session.integrity_score > 0.5 else "critical",
                "type": "session_anomaly",
                "message": (
                    f"{session.anomaly_count} incoherence(s) detectee(s) pendant une session "
                    f"du {session.started_at.date().isoformat()} "
                    "(horloge modifiee ou redemarrage suspect)."
                ),
                "session_id": str(session.id),
                "at": session.started_at.isoformat(),
            }
        )

    devices = list((await db.execute(select(Device).where(Device.child_id == child_id))).scalars())
    for device in devices:
        if device.failed_code_attempts >= 3:
            alerts.append(
                {
                    "severity": "warning",
                    "type": "code_bruteforce",
                    "message": (
                        f'{device.failed_code_attempts} codes errones saisis sur "{device.name}".'
                    ),
                    "device_id": str(device.id),
                    "at": (device.last_seen_at or at).isoformat(),
                }
            )
        if abs(device.clock_skew_ms) > 300_000:
            alerts.append(
                {
                    "severity": "critical",
                    "type": "clock_skew",
                    "message": (
                        f"L'horloge de \"{device.name}\" s'ecarte de "
                        f"{abs(device.clock_skew_ms) // 60000} minutes de l'heure reelle."
                    ),
                    "device_id": str(device.id),
                    "at": (device.last_seen_at or at).isoformat(),
                }
            )

    offline = list(
        (
            await db.execute(
                select(UnlockCode).where(
                    UnlockCode.child_id == child_id,
                    UnlockCode.consumed_offline.is_(True),
                    UnlockCode.created_at >= since,
                )
            )
        ).scalars()
    )
    if offline:
        alerts.append(
            {
                "severity": "info",
                "type": "offline_usage",
                "message": (
                    f"{len(offline)} code(s) utilisé(s) hors ligne : le temps a été "
                    "reconcilie a la reconnexion."
                ),
                "at": at.isoformat(),
            }
        )
    return sorted(alerts, key=lambda a: a["at"], reverse=True)[:20]


async def xp_timeline(
    db: AsyncSession, child_id: uuid.UUID, *, limit: int = 15
) -> list[dict[str, Any]]:
    rows = list(
        (
            await db.execute(
                select(XPLedgerEntry)
                .where(XPLedgerEntry.child_id == child_id)
                .order_by(XPLedgerEntry.created_at.desc())
                .limit(limit)
            )
        ).scalars()
    )
    return [
        {
            "delta": row.delta,
            "reason": row.reason.value,
            "label": row.label,
            "balance_after": row.balance_after,
            "at": row.created_at.isoformat(),
        }
        for row in rows
    ]


async def build_dashboard(
    db: AsyncSession, child: Child, policy: Any, *, at: datetime | None = None
) -> dict[str, Any]:
    """Assemble le tableau de bord complet d'un enfant."""
    at = at or clock_now()
    graded = await db.scalar(
        select(func.count(Assessment.id)).where(
            Assessment.child_id == child.id, Assessment.passed.is_not(None)
        )
    )
    passed = await db.scalar(
        select(func.count(Assessment.id)).where(
            Assessment.child_id == child.id, Assessment.passed.is_(True)
        )
    )
    return {
        "status": await child_status(db, child, policy, at=at),
        "subjects": await subject_performance(db, child.id, at=at),
        "mastery": await mastery_overview(db, child.id),
        "recent_assessments": await assessment_history(db, child.id),
        "screen_time_trend": await screen_time_trend(db, child.id, at=at),
        "alerts": await integrity_alerts(db, child.id, at=at),
        "xp_timeline": await xp_timeline(db, child.id),
        "totals": {
            "assessments_graded": int(graded or 0),
            "assessments_passed": int(passed or 0),
            "pass_rate": round((passed or 0) / graded, 3) if graded else None,
            "xp_lifetime": child.xp_lifetime,
        },
        "generated_at": at.isoformat(),
    }


async def family_overview(
    db: AsyncSession, family_id: uuid.UUID, *, at: datetime | None = None
) -> dict[str, Any]:
    """Vue d'ensemble du foyer, tous enfants confondus."""
    at = at or clock_now()
    children = list((await db.execute(select(Child).where(Child.family_id == family_id))).scalars())
    # Une session dont le butoir est depasse n'est plus vivante, meme si aucun
    # battement n'est venu la fermer : sans cette condition, le foyer affiche
    # « 1 session en cours » alors que toutes les tablettes sont verrouillees.
    active_sessions = int(
        await db.scalar(
            select(func.count(ScreenSession.id))
            .join(Child, Child.id == ScreenSession.child_id)
            .where(
                Child.family_id == family_id,
                ScreenSession.state == ScreenSessionState.ACTIVE,
                ScreenSession.wall_deadline_at > at,
            )
        )
        or 0
    )
    open_lockouts = int(
        await db.scalar(
            select(func.count(Lockout.id))
            .join(Child, Child.id == Lockout.child_id)
            .where(
                Child.family_id == family_id,
                Lockout.until > at,
                Lockout.released_at.is_(None),
            )
        )
        or 0
    )
    return {
        "children_count": len(children),
        "active_sessions": active_sessions,
        "open_lockouts": open_lockouts,
        "total_xp": sum(c.xp_balance for c in children),
        "generated_at": at.isoformat(),
    }
