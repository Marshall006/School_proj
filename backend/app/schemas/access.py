"""Codes de deverrouillage et sessions de temps d'ecran."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class ParentUnlockRequest(BaseModel):
    """Deverrouillage direct : les devoirs sont faits, le parent ouvre l'acces."""

    child_id: uuid.UUID
    device_id: uuid.UUID | None = None
    duration_minutes: int = Field(default=180, ge=5, le=495)
    note: str | None = Field(default=None, max_length=255)
    ttl_minutes: int = Field(default=30, ge=5, le=720)


class UnlockCodeOut(BaseModel):
    id: uuid.UUID
    code: str
    formatted: str
    kind: str
    duration_minutes: int
    expires_at: datetime
    device_id: uuid.UUID
    child_id: uuid.UUID


class UnlockCodeRecordOut(ORMModel):
    id: uuid.UUID
    child_id: uuid.UUID
    device_id: uuid.UUID
    kind: str
    status: str
    duration_minutes: int
    expires_at: datetime
    consumed_at: datetime | None = None
    consumed_offline: bool
    note: str | None = None
    created_at: datetime


class RedeemRequest(BaseModel):
    code: str = Field(min_length=4, max_length=24)
    boot_id: str | None = None
    device_wall_ms: int | None = None
    #: Renseigne si l'appareil a valide le code hors ligne et se synchronise apres coup.
    consumed_offline_at: datetime | None = None
    offline_active_ms: int = Field(default=0, ge=0)


class RedeemResponse(BaseModel):
    session_id: uuid.UUID
    granted_minutes: int
    granted_ms: int
    remaining_ms: int
    started_at: datetime
    wall_deadline_at: datetime
    truncated_by_cap: bool
    warnings: list[str] = Field(default_factory=list)
    heartbeat_interval_seconds: int


class HeartbeatRequest(BaseModel):
    """Battement de coeur du minuteur.

    `monotonic_ms` est le temps ecoule depuis le debut de la session mesure par
    l'horloge monotone de l'appareil : c'est la seule mesure de reference.
    """

    monotonic_ms: int = Field(ge=0)
    device_wall_ms: int | None = None
    screen_on: bool = True
    boot_id: str | None = None
    foreground_app: str | None = None


class HeartbeatResponse(BaseModel):
    session_id: uuid.UUID
    state: str
    remaining_ms: int
    remaining_minutes: int
    consumed_ms: int
    granted_ms: int
    should_lock: bool
    anomalies: list[str] = Field(default_factory=list)
    server_time: datetime
    wall_deadline_at: datetime


class ScreenSessionOut(ORMModel):
    id: uuid.UUID
    child_id: uuid.UUID
    device_id: uuid.UUID
    state: str
    granted_ms: int
    bonus_ms: int
    consumed_ms: int
    offline_ms: int
    started_at: datetime
    wall_deadline_at: datetime
    last_heartbeat_at: datetime | None = None
    ended_at: datetime | None = None
    end_reason: str | None = None
    anomaly_count: int
    integrity_score: float
    meta: dict[str, Any] = Field(default_factory=dict)


class ExtendRequest(BaseModel):
    minutes: int = Field(ge=5, le=240)
    reason: str | None = Field(default=None, max_length=255)


class XPConversionRequest(BaseModel):
    child_id: uuid.UUID
    device_id: uuid.UUID | None = None
    xp_to_spend: int | None = Field(default=None, ge=1)


class XPConversionQuote(BaseModel):
    minutes: int
    xp_spent: int
    xp_remaining: int
    capped_by_daily_limit: bool
    reason: str | None = None
    minutes_per_100_xp: int


class LockoutOut(BaseModel):
    id: uuid.UUID
    reason: str
    until: datetime
    remaining_seconds: int
    remaining_minutes: int
    message: str | None = None
    review_topics: list[dict[str, Any]] = Field(default_factory=list)
