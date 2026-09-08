"""Points d'experience et modele de maitrise par notion."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Float, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKey, UUIDType, enum_column
from app.models.enums import MasteryBand, XPReason

if TYPE_CHECKING:
    from app.models.family import Child


class XPLedgerEntry(UUIDPrimaryKey, TimestampMixin, Base):
    """Grand livre des XP : tout mouvement est trace, jamais un simple compteur."""

    __tablename__ = "xp_ledger"
    __table_args__ = (Index("ix_xp_child_created", "child_id", "created_at"),)

    child_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("children.id", ondelete="CASCADE"), index=True
    )
    delta: Mapped[int] = mapped_column(Integer)
    reason: Mapped[XPReason] = mapped_column(enum_column(XPReason))
    balance_after: Mapped[int] = mapped_column(Integer)
    ref_type: Mapped[str | None] = mapped_column(String(40), default=None)
    ref_id: Mapped[uuid.UUID | None] = mapped_column(UUIDType, default=None)
    label: Mapped[str | None] = mapped_column(String(160), default=None)
    meta: Mapped[dict[str, Any]] = mapped_column(default=dict)

    child: Mapped[Child] = relationship(back_populates="xp_entries")


class Mastery(UUIDPrimaryKey, TimestampMixin, Base):
    """Estimation continue du niveau de l'enfant sur une notion.

    - `ability` : score facon Elo (echelle logistique), compare a la difficulte
      calibree des items pour predire la probabilite de reussite.
    - `ewma` : moyenne mobile exponentielle des reussites recentes (0..1).
    - `next_review_at` / `interval_days` / `ease` : repetition espacee (SM-2 allege).
    """

    __tablename__ = "mastery"
    __table_args__ = (
        UniqueConstraint("child_id", "topic_id", name="uq_mastery_child_topic"),
        Index("ix_mastery_review", "child_id", "next_review_at"),
    )

    child_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("children.id", ondelete="CASCADE"), index=True
    )
    topic_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"), index=True
    )
    subject_code: Mapped[str] = mapped_column(String(32), index=True)

    ability: Mapped[float] = mapped_column(Float, default=0.0)
    ewma: Mapped[float] = mapped_column(Float, default=0.5)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    correct: Mapped[int] = mapped_column(Integer, default=0)
    streak: Mapped[int] = mapped_column(Integer, default=0)
    band: Mapped[MasteryBand] = mapped_column(
        enum_column(MasteryBand), default=MasteryBand.UNKNOWN, index=True
    )

    ease: Mapped[float] = mapped_column(Float, default=2.5)
    interval_days: Mapped[float] = mapped_column(Float, default=0.0)
    next_review_at: Mapped[datetime | None] = mapped_column(default=None)
    last_seen_at: Mapped[datetime | None] = mapped_column(default=None)

    child: Mapped[Child] = relationship(back_populates="mastery")

    @property
    def success_rate(self) -> float | None:
        return (self.correct / self.attempts) if self.attempts else None
