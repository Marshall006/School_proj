"""Socle SQLAlchemy : types portables PostgreSQL <-> SQLite et mixins communs."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, MetaData, TypeDecorator, Uuid
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class UTCDateTime(TypeDecorator):
    """Force l'aller-retour en UTC, y compris sur SQLite (qui perd le fuseau)."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Any) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    def process_result_value(self, value: datetime | None, dialect: Any) -> datetime | None:
        if value is None:
            return None
        return value if value.tzinfo else value.replace(tzinfo=UTC)


#: JSONB sur PostgreSQL (indexable), JSON standard ailleurs.
JSONType = JSON().with_variant(JSONB, "postgresql")

#: UUID natif sur PostgreSQL, CHAR(32) ailleurs - toujours rendu en `uuid.UUID`.
UUIDType = Uuid(as_uuid=True)


def enum_column(python_enum: type, **kwargs: Any) -> SAEnum:
    """Enumeration stockee en VARCHAR + contrainte CHECK : migrations indolores."""
    return SAEnum(
        python_enum,
        native_enum=False,
        length=40,
        values_callable=lambda e: [m.value for m in e],
        validate_strings=True,
        **kwargs,
    )


def utc_now() -> datetime:
    """Import tardif : l'horloge applicative est deplacable en test."""
    from app.core.clock import now

    return now()


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    type_annotation_map = {
        datetime: UTCDateTime,
        uuid.UUID: UUIDType,
        dict[str, Any]: JSONType,
        list[Any]: JSONType,
    }

    def __repr__(self) -> str:  # pragma: no cover - confort de debug
        return f"<{type(self).__name__} {getattr(self, 'id', None)}>"


class UUIDPrimaryKey:
    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(default=utc_now, index=True)
    updated_at: Mapped[datetime] = mapped_column(default=utc_now, onupdate=utc_now)
