"""Catalogue pedagogique expose aux clients."""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field

from app.models.enums import QuestionType
from app.schemas.common import ORMModel


class SubjectOut(ORMModel):
    id: uuid.UUID
    code: str
    name: str
    color: str
    icon: str
    position: int


class GradeLevelOut(ORMModel):
    id: uuid.UUID
    country_code: str
    code: str
    name: str
    cycle: str
    position: int
    typical_age: int | None = None


class CountryOut(BaseModel):
    code: str
    name: str
    currency: str
    capital: str
    grades: list[dict[str, Any]] = Field(default_factory=list)


class TopicOut(ORMModel):
    id: uuid.UUID
    code: str
    name: str
    description: str | None = None
    country_code: str
    grade_code: str
    position: int
    is_core: bool


class CustomQuestionIn(BaseModel):
    """Question ajoutee par un parent (la lecon du jour, un devoir precis)."""

    topic_id: uuid.UUID
    type: QuestionType = QuestionType.MCQ_SINGLE
    difficulty: int = Field(default=2, ge=1, le=5)
    prompt: str = Field(min_length=3)
    instructions: str | None = None
    choices: list[dict[str, Any]] | None = None
    answer: dict[str, Any]
    explanation: str | None = None
    points: float = Field(default=1.0, ge=0.25, le=5.0)
    estimated_seconds: int = Field(default=45, ge=5, le=900)
    tags: list[str] = Field(default_factory=list)


class QuestionOut(ORMModel):
    id: uuid.UUID
    topic_id: uuid.UUID
    external_ref: str | None = None
    type: str
    difficulty: int
    prompt: str
    instructions: str | None = None
    choices: list[Any] | None = None
    explanation: str | None = None
    points: float
    tags: list[Any] = Field(default_factory=list)
    is_active: bool
    times_served: int
    times_correct: int
