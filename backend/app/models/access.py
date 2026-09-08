"""Codes de deverrouillage, sessions d'ecran, temps de carence."""

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
from app.models.enums import (
    LockoutReason,
    ScreenEventType,
    ScreenSessionState,
    UnlockCodeStatus,
)

if TYPE_CHECKING:
    from app.models.family import Child


class UnlockCode(UUIDPrimaryKey, TimestampMixin, Base):
    """Trace serveur d'un code emis. Le code lui-meme n'est jamais stocke en clair."""

    __tablename__ = "unlock_codes"
    __table_args__ = (Index("ix_unlock_codes_device_status", "device_id", "status"),)

    child_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("children.id", ondelete="CASCADE"), index=True
    )
    device_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("devices.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(32))  # UnlockKind (protocole)
    status: Mapped[UnlockCodeStatus] = mapped_column(
        enum_column(UnlockCodeStatus), default=UnlockCodeStatus.ISSUED, index=True
    )
    counter: Mapped[int] = mapped_column(Integer)
    duration_minutes: Mapped[int] = mapped_column(Integer)
    fingerprint: Mapped[str] = mapped_column(String(64), index=True)

    issued_by_parent_id: Mapped[uuid.UUID | None] = mapped_column(UUIDType, default=None)
    assessment_id: Mapped[uuid.UUID | None] = mapped_column(UUIDType, default=None, index=True)
    expires_at: Mapped[datetime]
    consumed_at: Mapped[datetime | None] = mapped_column(default=None)
    revoked_at: Mapped[datetime | None] = mapped_column(default=None)
    consumed_offline: Mapped[bool] = mapped_column(Boolean, default=False)
    note: Mapped[str | None] = mapped_column(String(255), default=None)

    child: Mapped[Child] = relationship(back_populates="unlock_codes")


class ScreenSession(UUIDPrimaryKey, TimestampMixin, Base):
    """Fenetre de temps d'ecran ouverte par un code valide.

    La comptabilite se fait en millisecondes **monotones** rapportees par
    l'appareil : changer l'heure systeme ne rallonge rien.
    """

    __tablename__ = "screen_sessions"
    __table_args__ = (Index("ix_sessions_child_state", "child_id", "state", "started_at"),)

    child_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("children.id", ondelete="CASCADE"), index=True
    )
    device_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("devices.id", ondelete="CASCADE"), index=True
    )
    unlock_code_id: Mapped[uuid.UUID | None] = mapped_column(UUIDType, default=None)
    state: Mapped[ScreenSessionState] = mapped_column(
        enum_column(ScreenSessionState), default=ScreenSessionState.ACTIVE, index=True
    )

    granted_ms: Mapped[int] = mapped_column(BigInteger)
    bonus_ms: Mapped[int] = mapped_column(BigInteger, default=0)
    consumed_ms: Mapped[int] = mapped_column(BigInteger, default=0)
    offline_ms: Mapped[int] = mapped_column(BigInteger, default=0)

    started_at: Mapped[datetime]
    wall_deadline_at: Mapped[datetime]  # butoir absolu : pauses illimitees interdites
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(default=None)
    last_monotonic_ms: Mapped[int] = mapped_column(BigInteger, default=0)
    paused_at: Mapped[datetime | None] = mapped_column(default=None)
    ended_at: Mapped[datetime | None] = mapped_column(default=None)
    end_reason: Mapped[str | None] = mapped_column(String(64), default=None)

    device_boot_id: Mapped[str | None] = mapped_column(String(64), default=None)
    anomaly_count: Mapped[int] = mapped_column(Integer, default=0)
    integrity_score: Mapped[float] = mapped_column(Float, default=1.0)
    meta: Mapped[dict[str, Any]] = mapped_column(default=dict)

    child: Mapped[Child] = relationship(back_populates="screen_sessions")
    events: Mapped[list[ScreenEvent]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="ScreenEvent.created_at"
    )

    @property
    def total_ms(self) -> int:
        return self.granted_ms + self.bonus_ms

    @property
    def remaining_ms(self) -> int:
        return max(0, self.total_ms - self.consumed_ms)

    @property
    def is_live(self) -> bool:
        return self.state in (ScreenSessionState.ACTIVE, ScreenSessionState.PAUSED)


class ScreenEvent(UUIDPrimaryKey, TimestampMixin, Base):
    """Journal fin d'une session : chaque battement de coeur laisse une trace."""

    __tablename__ = "screen_events"

    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("screen_sessions.id", ondelete="CASCADE"), index=True
    )
    type: Mapped[ScreenEventType] = mapped_column(enum_column(ScreenEventType))
    monotonic_ms: Mapped[int] = mapped_column(BigInteger, default=0)
    device_wall_ms: Mapped[int | None] = mapped_column(BigInteger, default=None)
    delta_ms: Mapped[int] = mapped_column(BigInteger, default=0)
    skew_ms: Mapped[int] = mapped_column(BigInteger, default=0)
    screen_on: Mapped[bool] = mapped_column(Boolean, default=True)
    meta: Mapped[dict[str, Any]] = mapped_column(default=dict)

    session: Mapped[ScreenSession] = relationship(back_populates="events")


class Lockout(UUIDPrimaryKey, TimestampMixin, Base):
    """Temps de carence : l'enfant doit reviser avant de retenter."""

    __tablename__ = "lockouts"
    __table_args__ = (Index("ix_lockouts_child_until", "child_id", "until"),)

    child_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("children.id", ondelete="CASCADE"), index=True
    )
    reason: Mapped[LockoutReason] = mapped_column(enum_column(LockoutReason))
    started_at: Mapped[datetime]
    until: Mapped[datetime]
    message: Mapped[str | None] = mapped_column(Text, default=None)
    source_assessment_id: Mapped[uuid.UUID | None] = mapped_column(UUIDType, default=None)
    released_at: Mapped[datetime | None] = mapped_column(default=None)
    released_by_parent_id: Mapped[uuid.UUID | None] = mapped_column(UUIDType, default=None)
    review_topics: Mapped[list[Any]] = mapped_column(default=list)  # notions a revoir

    child: Mapped[Child] = relationship(back_populates="lockouts")
