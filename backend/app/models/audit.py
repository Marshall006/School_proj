"""Journal d'audit chaine : toute action sensible est infalsifiable a posteriori."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import BigInteger, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKey, UUIDType


class AuditEvent(UUIDPrimaryKey, TimestampMixin, Base):
    """Chaque evenement contient l'empreinte du precedent (chaine de hachage).

    Un enfant qui obtiendrait un acces a la base ne peut pas effacer une
    tentative de triche sans casser la chaine, ce que `verify_chain` detecte.
    """

    __tablename__ = "audit_events"
    __table_args__ = (Index("ix_audit_family_seq", "family_id", "seq"),)

    family_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("families.id", ondelete="CASCADE"), index=True
    )
    seq: Mapped[int] = mapped_column(BigInteger)
    actor_type: Mapped[str] = mapped_column(String(24))  # parent | child | device | system
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUIDType, default=None)
    action: Mapped[str] = mapped_column(String(64), index=True)
    target_type: Mapped[str | None] = mapped_column(String(40), default=None)
    target_id: Mapped[uuid.UUID | None] = mapped_column(UUIDType, default=None)
    payload: Mapped[dict[str, Any]] = mapped_column(default=dict)
    prev_hash: Mapped[str] = mapped_column(String(64), default="0" * 64)
    hash: Mapped[str] = mapped_column(String(64))
