"""Enfants, regles du foyer, calendrier scolaire et tableau de bord."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.api.deps import CurrentParent, CurrentWriter, DbSession, load_child
from app.core.errors import ConflictError, NotFoundError
from app.core.security import hash_pin
from app.models.family import Child, Family
from app.models.policy import CalendarPeriod, PolicyProfile
from app.schemas.family import (
    CalendarPeriodIn,
    CalendarPeriodOut,
    ChildCreate,
    ChildOut,
    ChildUpdate,
    EffectivePolicyOut,
    PolicyIn,
    PolicyOut,
)
from app.services import analytics, audit, lockouts
from app.services.policy import resolve_policy

router = APIRouter(tags=["Enfants et regles"])


# ---------------------------------------------------------------------------
# Enfants
# ---------------------------------------------------------------------------


@router.post("/children", response_model=ChildOut, status_code=201)
async def create_child(db: DbSession, parent: CurrentWriter, payload: ChildCreate) -> Child:
    family = await db.get(Family, parent.family_id)
    child = Child(
        family_id=parent.family_id,
        display_name=payload.display_name,
        grade_code=payload.grade_code,
        country_code=payload.country_code or (family.country_code if family else "FR"),
        birth_date=payload.birth_date,
        avatar=payload.avatar,
        pin_hash=hash_pin(payload.pin) if payload.pin else None,
    )
    db.add(child)
    await db.flush()
    await audit.record(
        db,
        family_id=parent.family_id,
        action="child.created",
        actor_type="parent",
        actor_id=parent.id,
        target_type="child",
        target_id=child.id,
        payload={"grade_code": child.grade_code, "country_code": child.country_code},
    )
    await db.commit()
    return child


@router.get("/children", response_model=list[ChildOut])
async def list_children(db: DbSession, parent: CurrentParent) -> list[Child]:
    return list(
        (
            await db.execute(
                select(Child).where(Child.family_id == parent.family_id).order_by(Child.created_at)
            )
        ).scalars()
    )


@router.get("/children/{child_id}", response_model=ChildOut)
async def get_child(db: DbSession, parent: CurrentParent, child_id: uuid.UUID) -> Child:
    return await load_child(db, parent, child_id)


@router.patch("/children/{child_id}", response_model=ChildOut)
async def update_child(
    db: DbSession, parent: CurrentWriter, child_id: uuid.UUID, payload: ChildUpdate
) -> Child:
    child = await load_child(db, parent, child_id)
    data = payload.model_dump(exclude_unset=True)
    if "pin" in data:
        pin = data.pop("pin")
        child.pin_hash = hash_pin(pin) if pin else None
    for field, value in data.items():
        setattr(child, field, value.upper() if field in {"grade_code", "country_code"} else value)
    await audit.record(
        db,
        family_id=parent.family_id,
        action="child.updated",
        actor_type="parent",
        actor_id=parent.id,
        target_type="child",
        target_id=child.id,
        payload={"fields": sorted(data)},
    )
    await db.commit()
    return child


@router.delete("/children/{child_id}", status_code=204)
async def deactivate_child(db: DbSession, parent: CurrentWriter, child_id: uuid.UUID) -> None:
    child = await load_child(db, parent, child_id)
    child.is_active = False
    await audit.record(
        db,
        family_id=parent.family_id,
        action="child.deactivated",
        actor_type="parent",
        actor_id=parent.id,
        target_type="child",
        target_id=child.id,
    )
    await db.commit()


# ---------------------------------------------------------------------------
# Tableau de bord
# ---------------------------------------------------------------------------


@router.get("/children/{child_id}/dashboard")
async def child_dashboard(
    db: DbSession, parent: CurrentParent, child_id: uuid.UUID
) -> dict[str, Any]:
    """Toutes les metriques d'un enfant en un seul appel."""
    child = await load_child(db, parent, child_id)
    policy = await resolve_policy(db, child)
    return await analytics.build_dashboard(db, child, policy)


@router.get("/children/{child_id}/status")
async def child_status(db: DbSession, parent: CurrentParent, child_id: uuid.UUID) -> dict[str, Any]:
    """Etat instantane (verrouille / deverrouille, carence, temps restant)."""
    child = await load_child(db, parent, child_id)
    policy = await resolve_policy(db, child)
    return await analytics.child_status(db, child, policy)


@router.get("/children/{child_id}/lockout")
async def get_lockout(
    db: DbSession, parent: CurrentParent, child_id: uuid.UUID
) -> dict[str, Any] | None:
    """Temps de carence en cours, s'il y en a un."""
    child = await load_child(db, parent, child_id)
    lockout = await lockouts.active_lockout(db, child.id)
    return lockouts.describe(lockout) if lockout else None


@router.post("/children/{child_id}/lockout/release")
async def release_lockout(
    db: DbSession, parent: CurrentWriter, child_id: uuid.UUID
) -> dict[str, Any]:
    """Le parent leve la carence : il garde toujours le dernier mot.

    Utile quand l'enfant a revise avec un adulte et peut retenter tout de suite.
    """
    child = await load_child(db, parent, child_id)
    lockout = await lockouts.active_lockout(db, child.id)
    if lockout is None:
        return {"released": False, "message": "Aucun temps de carence en cours."}
    await lockouts.release_lockout(db, lockout, parent_id=parent.id)
    await audit.record(
        db,
        family_id=parent.family_id,
        action="lockout.released",
        actor_type="parent",
        actor_id=parent.id,
        target_type="lockout",
        target_id=lockout.id,
    )
    await db.commit()
    return {"released": True, "lockout_id": str(lockout.id)}


@router.get("/family/overview")
async def family_overview(db: DbSession, parent: CurrentParent) -> dict[str, Any]:
    return await analytics.family_overview(db, parent.family_id)


@router.get("/family/audit")
async def family_audit(
    db: DbSession,
    parent: CurrentParent,
    verify: bool = Query(default=False, description="Revalide la chaine de hachage"),
) -> dict[str, Any]:
    """Journal d'audit du foyer, avec verification d'integrite a la demande."""
    result: dict[str, Any] = {"events": await audit.count_events(db, parent.family_id)}
    if verify:
        result["integrity"] = await audit.verify_chain(db, parent.family_id)
    return result


# ---------------------------------------------------------------------------
# Regles
# ---------------------------------------------------------------------------


@router.get("/children/{child_id}/policy", response_model=EffectivePolicyOut)
async def effective_policy(
    db: DbSession, parent: CurrentParent, child_id: uuid.UUID
) -> EffectivePolicyOut:
    """Regles reellement appliquees maintenant (apres resolution de la periode)."""
    child = await load_child(db, parent, child_id)
    policy = await resolve_policy(db, child)
    return EffectivePolicyOut(**policy.to_dict())


@router.get("/policies", response_model=list[PolicyOut])
async def list_policies(db: DbSession, parent: CurrentParent) -> list[PolicyProfile]:
    return list(
        (
            await db.execute(
                select(PolicyProfile)
                .where(PolicyProfile.family_id == parent.family_id)
                .order_by(PolicyProfile.period_type)
            )
        ).scalars()
    )


@router.put("/policies", response_model=PolicyOut)
async def upsert_policy(db: DbSession, parent: CurrentWriter, payload: PolicyIn) -> PolicyProfile:
    """Cree ou met a jour le profil de regles pour une periode (et un enfant)."""
    if payload.child_id:
        await load_child(db, parent, payload.child_id)

    profile = (
        await db.execute(
            select(PolicyProfile).where(
                PolicyProfile.family_id == parent.family_id,
                PolicyProfile.child_id == payload.child_id,
                PolicyProfile.period_type == payload.period_type,
            )
        )
    ).scalar_one_or_none()

    if profile is None:
        profile = PolicyProfile(
            family_id=parent.family_id,
            child_id=payload.child_id,
            period_type=payload.period_type,
            name=payload.name,
        )
        db.add(profile)

    for field, value in payload.model_dump(
        exclude_unset=True, exclude={"child_id", "period_type"}
    ).items():
        if value is not None:
            setattr(profile, field, value)

    await db.flush()
    await audit.record(
        db,
        family_id=parent.family_id,
        action="policy.updated",
        actor_type="parent",
        actor_id=parent.id,
        target_type="policy",
        target_id=profile.id,
        payload={
            "period_type": payload.period_type.value,
            "child_id": str(payload.child_id) if payload.child_id else None,
        },
    )
    await db.commit()
    return profile


@router.delete("/policies/{policy_id}", status_code=204)
async def delete_policy(db: DbSession, parent: CurrentWriter, policy_id: uuid.UUID) -> None:
    profile = await db.get(PolicyProfile, policy_id)
    if profile is None or profile.family_id != parent.family_id:
        raise NotFoundError("Profil de regles introuvable.")
    await db.delete(profile)
    await db.commit()


# ---------------------------------------------------------------------------
# Calendrier (vacances / periode scolaire)
# ---------------------------------------------------------------------------


@router.get("/calendar", response_model=list[CalendarPeriodOut])
async def list_calendar(db: DbSession, parent: CurrentParent) -> list[CalendarPeriod]:
    return list(
        (
            await db.execute(
                select(CalendarPeriod)
                .where(CalendarPeriod.family_id == parent.family_id)
                .order_by(CalendarPeriod.start_date)
            )
        ).scalars()
    )


@router.post("/calendar", response_model=CalendarPeriodOut, status_code=201)
async def add_calendar_period(
    db: DbSession, parent: CurrentWriter, payload: CalendarPeriodIn
) -> CalendarPeriod:
    overlapping = (
        (
            await db.execute(
                select(CalendarPeriod).where(
                    CalendarPeriod.family_id == parent.family_id,
                    CalendarPeriod.start_date <= payload.end_date,
                    CalendarPeriod.end_date >= payload.start_date,
                )
            )
        )
        .scalars()
        .first()
    )
    if overlapping is not None:
        raise ConflictError(
            f'Cette periode chevauche "{overlapping.label}".',
            details={"conflict_id": str(overlapping.id)},
        )

    period = CalendarPeriod(family_id=parent.family_id, **payload.model_dump())
    db.add(period)
    await db.commit()
    return period


@router.delete("/calendar/{period_id}", status_code=204)
async def delete_calendar_period(
    db: DbSession, parent: CurrentWriter, period_id: uuid.UUID
) -> None:
    period = await db.get(CalendarPeriod, period_id)
    if period is None or period.family_id != parent.family_id:
        raise NotFoundError("Période introuvable.")
    await db.delete(period)
    await db.commit()
