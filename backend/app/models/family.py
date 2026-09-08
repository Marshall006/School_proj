"""Foyer, parents, enfants."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, Date, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKey, UUIDType, enum_column
from app.models.enums import ParentRole

if TYPE_CHECKING:
    from app.models.access import Lockout, ScreenSession, UnlockCode
    from app.models.assessment import Assessment
    from app.models.device import Device
    from app.models.policy import CalendarPeriod, PolicyProfile
    from app.models.progress import Mastery, XPLedgerEntry


class Family(UUIDPrimaryKey, TimestampMixin, Base):
    """Le foyer : unite de facturation, de contenu et de reglages."""

    __tablename__ = "families"

    name: Mapped[str] = mapped_column(String(120))
    country_code: Mapped[str] = mapped_column(String(2), default="FR", index=True)
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Paris")
    locale: Mapped[str] = mapped_column(String(8), default="fr-FR")
    settings: Mapped[dict[str, Any]] = mapped_column(default=dict)

    parents: Mapped[list[Parent]] = relationship(
        back_populates="family", cascade="all, delete-orphan"
    )
    children: Mapped[list[Child]] = relationship(
        back_populates="family", cascade="all, delete-orphan"
    )
    policies: Mapped[list[PolicyProfile]] = relationship(
        back_populates="family", cascade="all, delete-orphan"
    )
    calendar: Mapped[list[CalendarPeriod]] = relationship(
        back_populates="family", cascade="all, delete-orphan"
    )


class Parent(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "parents"
    __table_args__ = (
        UniqueConstraint("email", name="uq_parents_email"),
        Index("ix_parents_phone", "phone"),
    )

    family_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("families.id", ondelete="CASCADE"), index=True
    )
    email: Mapped[str] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(32), default=None)
    display_name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str | None] = mapped_column(Text, default=None)
    firebase_uid: Mapped[str | None] = mapped_column(String(128), default=None, index=True)
    role: Mapped[ParentRole] = mapped_column(enum_column(ParentRole), default=ParentRole.OWNER)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(default=None)
    notification_prefs: Mapped[dict[str, Any]] = mapped_column(default=dict)

    family: Mapped[Family] = relationship(back_populates="parents")

    @property
    def can_write(self) -> bool:
        return self.role in (ParentRole.OWNER, ParentRole.GUARDIAN)


class Child(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "children"

    family_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("families.id", ondelete="CASCADE"), index=True
    )
    display_name: Mapped[str] = mapped_column(String(120))
    birth_date: Mapped[date | None] = mapped_column(Date, default=None)
    country_code: Mapped[str] = mapped_column(String(2), default="FR", index=True)
    grade_code: Mapped[str] = mapped_column(String(16), index=True)  # CP, CE2, 6E...
    avatar: Mapped[str] = mapped_column(String(64), default="fox")
    pin_hash: Mapped[str | None] = mapped_column(Text, default=None)
    xp_balance: Mapped[int] = mapped_column(Integer, default=0)
    xp_lifetime: Mapped[int] = mapped_column(Integer, default=0)
    streak_days: Mapped[int] = mapped_column(Integer, default=0)
    last_activity_on: Mapped[date | None] = mapped_column(Date, default=None)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    profile: Mapped[dict[str, Any]] = mapped_column(default=dict)

    family: Mapped[Family] = relationship(back_populates="children")
    devices: Mapped[list[Device]] = relationship(
        back_populates="child", cascade="all, delete-orphan"
    )
    assessments: Mapped[list[Assessment]] = relationship(
        back_populates="child", cascade="all, delete-orphan"
    )
    unlock_codes: Mapped[list[UnlockCode]] = relationship(
        back_populates="child", cascade="all, delete-orphan"
    )
    screen_sessions: Mapped[list[ScreenSession]] = relationship(
        back_populates="child", cascade="all, delete-orphan"
    )
    lockouts: Mapped[list[Lockout]] = relationship(
        back_populates="child", cascade="all, delete-orphan"
    )
    xp_entries: Mapped[list[XPLedgerEntry]] = relationship(
        back_populates="child", cascade="all, delete-orphan"
    )
    mastery: Mapped[list[Mastery]] = relationship(
        back_populates="child", cascade="all, delete-orphan"
    )


class RefreshToken(UUIDPrimaryKey, TimestampMixin, Base):
    """Jetons de rafraichissement revocables (rotation a chaque usage)."""

    __tablename__ = "refresh_tokens"

    parent_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("parents.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime]
    revoked_at: Mapped[datetime | None] = mapped_column(default=None)
    replaced_by: Mapped[uuid.UUID | None] = mapped_column(UUIDType, default=None)
    user_agent: Mapped[str | None] = mapped_column(String(255), default=None)
