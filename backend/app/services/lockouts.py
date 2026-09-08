"""Temps de carence : la pause obligatoire qui rend l'echec formateur.

En cas d'echec a l'evaluation, l'enfant recoit la correction detaillee mais pas
le code. Un delai s'enclenche (2 h par defaut, parametrable, avec escalade
possible a chaque nouvel echec du jour) pendant lequel il est cense reviser.
On lui affiche precisement *quelles notions* revoir.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import now as clock_now
from app.models.access import Lockout
from app.models.enums import LockoutReason


async def active_lockout(
    db: AsyncSession,
    child_id: uuid.UUID,
    *,
    at: datetime | None = None,
    reasons: list[LockoutReason] | None = None,
) -> Lockout | None:
    at = at or clock_now()
    query = select(Lockout).where(
        Lockout.child_id == child_id,
        Lockout.until > at,
        Lockout.released_at.is_(None),
    )
    if reasons:
        query = query.where(Lockout.reason.in_(reasons))
    return (await db.execute(query.order_by(Lockout.until.desc()).limit(1))).scalar_one_or_none()


async def open_lockout(
    db: AsyncSession,
    *,
    child_id: uuid.UUID,
    reason: LockoutReason,
    minutes: int,
    message: str | None = None,
    source_assessment_id: uuid.UUID | None = None,
    review_topics: list[dict[str, Any]] | None = None,
    at: datetime | None = None,
) -> Lockout:
    at = at or clock_now()
    lockout = Lockout(
        child_id=child_id,
        reason=reason,
        started_at=at,
        until=at + timedelta(minutes=max(1, minutes)),
        message=message,
        source_assessment_id=source_assessment_id,
        review_topics=review_topics or [],
    )
    db.add(lockout)
    await db.flush()
    return lockout


async def release_lockout(
    db: AsyncSession,
    lockout: Lockout,
    *,
    parent_id: uuid.UUID | None = None,
    at: datetime | None = None,
) -> Lockout:
    """Le parent garde toujours le dernier mot : il peut lever la carence."""
    lockout.released_at = at or clock_now()
    lockout.released_by_parent_id = parent_id
    return lockout


def describe(lockout: Lockout, at: datetime | None = None) -> dict[str, Any]:
    at = at or clock_now()
    remaining = max(0, int((lockout.until - at).total_seconds()))
    return {
        "id": str(lockout.id),
        "reason": lockout.reason.value,
        "until": lockout.until.isoformat(),
        "remaining_seconds": remaining,
        "remaining_minutes": (remaining + 59) // 60,
        "message": lockout.message,
        "review_topics": lockout.review_topics or [],
    }


def escalated_minutes(base_minutes: int, failures_today: int, escalation: float) -> int:
    """2 h, puis 2 h x escalade au 2e echec, etc. (escalade = 1.0 -> pas d'escalade)."""
    if failures_today <= 1 or escalation <= 1.0:
        return base_minutes
    return int(round(base_minutes * (escalation ** (failures_today - 1))))
