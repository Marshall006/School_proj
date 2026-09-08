"""Appairage et synchronisation des appareils."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.enums import DevicePlatform
from app.schemas.common import ORMModel


class PairingCodeRequest(BaseModel):
    child_id: uuid.UUID
    suggested_name: str | None = Field(default=None, max_length=120)
    ttl_minutes: int = Field(default=30, ge=5, le=1440)


class PairingCodeOut(BaseModel):
    code: str
    expires_at: datetime
    child_id: uuid.UUID
    instructions: str = (
        "Saisis ce code dans l'application KODA installee sur la tablette de l'enfant."
    )


class DeviceClaimRequest(BaseModel):
    pairing_code: str = Field(min_length=4, max_length=32)
    name: str = Field(min_length=1, max_length=120)
    platform: DevicePlatform = DevicePlatform.ANDROID
    os_version: str | None = None
    app_version: str | None = None
    hardware_id: str | None = Field(default=None, max_length=128)
    boot_id: str | None = None


class DeviceCredentials(BaseModel):
    """Remis une seule fois. `device_secret` permet la validation hors ligne."""

    device_id: uuid.UUID
    child_id: uuid.UUID
    device_token: str
    device_secret: str
    accepted_counter: int
    protocol: str = "KODA-UNLOCK/1"
    server_time: datetime


class DeviceOut(ORMModel):
    id: uuid.UUID
    child_id: uuid.UUID
    name: str
    platform: str
    status: str
    app_version: str | None = None
    os_version: str | None = None
    last_seen_at: datetime | None = None
    last_sync_at: datetime | None = None
    clock_skew_ms: int
    tamper_score: float
    failed_code_attempts: int
    code_locked_until: datetime | None = None
    created_at: datetime


class DeviceSyncRequest(BaseModel):
    """Battement de synchronisation envoye par l'appareil (meme hors session)."""

    boot_id: str | None = None
    device_wall_ms: int | None = None
    app_version: str | None = None
    os_version: str | None = None
    battery_pct: int | None = Field(default=None, ge=0, le=100)
    pending_events: list[dict[str, Any]] = Field(default_factory=list)


class DeviceSyncResponse(BaseModel):
    server_time: datetime
    clock_skew_ms: int
    clock_trustworthy: bool
    child: dict[str, Any]
    policy: dict[str, Any]
    lockout: dict[str, Any] | None = None
    active_session: dict[str, Any] | None = None
    revoked_code_fingerprints: list[str] = Field(default_factory=list)
    accepted_counter: int
    lookahead_window: int
    heartbeat_interval_seconds: int
    should_lock: bool
    messages: list[str] = Field(default_factory=list)
