"""Banque pedagogique : pays -> niveau -> matiere -> notion -> question."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKey, UUIDType, enum_column
from app.models.enums import QuestionType

if TYPE_CHECKING:
    pass


class Subject(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "subjects"

    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(80))
    color: Mapped[str] = mapped_column(String(9), default="#4F46E5")
    icon: Mapped[str] = mapped_column(String(32), default="book")
    position: Mapped[int] = mapped_column(Integer, default=0)

    topics: Mapped[list[Topic]] = relationship(back_populates="subject")


class GradeLevel(UUIDPrimaryKey, TimestampMixin, Base):
    """Niveaux scolaires : ils different d'un pays a l'autre (CI/CP au Benin...)."""

    __tablename__ = "grade_levels"
    __table_args__ = (UniqueConstraint("country_code", "code", name="uq_grade_country_code"),)

    country_code: Mapped[str] = mapped_column(String(2), index=True)
    code: Mapped[str] = mapped_column(String(16))
    name: Mapped[str] = mapped_column(String(80))
    cycle: Mapped[str] = mapped_column(String(40), default="primaire")
    position: Mapped[int] = mapped_column(Integer, default=0)
    typical_age: Mapped[int | None] = mapped_column(Integer, default=None)


class Topic(UUIDPrimaryKey, TimestampMixin, Base):
    """Notion du programme, ancree sur un pays et un niveau."""

    __tablename__ = "topics"
    __table_args__ = (
        UniqueConstraint("country_code", "grade_code", "code", name="uq_topic_scope"),
        Index("ix_topics_lookup", "country_code", "grade_code", "subject_id"),
    )

    subject_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("subjects.id"), index=True)
    country_code: Mapped[str] = mapped_column(String(2), index=True)
    grade_code: Mapped[str] = mapped_column(String(16), index=True)
    code: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(Text, default=None)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("topics.id", ondelete="SET NULL"), default=None
    )
    position: Mapped[int] = mapped_column(Integer, default=0)
    tags: Mapped[list[Any]] = mapped_column(default=list)
    is_core: Mapped[bool] = mapped_column(Boolean, default=True)

    subject: Mapped[Subject] = relationship(back_populates="topics")
    questions: Mapped[list[Question]] = relationship(back_populates="topic")


class Question(UUIDPrimaryKey, TimestampMixin, Base):
    """Un item evaluable.

    `answer` decrit la correction attendue, `input_spec` decrit l'interface de
    saisie proposee a l'enfant (pave numerique, palette de symboles, gabarit
    d'operation posee, ardoise manuscrite...).
    """

    __tablename__ = "questions"
    __table_args__ = (
        Index("ix_questions_selection", "topic_id", "difficulty", "is_active"),
        UniqueConstraint("external_ref", name="uq_questions_external_ref"),
    )

    topic_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("topics.id", ondelete="CASCADE"))
    external_ref: Mapped[str | None] = mapped_column(String(120), default=None)
    type: Mapped[QuestionType] = mapped_column(enum_column(QuestionType))
    difficulty: Mapped[int] = mapped_column(Integer, default=2)  # 1 (facile) .. 5 (difficile)
    difficulty_elo: Mapped[float] = mapped_column(Float, default=0.0)  # calibrage empirique

    prompt: Mapped[str] = mapped_column(Text)
    instructions: Mapped[str | None] = mapped_column(Text, default=None)
    choices: Mapped[list[Any] | None] = mapped_column(default=None)
    answer: Mapped[dict[str, Any]] = mapped_column(default=dict)
    explanation: Mapped[str | None] = mapped_column(Text, default=None)
    hints: Mapped[list[Any]] = mapped_column(default=list)
    assets: Mapped[list[Any]] = mapped_column(default=list)
    input_spec: Mapped[dict[str, Any]] = mapped_column(default=dict)

    points: Mapped[float] = mapped_column(Float, default=1.0)
    estimated_seconds: Mapped[int] = mapped_column(Integer, default=45)
    locale: Mapped[str] = mapped_column(String(8), default="fr-FR")
    tags: Mapped[list[Any]] = mapped_column(default=list)
    source: Mapped[str] = mapped_column(String(64), default="koda-core")
    author_parent_id: Mapped[uuid.UUID | None] = mapped_column(UUIDType, default=None, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Statistiques d'usage (calibrage et detection d'items defectueux)
    times_served: Mapped[int] = mapped_column(Integer, default=0)
    times_correct: Mapped[int] = mapped_column(Integer, default=0)
    avg_seconds: Mapped[float] = mapped_column(Float, default=0.0)

    topic: Mapped[Topic] = relationship(back_populates="questions")

    @property
    def empirical_success_rate(self) -> float | None:
        if self.times_served < 5:
            return None
        return self.times_correct / self.times_served
