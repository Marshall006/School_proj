"""Appareils de l'enfant et appairage."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKey, enum_column
from app.models.enums import DevicePlatform, DeviceStatus

if TYPE_CHECKING:
    from app.models.family import Child


class Device(UUIDPrimaryKey, TimestampMixin, Base):
    """Une tablette / un PC appaire a un enfant.

    `device_secret` est la cle HMAC du protocole KODA-UNLOCK : elle ne quitte le
    serveur qu'une seule fois, au moment de l'appairage.
    """

    __tablename__ = "devices"

    child_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("children.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    platform: Mapped[DevicePlatform] = mapped_column(enum_column(DevicePlatform))
    status: Mapped[DeviceStatus] = mapped_column(
        enum_column(DeviceStatus), default=DeviceStatus.ACTIVE, index=True
    )
    device_secret: Mapped[str] = mapped_column(Text)
    unlock_counter: Mapped[int] = mapped_column(Integer, default=0)
    accepted_counter: Mapped[int] = mapped_column(Integer, default=0)  # dernier code consomme
    failed_code_attempts: Mapped[int] = mapped_column(Integer, default=0)
    code_locked_until: Mapped[datetime | None] = mapped_column(default=None)

    app_version: Mapped[str | None] = mapped_column(String(32), default=None)
    os_version: Mapped[str | None] = mapped_column(String(64), default=None)
    hardware_id: Mapped[str | None] = mapped_column(String(128), default=None, index=True)
    push_token: Mapped[str | None] = mapped_column(Text, default=None)

    last_seen_at: Mapped[datetime | None] = mapped_column(default=None)
    last_sync_at: Mapped[datetime | None] = mapped_column(default=None)
    boot_id: Mapped[str | None] = mapped_column(String(64), default=None)
    clock_skew_ms: Mapped[int] = mapped_column(Integer, default=0)
    tamper_score: Mapped[float] = mapped_column(Float, default=0.0)  # 0 = sain, >1 = suspect
    kiosk_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    meta: Mapped[dict[str, Any]] = mapped_column(default=dict)

    child: Mapped[Child] = relationship(back_populates="devices")

    @property
    def is_usable(self) -> bool:
        return self.status == DeviceStatus.ACTIVE


class PairingRequest(UUIDPrimaryKey, TimestampMixin, Base):
    """Code d'appairage a usage unique genere depuis le tableau de bord parent."""

    __tablename__ = "pairing_requests"

    child_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("children.id", ondelete="CASCADE"), index=True
    )
    created_by_parent_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("parents.id"))
    code_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime]
    consumed_at: Mapped[datetime | None] = mapped_column(default=None)
    device_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("devices.id", ondelete="SET NULL"), default=None
    )
    suggested_name: Mapped[str | None] = mapped_column(String(120), default=None)
