"""Evaluations (l'examen) et reponses de l'enfant."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKey, UUIDType, enum_column
from app.models.enums import AnswerMode, AssessmentKind, AssessmentStatus, QuestionType

if TYPE_CHECKING:
    from app.models.family import Child


class Assessment(UUIDPrimaryKey, TimestampMixin, Base):
    """Une session d'examen. Le bareme et les regles sont figes au demarrage."""

    __tablename__ = "assessments"
    __table_args__ = (Index("ix_assessments_child_status", "child_id", "status", "created_at"),)

    child_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("children.id", ondelete="CASCADE"), index=True
    )
    device_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("devices.id", ondelete="SET NULL"), default=None
    )
    kind: Mapped[AssessmentKind] = mapped_column(
        enum_column(AssessmentKind), default=AssessmentKind.UNLOCK
    )
    status: Mapped[AssessmentStatus] = mapped_column(
        enum_column(AssessmentStatus), default=AssessmentStatus.IN_PROGRESS, index=True
    )

    # Regles figees a l'instant T (le parent peut les changer sans fausser l'examen)
    policy_snapshot: Mapped[dict[str, Any]] = mapped_column(default=dict)
    blueprint: Mapped[dict[str, Any]] = mapped_column(default=dict)  # trace du moteur adaptatif
    seed: Mapped[int] = mapped_column(BigInteger, default=0)  # tirage reproductible

    pass_score_pct: Mapped[float] = mapped_column(Float, default=70.0)
    question_count: Mapped[int] = mapped_column(Integer, default=10)
    points_max: Mapped[float] = mapped_column(Float, default=0.0)
    points_earned: Mapped[float] = mapped_column(Float, default=0.0)
    score_pct: Mapped[float | None] = mapped_column(Float, default=None)
    score_out_of_20: Mapped[float | None] = mapped_column(Float, default=None)
    passed: Mapped[bool | None] = mapped_column(Boolean, default=None)

    reward_minutes: Mapped[int] = mapped_column(Integer, default=0)
    xp_earned: Mapped[int] = mapped_column(Integer, default=0)

    started_at: Mapped[datetime | None] = mapped_column(default=None)
    expires_at: Mapped[datetime | None] = mapped_column(default=None)
    submitted_at: Mapped[datetime | None] = mapped_column(default=None)
    graded_at: Mapped[datetime | None] = mapped_column(default=None)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, default=None)

    unlock_code_id: Mapped[uuid.UUID | None] = mapped_column(UUIDType, default=None)
    lockout_id: Mapped[uuid.UUID | None] = mapped_column(UUIDType, default=None)
    assigned_by_parent_id: Mapped[uuid.UUID | None] = mapped_column(UUIDType, default=None)
    integrity: Mapped[dict[str, Any]] = mapped_column(default=dict)  # sorties d'ecran, pauses...

    child: Mapped[Child] = relationship(back_populates="assessments")
    items: Mapped[list[AssessmentItem]] = relationship(
        back_populates="assessment",
        cascade="all, delete-orphan",
        order_by="AssessmentItem.position",
    )

    @property
    def is_open(self) -> bool:
        return self.status == AssessmentStatus.IN_PROGRESS


class AssessmentItem(UUIDPrimaryKey, TimestampMixin, Base):
    """Une question posee, la reponse donnee et sa correction."""

    __tablename__ = "assessment_items"
    __table_args__ = (Index("ix_items_assessment_pos", "assessment_id", "position"),)

    assessment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assessments.id", ondelete="CASCADE"), index=True
    )
    question_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("questions.id", ondelete="SET NULL"), default=None
    )
    topic_id: Mapped[uuid.UUID | None] = mapped_column(UUIDType, default=None, index=True)
    subject_code: Mapped[str | None] = mapped_column(String(32), default=None, index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    question_type: Mapped[QuestionType] = mapped_column(enum_column(QuestionType))
    difficulty: Mapped[int] = mapped_column(Integer, default=2)

    #: Copie figee de l'enonce : l'historique reste lisible meme si l'item change.
    snapshot: Mapped[dict[str, Any]] = mapped_column(default=dict)

    answer: Mapped[dict[str, Any] | None] = mapped_column(default=None)
    answer_mode: Mapped[AnswerMode | None] = mapped_column(enum_column(AnswerMode), default=None)
    strokes: Mapped[dict[str, Any] | None] = mapped_column(default=None)  # ardoise : traces
    scratchpad: Mapped[dict[str, Any] | None] = mapped_column(default=None)  # brouillon libre

    is_correct: Mapped[bool | None] = mapped_column(Boolean, default=None)
    score: Mapped[float] = mapped_column(Float, default=0.0)  # 0..1 (credit partiel)
    points_awarded: Mapped[float] = mapped_column(Float, default=0.0)
    points_max: Mapped[float] = mapped_column(Float, default=1.0)
    feedback: Mapped[dict[str, Any]] = mapped_column(default=dict)  # correction detaillee

    time_spent_ms: Mapped[int] = mapped_column(Integer, default=0)
    answered_at: Mapped[datetime | None] = mapped_column(default=None)
    needs_manual_review: Mapped[bool] = mapped_column(Boolean, default=False)
    manual_grade: Mapped[float | None] = mapped_column(Float, default=None)
    graded_by_parent_id: Mapped[uuid.UUID | None] = mapped_column(UUIDType, default=None)
    parent_comment: Mapped[str | None] = mapped_column(Text, default=None)

    assessment: Mapped[Assessment] = relationship(back_populates="items")
