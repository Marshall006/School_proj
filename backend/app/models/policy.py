"""Regles parametrables par le parent + calendrier scolaire du foyer."""

from __future__ import annotations

import uuid
from datetime import date
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, Date, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKey, enum_column
from app.models.enums import PeriodType

if TYPE_CHECKING:
    from app.models.family import Family


class PolicyProfile(UUIDPrimaryKey, TimestampMixin, Base):
    """Un jeu de regles applique selon la periode (scolaire / week-end / vacances).

    Resolution : profil de l'enfant pour la periode courante, sinon profil du
    foyer pour cette periode, sinon valeurs par defaut du produit.
    """

    __tablename__ = "policy_profiles"
    __table_args__ = (
        UniqueConstraint("family_id", "child_id", "period_type", name="uq_policy_scope"),
    )

    family_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("families.id", ondelete="CASCADE"), index=True
    )
    child_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("children.id", ondelete="CASCADE"), default=None, index=True
    )
    period_type: Mapped[PeriodType] = mapped_column(
        enum_column(PeriodType), default=PeriodType.SCHOOL
    )
    name: Mapped[str] = mapped_column(String(80), default="Regles par defaut")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # --- Exigences de reussite -------------------------------------------
    pass_score_pct: Mapped[float] = mapped_column(Float, default=70.0)  # 14/20
    question_count: Mapped[int] = mapped_column(Integer, default=10)
    time_limit_minutes: Mapped[int] = mapped_column(Integer, default=20)
    difficulty_bias: Mapped[float] = mapped_column(Float, default=0.0)  # -1 doux .. +1 exigeant

    # --- Recompense -------------------------------------------------------
    reward_minutes: Mapped[int] = mapped_column(Integer, default=180)
    daily_cap_minutes: Mapped[int] = mapped_column(Integer, default=300)
    max_attempts_per_day: Mapped[int] = mapped_column(Integer, default=4)
    allow_parent_direct_unlock: Mapped[bool] = mapped_column(Boolean, default=True)
    allow_assessment_unlock: Mapped[bool] = mapped_column(Boolean, default=True)

    # --- Sanction ---------------------------------------------------------
    cooldown_minutes: Mapped[int] = mapped_column(Integer, default=120)
    cooldown_escalation: Mapped[float] = mapped_column(Float, default=1.0)  # x par echec du jour
    review_required_before_retry: Mapped[bool] = mapped_column(Boolean, default=True)

    # --- Experience -------------------------------------------------------
    minutes_per_100_xp: Mapped[int] = mapped_column(Integer, default=15)
    xp_daily_bonus_cap_minutes: Mapped[int] = mapped_column(Integer, default=60)
    practice_xp_multiplier: Mapped[float] = mapped_column(Float, default=1.0)

    # --- Horaires ---------------------------------------------------------
    curfew_start: Mapped[str | None] = mapped_column(String(5), default="21:00")
    curfew_end: Mapped[str | None] = mapped_column(String(5), default="07:00")

    # --- Contenu ----------------------------------------------------------
    subject_codes: Mapped[list[Any]] = mapped_column(default=list)  # vide = toutes les matieres
    extras: Mapped[dict[str, Any]] = mapped_column(default=dict)

    family: Mapped[Family] = relationship(back_populates="policies")


class CalendarPeriod(UUIDPrimaryKey, TimestampMixin, Base):
    """Plage de dates declaree "vacances" (ou autre) pour le foyer."""

    __tablename__ = "calendar_periods"

    family_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("families.id", ondelete="CASCADE"), index=True
    )
    label: Mapped[str] = mapped_column(String(120))
    period_type: Mapped[PeriodType] = mapped_column(enum_column(PeriodType))
    start_date: Mapped[date] = mapped_column(Date, index=True)
    end_date: Mapped[date] = mapped_column(Date, index=True)

    family: Mapped[Family] = relationship(back_populates="calendar")
