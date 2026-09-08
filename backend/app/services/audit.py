"""Journal d'audit chaine par hachage.

Chaque evenement embarque l'empreinte du precedent. Supprimer ou modifier une
ligne (une tentative de triche, une revocation de code) casse la chaine, ce que
`verify_chain` revele immediatement. C'est la garantie donnee au parent que
l'historique affiche est bien l'historique reel.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditEvent

GENESIS = "0" * 64


def compute_hash(
    *,
    seq: int,
    family_id: uuid.UUID,
    actor_type: str,
    actor_id: uuid.UUID | None,
    action: str,
    target_type: str | None,
    target_id: uuid.UUID | None,
    payload: dict[str, Any],
    prev_hash: str,
) -> str:
    canonical = json.dumps(
        {
            "seq": seq,
            "family_id": str(family_id),
            "actor_type": actor_type,
            "actor_id": str(actor_id) if actor_id else None,
            "action": action,
            "target_type": target_type,
            "target_id": str(target_id) if target_id else None,
            "payload": payload,
            "prev": prev_hash,
        },
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


async def record(
    db: AsyncSession,
    *,
    family_id: uuid.UUID,
    action: str,
    actor_type: str = "system",
    actor_id: uuid.UUID | None = None,
    target_type: str | None = None,
    target_id: uuid.UUID | None = None,
    payload: dict[str, Any] | None = None,
) -> AuditEvent:
    payload = payload or {}
    last = (
        await db.execute(
            select(AuditEvent)
            .where(AuditEvent.family_id == family_id)
            .order_by(AuditEvent.seq.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    seq = (last.seq + 1) if last else 1
    prev_hash = last.hash if last else GENESIS

    event = AuditEvent(
        family_id=family_id,
        seq=seq,
        actor_type=actor_type,
        actor_id=actor_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        payload=payload,
        prev_hash=prev_hash,
        hash=compute_hash(
            seq=seq,
            family_id=family_id,
            actor_type=actor_type,
            actor_id=actor_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            payload=payload,
            prev_hash=prev_hash,
        ),
    )
    db.add(event)
    await db.flush()
    return event


async def verify_chain(db: AsyncSession, family_id: uuid.UUID) -> dict[str, Any]:
    """Revalide toute la chaine d'un foyer."""
    events = list(
        (
            await db.execute(
                select(AuditEvent)
                .where(AuditEvent.family_id == family_id)
                .order_by(AuditEvent.seq.asc())
            )
        ).scalars()
    )
    expected_prev = GENESIS
    for index, event in enumerate(events):
        recomputed = compute_hash(
            seq=event.seq,
            family_id=event.family_id,
            actor_type=event.actor_type,
            actor_id=event.actor_id,
            action=event.action,
            target_type=event.target_type,
            target_id=event.target_id,
            payload=event.payload,
            prev_hash=event.prev_hash,
        )
        if event.prev_hash != expected_prev or recomputed != event.hash:
            return {
                "valid": False,
                "checked": index + 1,
                "total": len(events),
                "broken_at_seq": event.seq,
                "reason": (
                    "chainage rompu" if event.prev_hash != expected_prev else "contenu modifie"
                ),
            }
        expected_prev = event.hash
    return {"valid": True, "checked": len(events), "total": len(events), "head": expected_prev}


async def count_events(db: AsyncSession, family_id: uuid.UUID) -> int:
    return int(
        await db.scalar(select(func.count(AuditEvent.id)).where(AuditEvent.family_id == family_id))
        or 0
    )
