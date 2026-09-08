"""Enfants, regles, calendrier scolaire."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.models.enums import PeriodType
from app.schemas.common import ORMModel


class ChildCreate(BaseModel):
    display_name: str = Field(min_length=1, max_length=120)
    grade_code: str = Field(min_length=1, max_length=16)
    country_code: str | None = Field(default=None, min_length=2, max_length=2)
    birth_date: date | None = None
    avatar: str = "fox"
    pin: str | None = Field(default=None, pattern=r"^\d{4,6}$")

    @field_validator("grade_code")
    @classmethod
    def _upper_grade(cls, v: str) -> str:
        return v.upper()

    @field_validator("country_code")
    @classmethod
    def _upper_country(cls, v: str | None) -> str | None:
        return v.upper() if v else v


class ChildUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=120)
    grade_code: str | None = Field(default=None, max_length=16)
    country_code: str | None = Field(default=None, min_length=2, max_length=2)
    birth_date: date | None = None
    avatar: str | None = None
    pin: str | None = Field(default=None, pattern=r"^\d{4,6}$")
    is_active: bool | None = None


class ChildOut(ORMModel):
    id: uuid.UUID
    family_id: uuid.UUID
    display_name: str
    grade_code: str
    country_code: str
    birth_date: date | None = None
    avatar: str
    xp_balance: int
    xp_lifetime: int
    streak_days: int
    is_active: bool
    created_at: datetime


class PolicyIn(BaseModel):
    period_type: PeriodType = PeriodType.SCHOOL
    child_id: uuid.UUID | None = None
    name: str = "Regles personnalisees"
    pass_score_pct: float | None = Field(default=None, ge=0, le=100)
    question_count: int | None = Field(default=None, ge=3, le=40)
    time_limit_minutes: int | None = Field(default=None, ge=3, le=180)
    difficulty_bias: float | None = Field(default=None, ge=-1, le=1)
    reward_minutes: int | None = Field(default=None, ge=5, le=495)
    daily_cap_minutes: int | None = Field(default=None, ge=0, le=1440)
    max_attempts_per_day: int | None = Field(default=None, ge=1, le=20)
    allow_parent_direct_unlock: bool | None = None
    allow_assessment_unlock: bool | None = None
    cooldown_minutes: int | None = Field(default=None, ge=0, le=1440)
    cooldown_escalation: float | None = Field(default=None, ge=1.0, le=4.0)
    review_required_before_retry: bool | None = None
    minutes_per_100_xp: int | None = Field(default=None, ge=0, le=120)
    xp_daily_bonus_cap_minutes: int | None = Field(default=None, ge=0, le=600)
    practice_xp_multiplier: float | None = Field(default=None, ge=0.1, le=5.0)
    curfew_start: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    curfew_end: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    subject_codes: list[str] | None = None
    is_active: bool | None = None


class PolicyOut(ORMModel):
    id: uuid.UUID
    family_id: uuid.UUID
    child_id: uuid.UUID | None = None
    period_type: str
    name: str
    is_active: bool
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
    curfew_start: str | None = None
    curfew_end: str | None = None
    subject_codes: list[Any] = []


class EffectivePolicyOut(BaseModel):
    period_type: str
    source: str
    pass_score_pct: float
    pass_score_out_of_20: float
    question_count: int
    time_limit_minutes: int
    reward_minutes: int
    daily_cap_minutes: int
    max_attempts_per_day: int
    allow_parent_direct_unlock: bool
    allow_assessment_unlock: bool
    cooldown_minutes: int
    minutes_per_100_xp: int
    xp_daily_bonus_cap_minutes: int
    curfew_start: str | None = None
    curfew_end: str | None = None
    subject_codes: list[str] = []
    timezone: str


class CalendarPeriodIn(BaseModel):
    label: str = Field(max_length=120)
    period_type: PeriodType
    start_date: date
    end_date: date

    @field_validator("end_date")
    @classmethod
    def _ordered(cls, v: date, info: Any) -> date:
        start = info.data.get("start_date")
        if start and v < start:
            raise ValueError("La date de fin doit suivre la date de debut.")
        return v


class CalendarPeriodOut(ORMModel):
    id: uuid.UUID
    label: str
    period_type: str
    start_date: date
    end_date: date
