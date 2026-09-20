"""Points d'experience : gagner, plafonner, convertir en minutes d'ecran.

Regles concues pour recompenser l'effort **sincere** :

- une bonne reponse rapporte selon la difficulte, pas selon la quantite ;
- le rendement decroit au fil de la journee (on ne "farme" pas des QCM faciles
  pendant deux heures pour ouvrir la console) ;
- franchir un palier de maitrise sur une notion fragile rapporte gros : c'est
  exactement le comportement que le produit veut encourager ;
- la conversion en minutes est plafonnee par jour et arrondie au pas de
  5 minutes impose par le protocole de code.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import now as clock_now
from app.core.unlock_protocol import DURATION_STEP_MINUTES
from app.models.enums import XPReason
from app.models.family import Child
from app.models.progress import XPLedgerEntry

XP_PER_CORRECT = 10.0
DIFFICULTY_MULTIPLIER: dict[int, float] = {1: 0.6, 2: 0.8, 3: 1.0, 4: 1.3, 5: 1.6}
PASS_BONUS = 50
PERFECT_BONUS = 50
WEAKNESS_CLEARED_BONUS = 30
STREAK_XP_PER_DAY = 10
STREAK_MAX_BONUS = 50

#: Rendement decroissant : (XP deja gagnes aujourd'hui, coefficient applique).
DIMINISHING_TIERS: tuple[tuple[int, float], ...] = ((300, 1.0), (600, 0.5), (10**9, 0.25))


@dataclass(slots=True)
class XPGrant:
    """Detail d'un gain, pour l'afficher a l'enfant ligne par ligne."""

    amount: int
    reason: XPReason
    label: str
    meta: dict[str, Any] = field(default_factory=dict)


def base_xp_for_answer(score: float, difficulty: int) -> float:
    """XP bruts d'une reponse (credit partiel proportionnel)."""
    score = min(max(score, 0.0), 1.0)
    return XP_PER_CORRECT * DIFFICULTY_MULTIPLIER.get(int(difficulty), 1.0) * score


def diminishing_factor(xp_already_today: int) -> float:
    for threshold, factor in DIMINISHING_TIERS:
        if xp_already_today < threshold:
            return factor
    return DIMINISHING_TIERS[-1][1]


def plural(count: int) -> str:
    """Marque du pluriel, pour que les libelles restent lisibles au singulier."""
    return "s" if count > 1 else ""


def apply_diminishing(raw_xp: float, xp_already_today: int) -> int:
    """Applique le rendement decroissant palier par palier."""
    remaining = raw_xp
    earned = 0.0
    cursor = xp_already_today
    previous_threshold = 0
    for threshold, factor in DIMINISHING_TIERS:
        if cursor >= threshold:
            previous_threshold = threshold
            continue
        room = threshold - max(cursor, previous_threshold)
        take = min(remaining, room / factor if factor else remaining)
        earned += take * factor
        remaining -= take
        cursor += take * factor
        previous_threshold = threshold
        if remaining <= 0:
            break
    return int(round(earned))


def compute_assessment_xp(
    *,
    item_scores: list[tuple[float, int]],  # (score 0..1, difficulte)
    passed: bool,
    score_pct: float,
    cleared_weaknesses: int = 0,
    streak_days: int = 0,
    practice_multiplier: float = 1.0,
    xp_already_today: int = 0,
) -> tuple[int, list[XPGrant]]:
    """Detaille les XP d'une evaluation terminee."""
    grants: list[XPGrant] = []

    raw_answers = sum(base_xp_for_answer(score, diff) for score, diff in item_scores)
    raw_answers *= max(0.1, practice_multiplier)
    answers_xp = apply_diminishing(raw_answers, xp_already_today)
    if answers_xp:
        correct_count = sum(1 for score, _ in item_scores if score >= 0.999)
        grants.append(
            XPGrant(
                amount=answers_xp,
                reason=XPReason.CORRECT_ANSWER,
                label=f"{correct_count} bonne{plural(correct_count)} réponse{plural(correct_count)}",
                meta={
                    "raw": round(raw_answers, 2),
                    "factor": diminishing_factor(xp_already_today),
                },
            )
        )

    running = xp_already_today + answers_xp
    if passed:
        bonus = apply_diminishing(PASS_BONUS, running)
        running += bonus
        grants.append(XPGrant(bonus, XPReason.ASSESSMENT_PASSED, "Évaluation réussie"))
    if score_pct >= 100.0:
        bonus = apply_diminishing(PERFECT_BONUS, running)
        running += bonus
        grants.append(XPGrant(bonus, XPReason.PERFECT_SCORE, "Sans faute !"))
    if cleared_weaknesses:
        bonus = apply_diminishing(WEAKNESS_CLEARED_BONUS * cleared_weaknesses, running)
        running += bonus
        grants.append(
            XPGrant(
                bonus,
                XPReason.WEAKNESS_CLEARED,
                f"{cleared_weaknesses} lacune{plural(cleared_weaknesses)} comblée{plural(cleared_weaknesses)}",
                {"count": cleared_weaknesses},
            )
        )
    if streak_days >= 2:
        bonus = min(STREAK_MAX_BONUS, STREAK_XP_PER_DAY * streak_days)
        bonus = apply_diminishing(bonus, running)
        running += bonus
        grants.append(
            XPGrant(
                bonus, XPReason.STREAK_BONUS, f"Série de {streak_days} jours", {"days": streak_days}
            )
        )

    total = sum(g.amount for g in grants)
    return total, grants


# ---------------------------------------------------------------------------
# Conversion XP -> minutes
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Conversion:
    minutes: int
    xp_spent: int
    xp_remaining: int
    capped_by_daily_limit: bool
    reason: str | None = None

    @property
    def ok(self) -> bool:
        return self.minutes > 0


def quote_conversion(
    *,
    xp_balance: int,
    xp_to_spend: int | None,
    minutes_per_100_xp: int,
    daily_bonus_used_minutes: int,
    daily_bonus_cap_minutes: int,
) -> Conversion:
    """Simule (ou prepare) une conversion XP -> minutes.

    La duree est arrondie **au pas de 5 minutes inferieur** : le protocole de
    code ne sait transporter que des multiples de 5.
    """
    if minutes_per_100_xp <= 0:
        return Conversion(0, 0, xp_balance, False, "La conversion est desactivee par le parent.")

    remaining_cap = max(0, daily_bonus_cap_minutes - daily_bonus_used_minutes)
    if remaining_cap < DURATION_STEP_MINUTES:
        return Conversion(0, 0, xp_balance, True, "Plafond de bonus quotidien atteint.")

    wanted = xp_balance if xp_to_spend is None else min(xp_to_spend, xp_balance)
    if wanted <= 0:
        return Conversion(0, 0, xp_balance, False, "Pas assez de points d'experience.")

    minutes = int(wanted * minutes_per_100_xp / 100)
    capped = False
    if minutes > remaining_cap:
        minutes, capped = remaining_cap, True

    minutes -= minutes % DURATION_STEP_MINUTES
    if minutes <= 0:
        need = int(100 * DURATION_STEP_MINUTES / minutes_per_100_xp)
        return Conversion(
            0, 0, xp_balance, capped, f"Il faut au moins {need} XP pour obtenir 5 minutes."
        )

    xp_spent = int(round(minutes * 100 / minutes_per_100_xp))
    xp_spent = min(xp_spent, xp_balance)
    return Conversion(minutes, xp_spent, xp_balance - xp_spent, capped)


# ---------------------------------------------------------------------------
# Grand livre (I/O)
# ---------------------------------------------------------------------------


async def xp_earned_today(db: AsyncSession, child_id: uuid.UUID, at: datetime | None = None) -> int:
    at = at or clock_now()
    start = at.replace(hour=0, minute=0, second=0, microsecond=0)
    total = await db.scalar(
        select(func.coalesce(func.sum(XPLedgerEntry.delta), 0)).where(
            XPLedgerEntry.child_id == child_id,
            XPLedgerEntry.created_at >= start,
            XPLedgerEntry.delta > 0,
        )
    )
    return int(total or 0)


async def record_xp(
    db: AsyncSession,
    child: Child,
    grants: list[XPGrant],
    *,
    ref_type: str | None = None,
    ref_id: uuid.UUID | None = None,
) -> list[XPLedgerEntry]:
    """Ecrit les mouvements et met a jour le solde de l'enfant."""
    entries: list[XPLedgerEntry] = []
    for grant in grants:
        if grant.amount == 0:
            continue
        child.xp_balance = max(0, child.xp_balance + grant.amount)
        if grant.amount > 0:
            child.xp_lifetime += grant.amount
        entry = XPLedgerEntry(
            child_id=child.id,
            delta=grant.amount,
            reason=grant.reason,
            balance_after=child.xp_balance,
            ref_type=ref_type,
            ref_id=ref_id,
            label=grant.label,
            meta=grant.meta,
        )
        db.add(entry)
        entries.append(entry)
    return entries


def update_streak(child: Child, today: date) -> int:
    """Met a jour la serie de jours consecutifs d'activite."""
    previous = child.last_activity_on
    if previous == today:
        return child.streak_days
    if previous is not None and (today - previous).days == 1:
        child.streak_days += 1
    else:
        child.streak_days = 1
    child.last_activity_on = today
    return child.streak_days
