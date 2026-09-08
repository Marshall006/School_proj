"""Evaluations : lancement, reponses, correction."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.enums import AnswerMode, AssessmentKind
from app.schemas.common import ORMModel


class StartAssessmentRequest(BaseModel):
    child_id: uuid.UUID | None = None  # deduit du jeton appareil si absent
    kind: AssessmentKind = AssessmentKind.UNLOCK
    question_count: int | None = Field(default=None, ge=3, le=40)
    seed: int | None = None  # rejouer une epreuve a l'identique (support, litige)


class AssessmentItemOut(BaseModel):
    """Enonce transmis a l'enfant : jamais la correction."""

    id: uuid.UUID
    position: int
    type: str
    difficulty: int
    prompt: str
    instructions: str | None = None
    choices: list[Any] | None = None
    assets: list[Any] = Field(default_factory=list)
    input_spec: dict[str, Any] = Field(default_factory=dict)
    points_max: float
    estimated_seconds: int = 45
    subject_code: str | None = None
    answered: bool = False
    answer: dict[str, Any] | None = None
    answer_mode: str | None = None


class AssessmentOut(BaseModel):
    id: uuid.UUID
    child_id: uuid.UUID
    kind: str
    status: str
    question_count: int
    points_max: float
    pass_score_pct: float
    pass_score_out_of_20: float
    started_at: datetime | None = None
    expires_at: datetime | None = None
    time_limit_seconds: int | None = None
    items: list[AssessmentItemOut] = Field(default_factory=list)
    blueprint_distribution: dict[str, int] = Field(default_factory=dict)


class SaveAnswerRequest(BaseModel):
    answer: dict[str, Any] | None = None
    answer_mode: AnswerMode | None = None
    strokes: dict[str, Any] | None = None  # traces de l'ardoise (vectorielles)
    scratchpad: dict[str, Any] | None = None  # brouillon libre, non note
    time_spent_ms: int | None = Field(default=None, ge=0)


class SubmitRequest(BaseModel):
    integrity: dict[str, Any] | None = None  # sorties d'application, pauses...
    answers: dict[uuid.UUID, SaveAnswerRequest] | None = None  # envoi groupe hors ligne


class ReviewItem(BaseModel):
    position: int
    subject_code: str | None = None
    bucket: str | None = None
    prompt: str | None = None
    choices: list[Any] | None = None
    type: str
    difficulty: int
    your_answer: Any = None
    expected: Any = None
    is_correct: bool | None = None
    score: float
    points: str
    explanation: str | None = None
    diagnosis: str | None = None
    detail: str | None = None
    per_part: list[dict[str, Any]] = Field(default_factory=list)
    needs_manual_review: bool = False
    time_spent_ms: int = 0


class SubmissionOut(BaseModel):
    assessment_id: uuid.UUID
    status: str
    passed: bool
    pending_manual_review: bool
    score_pct: float
    score_out_of_20: float
    pass_score_pct: float
    pass_score_out_of_20: float
    points_earned: float
    points_max: float
    unlock_code: dict[str, Any] | None = None
    lockout: dict[str, Any] | None = None
    xp_earned: int
    xp_detail: list[dict[str, Any]] = Field(default_factory=list)
    review: list[ReviewItem] = Field(default_factory=list)
    weak_topics: list[dict[str, Any]] = Field(default_factory=list)
    mastery_moves: list[dict[str, Any]] = Field(default_factory=list)


class ManualGradeRequest(BaseModel):
    score: float = Field(ge=0, le=1)
    comment: str | None = Field(default=None, max_length=500)


class AssessmentSummaryOut(ORMModel):
    id: uuid.UUID
    child_id: uuid.UUID
    kind: str
    status: str
    score_pct: float | None = None
    score_out_of_20: float | None = None
    passed: bool | None = None
    question_count: int
    reward_minutes: int
    xp_earned: int
    duration_seconds: int | None = None
    created_at: datetime
    submitted_at: datetime | None = None


class EligibilityOut(BaseModel):
    allowed: bool
    reason: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    policy: dict[str, Any] = Field(default_factory=dict)
    attempts_today: int = 0
    max_attempts_per_day: int = 0
