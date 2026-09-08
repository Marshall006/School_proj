"""Resolution des regles applicables a un enfant, a un instant donne.

Ordre de precedence : profil de l'enfant pour la periode courante > profil du
foyer pour cette periode > valeurs par defaut du produit.

La periode (scolaire / week-end / vacances) est deduite du calendrier declare
par le parent. C'est elle qui bascule le mode de deverrouillage :
periode scolaire -> le parent peut debloquer directement (devoirs faits) ;
vacances -> l'appareil ne s'ouvre qu'en reussissant une evaluation.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import now as clock_now
from app.core.config import settings
from app.models.enums import PeriodType
from app.models.family import Child, Family
from app.models.policy import CalendarPeriod, PolicyProfile


@dataclass(frozen=True, slots=True)
class EffectivePolicy:
    """Vue figee et complete des regles. C'est ce qu'on archive dans un examen."""

    period_type: PeriodType
    source: str  # "child" | "family" | "default"
    profile_id: uuid.UUID | None
    timezone: str

    pass_score_pct: float
    question_count: int
    time_limit_minutes: int
    difficulty_bias: float

    reward_minutes: int
    daily_cap_minutes: int
    max_attempts_per_day: int
    allow_parent_direct_unlock: bool
    allow_assessment_unlock: bool

    cooldown_minutes: int
    cooldown_escalation: float
    review_required_before_retry: bool

    minutes_per_100_xp: int
    xp_daily_bonus_cap_minutes: int
    practice_xp_multiplier: float

    curfew_start: str | None
    curfew_end: str | None
    subject_codes: list[str] = field(default_factory=list)
    extras: dict[str, Any] = field(default_factory=dict)

    @property
    def pass_score_out_of_20(self) -> float:
        return round(self.pass_score_pct * 0.2, 2)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["period_type"] = self.period_type.value
        data["profile_id"] = str(self.profile_id) if self.profile_id else None
        data["pass_score_out_of_20"] = self.pass_score_out_of_20
        return data


def _zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


def local_now(timezone: str, at: datetime | None = None) -> datetime:
    return (at or clock_now()).astimezone(_zone(timezone))


# ---------------------------------------------------------------------------
# Periode calendaire
# ---------------------------------------------------------------------------


def resolve_period_type(
    periods: list[CalendarPeriod], local_date: date, *, weekend_profile: bool = True
) -> PeriodType:
    """Une plage declaree l'emporte ; sinon samedi/dimanche -> week-end."""
    for period in periods:
        if period.start_date <= local_date <= period.end_date:
            return period.period_type
    if weekend_profile and local_date.weekday() >= 5:
        return PeriodType.WEEKEND
    return PeriodType.SCHOOL


async def get_period_type(
    db: AsyncSession, family_id: uuid.UUID, timezone: str, at: datetime | None = None
) -> PeriodType:
    periods = list(
        (
            await db.execute(select(CalendarPeriod).where(CalendarPeriod.family_id == family_id))
        ).scalars()
    )
    return resolve_period_type(periods, local_now(timezone, at).date())


# ---------------------------------------------------------------------------
# Profil applicable
# ---------------------------------------------------------------------------


def _default_policy(period_type: PeriodType, timezone: str) -> EffectivePolicy:
    """Reglages livres par defaut, differencies selon la periode."""
    holiday = period_type == PeriodType.HOLIDAY
    weekend = period_type == PeriodType.WEEKEND
    return EffectivePolicy(
        period_type=period_type,
        source="default",
        profile_id=None,
        timezone=timezone,
        pass_score_pct=settings.default_pass_score_pct,
        question_count=settings.default_question_count,
        time_limit_minutes=20,
        difficulty_bias=0.0,
        reward_minutes=settings.default_reward_minutes if not holiday else 120,
        daily_cap_minutes=settings.default_daily_cap_minutes if not holiday else 360,
        max_attempts_per_day=settings.default_max_attempts_per_day,
        # En vacances, plus de devoirs a valider : le deverrouillage direct est coupe
        # par defaut, l'evaluation devient le seul chemin.
        allow_parent_direct_unlock=not holiday,
        allow_assessment_unlock=True,
        cooldown_minutes=settings.default_cooldown_minutes,
        cooldown_escalation=1.0,
        review_required_before_retry=True,
        minutes_per_100_xp=settings.default_minutes_per_100_xp,
        xp_daily_bonus_cap_minutes=settings.default_xp_daily_bonus_cap_minutes,
        practice_xp_multiplier=1.5 if (holiday or weekend) else 1.0,
        curfew_start="21:00" if not (holiday or weekend) else "22:00",
        curfew_end="07:00",
        subject_codes=[],
        extras={},
    )


def _from_profile(
    profile: PolicyProfile, period_type: PeriodType, timezone: str
) -> EffectivePolicy:
    return EffectivePolicy(
        period_type=period_type,
        source="child" if profile.child_id else "family",
        profile_id=profile.id,
        timezone=timezone,
        pass_score_pct=profile.pass_score_pct,
        question_count=profile.question_count,
        time_limit_minutes=profile.time_limit_minutes,
        difficulty_bias=profile.difficulty_bias,
        reward_minutes=profile.reward_minutes,
        daily_cap_minutes=profile.daily_cap_minutes,
        max_attempts_per_day=profile.max_attempts_per_day,
        allow_parent_direct_unlock=profile.allow_parent_direct_unlock,
        allow_assessment_unlock=profile.allow_assessment_unlock,
        cooldown_minutes=profile.cooldown_minutes,
        cooldown_escalation=profile.cooldown_escalation,
        review_required_before_retry=profile.review_required_before_retry,
        minutes_per_100_xp=profile.minutes_per_100_xp,
        xp_daily_bonus_cap_minutes=profile.xp_daily_bonus_cap_minutes,
        practice_xp_multiplier=profile.practice_xp_multiplier,
        curfew_start=profile.curfew_start,
        curfew_end=profile.curfew_end,
        subject_codes=list(profile.subject_codes or []),
        extras=dict(profile.extras or {}),
    )


async def resolve_policy(
    db: AsyncSession, child: Child, at: datetime | None = None
) -> EffectivePolicy:
    """Regles effectives pour cet enfant, maintenant."""
    family = await db.get(Family, child.family_id)
    timezone = family.timezone if family else settings.server_timezone
    period_type = await get_period_type(db, child.family_id, timezone, at)

    profiles = list(
        (
            await db.execute(
                select(PolicyProfile).where(
                    PolicyProfile.family_id == child.family_id,
                    PolicyProfile.period_type == period_type,
                    PolicyProfile.is_active.is_(True),
                )
            )
        ).scalars()
    )
    for profile in profiles:
        if profile.child_id == child.id:
            return _from_profile(profile, period_type, timezone)
    for profile in profiles:
        if profile.child_id is None:
            return _from_profile(profile, period_type, timezone)
    return _default_policy(period_type, timezone)


# ---------------------------------------------------------------------------
# Couvre-feu
# ---------------------------------------------------------------------------


def _parse_hhmm(value: str | None) -> time | None:
    if not value:
        return None
    try:
        hour, _, minute = value.partition(":")
        return time(int(hour), int(minute or 0))
    except (ValueError, TypeError):
        return None


def is_within_curfew(policy: EffectivePolicy, at: datetime | None = None) -> bool:
    """Vrai si l'heure locale tombe dans la plage interdite (gere le passage a minuit)."""
    start, end = _parse_hhmm(policy.curfew_start), _parse_hhmm(policy.curfew_end)
    if start is None or end is None:
        return False
    current = local_now(policy.timezone, at).time()
    if start == end:
        return False
    if start < end:  # ex. 13:00 -> 15:00
        return start <= current < end
    return current >= start or current < end  # ex. 21:00 -> 07:00


def next_curfew_end(policy: EffectivePolicy, at: datetime | None = None) -> datetime | None:
    """Instant (UTC) auquel le couvre-feu se leve."""
    end = _parse_hhmm(policy.curfew_end)
    if end is None or not is_within_curfew(policy, at):
        return None
    local = local_now(policy.timezone, at)
    candidate = local.replace(hour=end.hour, minute=end.minute, second=0, microsecond=0)
    if candidate <= local:
        candidate += timedelta(days=1)
    return candidate.astimezone(clock_now().tzinfo)
