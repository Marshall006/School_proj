"""Evaluations : lancement, sauvegarde des reponses, correction, historique."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Query
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import (
    CurrentDevice,
    CurrentParent,
    CurrentWriter,
    DbSession,
    DeviceChild,
    load_child,
)
from app.core.errors import ConflictError, NotFoundError, PermissionDeniedError
from app.models.assessment import Assessment
from app.models.device import Device
from app.models.enums import AssessmentKind, AssessmentStatus, DeviceStatus
from app.models.family import Child
from app.schemas.assessment import (
    AssessmentItemOut,
    AssessmentOut,
    AssessmentSummaryOut,
    EligibilityOut,
    ManualGradeRequest,
    SaveAnswerRequest,
    StartAssessmentRequest,
    SubmissionOut,
    SubmitRequest,
)
from app.services import assessment as svc
from app.services.policy import resolve_policy

router = APIRouter(tags=["Evaluations"])


def _serialize(assessment: Assessment, *, include_answers: bool = True) -> AssessmentOut:
    """Vue enfant d'une epreuve : enonces seulement, jamais le corrige."""
    items = []
    for item in sorted(assessment.items, key=lambda i: i.position):
        snapshot = item.snapshot or {}
        items.append(
            AssessmentItemOut(
                id=item.id,
                position=item.position,
                type=item.question_type.value,
                difficulty=item.difficulty,
                prompt=snapshot.get("prompt", ""),
                instructions=snapshot.get("instructions"),
                choices=snapshot.get("choices"),
                assets=snapshot.get("assets") or [],
                input_spec=snapshot.get("input_spec") or {},
                points_max=item.points_max,
                estimated_seconds=snapshot.get("estimated_seconds", 45),
                subject_code=item.subject_code,
                answered=item.answer is not None,
                answer=item.answer if include_answers else None,
                answer_mode=item.answer_mode.value if item.answer_mode else None,
            )
        )
    blueprint = assessment.blueprint or {}
    time_limit = None
    if assessment.expires_at and assessment.started_at:
        time_limit = int((assessment.expires_at - assessment.started_at).total_seconds())
    return AssessmentOut(
        id=assessment.id,
        child_id=assessment.child_id,
        kind=assessment.kind.value,
        status=assessment.status.value,
        question_count=assessment.question_count,
        points_max=assessment.points_max,
        pass_score_pct=assessment.pass_score_pct,
        pass_score_out_of_20=round(assessment.pass_score_pct * 0.2, 2),
        started_at=assessment.started_at,
        expires_at=assessment.expires_at,
        time_limit_seconds=time_limit,
        items=items,
        blueprint_distribution=blueprint.get("distribution", {}),
    )


async def _child_and_device(db: DbSession, device: Device, child: Child) -> tuple[Child, Device]:
    return child, device


# ---------------------------------------------------------------------------
# Cote enfant (jeton appareil)
# ---------------------------------------------------------------------------


@router.get("/assessments/eligibility", response_model=EligibilityOut)
async def eligibility(
    db: DbSession,
    device: CurrentDevice,
    child: DeviceChild,
    kind: AssessmentKind = AssessmentKind.UNLOCK,
) -> EligibilityOut:
    """L'enfant peut-il lancer une evaluation maintenant ? (et sinon, pourquoi)"""
    policy = await resolve_policy(db, child)
    report = await svc.check_eligibility(db, child, policy, kind=kind)
    used = await svc.attempts_today(db, child.id, kind=kind)
    return EligibilityOut(
        allowed=report.allowed,
        reason=report.reason,
        details=report.details,
        policy=policy.to_dict(),
        attempts_today=used,
        max_attempts_per_day=policy.max_attempts_per_day,
    )


@router.post("/assessments", response_model=AssessmentOut, status_code=201)
async def start(
    db: DbSession,
    device: CurrentDevice,
    child: DeviceChild,
    payload: StartAssessmentRequest,
) -> AssessmentOut:
    """Compose une epreuve adaptee et l'ouvre."""
    policy = await resolve_policy(db, child)
    assessment = await svc.start_assessment(
        db,
        child=child,
        policy=policy,
        device=device,
        kind=payload.kind,
        question_count=payload.question_count,
        seed=payload.seed,
    )
    await db.commit()
    loaded = await svc.get_assessment(db, assessment.id)
    return _serialize(loaded)


@router.get("/assessments/current", response_model=AssessmentOut | None)
async def current(db: DbSession, device: CurrentDevice, child: DeviceChild) -> Any:
    """Reprise apres coupure : l'epreuve en cours, avec les reponses deja saisies."""
    assessment = (
        await db.execute(
            select(Assessment)
            .where(
                Assessment.child_id == child.id,
                Assessment.status == AssessmentStatus.IN_PROGRESS,
            )
            .options(selectinload(Assessment.items))
            .order_by(Assessment.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    return _serialize(assessment) if assessment else None


@router.get("/assessments/{assessment_id}", response_model=AssessmentOut)
async def get_one(
    db: DbSession, device: CurrentDevice, child: DeviceChild, assessment_id: uuid.UUID
) -> AssessmentOut:
    assessment = await svc.get_assessment(db, assessment_id)
    if assessment.child_id != child.id:
        raise PermissionDeniedError("Cette évaluation ne concerne pas cet enfant.")
    return _serialize(assessment)


@router.patch("/assessments/{assessment_id}/items/{item_id}", status_code=204)
async def save_answer(
    db: DbSession,
    device: CurrentDevice,
    child: DeviceChild,
    assessment_id: uuid.UUID,
    item_id: uuid.UUID,
    payload: SaveAnswerRequest,
) -> None:
    """Sauvegarde continue : rien n'est perdu si la tablette s'eteint."""
    assessment = await svc.get_assessment(db, assessment_id)
    if assessment.child_id != child.id:
        raise PermissionDeniedError("Cette évaluation ne concerne pas cet enfant.")
    item = next((i for i in assessment.items if i.id == item_id), None)
    if item is None:
        raise NotFoundError("Question introuvable dans cette évaluation.")

    await svc.save_answer(
        db,
        assessment,
        item,
        answer=payload.answer,
        answer_mode=payload.answer_mode,
        strokes=payload.strokes,
        scratchpad=payload.scratchpad,
        time_spent_ms=payload.time_spent_ms,
    )
    await db.commit()


@router.post("/assessments/{assessment_id}/submit", response_model=SubmissionOut)
async def submit(
    db: DbSession,
    device: CurrentDevice,
    child: DeviceChild,
    assessment_id: uuid.UUID,
    payload: SubmitRequest,
) -> SubmissionOut:
    """Corrige l'epreuve et delivre le code, ou ouvre le temps de carence."""
    assessment = await svc.get_assessment(db, assessment_id)
    if assessment.child_id != child.id:
        raise PermissionDeniedError("Cette évaluation ne concerne pas cet enfant.")

    if payload.answers:
        for item_id, answer in payload.answers.items():
            item = next((i for i in assessment.items if i.id == item_id), None)
            if item is None:
                continue
            await svc.save_answer(
                db,
                assessment,
                item,
                answer=answer.answer,
                answer_mode=answer.answer_mode,
                strokes=answer.strokes,
                scratchpad=answer.scratchpad,
                time_spent_ms=answer.time_spent_ms,
            )
    if payload.integrity:
        assessment.integrity = payload.integrity

    policy = await resolve_policy(db, child)
    result = await svc.submit_assessment(
        db, child=child, assessment=assessment, policy=policy, device=device
    )
    await db.commit()
    return SubmissionOut(**result.to_dict())


@router.get("/assessments/{assessment_id}/review", response_model=SubmissionOut)
async def review(
    db: DbSession, device: CurrentDevice, child: DeviceChild, assessment_id: uuid.UUID
) -> SubmissionOut:
    """Correction detaillee : accessible meme (et surtout) en cas d'echec."""
    assessment = await svc.get_assessment(db, assessment_id)
    if assessment.child_id != child.id:
        raise PermissionDeniedError("Cette évaluation ne concerne pas cet enfant.")
    if assessment.status == AssessmentStatus.IN_PROGRESS:
        raise ConflictError("L'évaluation n'est pas encore terminée.")
    return SubmissionOut(
        assessment_id=assessment.id,
        status=assessment.status.value,
        passed=bool(assessment.passed),
        pending_manual_review=assessment.status == AssessmentStatus.NEEDS_REVIEW,
        score_pct=assessment.score_pct or 0.0,
        score_out_of_20=assessment.score_out_of_20 or 0.0,
        pass_score_pct=assessment.pass_score_pct,
        pass_score_out_of_20=round(assessment.pass_score_pct * 0.2, 2),
        points_earned=assessment.points_earned,
        points_max=assessment.points_max,
        unlock_code=None,  # un code ne se reaffiche jamais
        lockout=None,
        xp_earned=assessment.xp_earned,
        review=svc._review_payload(assessment),
    )


# ---------------------------------------------------------------------------
# Cote parent
# ---------------------------------------------------------------------------


@router.get("/children/{child_id}/assessments", response_model=list[AssessmentSummaryOut])
async def history(
    db: DbSession,
    parent: CurrentParent,
    child_id: uuid.UUID,
    limit: int = Query(default=20, ge=1, le=100),
) -> list[Assessment]:
    child = await load_child(db, parent, child_id)
    return list(
        (
            await db.execute(
                select(Assessment)
                .where(Assessment.child_id == child.id)
                .order_by(Assessment.created_at.desc())
                .limit(limit)
            )
        ).scalars()
    )


@router.get("/parent/assessments/pending-review", response_model=list[AssessmentSummaryOut])
async def pending_review(db: DbSession, parent: CurrentParent) -> list[Assessment]:
    """Copies en attente d'une validation parentale (reponses manuscrites)."""
    return list(
        (
            await db.execute(
                select(Assessment)
                .join(Child, Child.id == Assessment.child_id)
                .where(
                    Child.family_id == parent.family_id,
                    Assessment.status == AssessmentStatus.NEEDS_REVIEW,
                )
                .order_by(Assessment.submitted_at.desc())
            )
        ).scalars()
    )


@router.get("/parent/assessments/{assessment_id}")
async def parent_view(
    db: DbSession, parent: CurrentParent, assessment_id: uuid.UUID
) -> dict[str, Any]:
    """Copie complete vue par le parent : reponses, corrections, ardoise."""
    assessment = await svc.get_assessment(db, assessment_id)
    await load_child(db, parent, assessment.child_id)
    return {
        "assessment": {
            "id": str(assessment.id),
            "kind": assessment.kind.value,
            "status": assessment.status.value,
            "score_out_of_20": assessment.score_out_of_20,
            "passed": assessment.passed,
            "points_earned": assessment.points_earned,
            "points_max": assessment.points_max,
            "pass_score_out_of_20": round(assessment.pass_score_pct * 0.2, 2),
            "duration_seconds": assessment.duration_seconds,
            "created_at": assessment.created_at.isoformat(),
            "blueprint": assessment.blueprint,
            "integrity": assessment.integrity,
        },
        "items": [
            {
                "id": str(item.id),
                "position": item.position,
                "prompt": (item.snapshot or {}).get("prompt"),
                "type": item.question_type.value,
                "subject_code": item.subject_code,
                "answer": item.answer,
                "answer_mode": item.answer_mode.value if item.answer_mode else None,
                "strokes": item.strokes,
                "is_correct": item.is_correct,
                "score": item.score,
                "points": f"{item.points_awarded}/{item.points_max}",
                "feedback": item.feedback,
                "needs_manual_review": item.needs_manual_review,
                "parent_comment": item.parent_comment,
                "time_spent_ms": item.time_spent_ms,
            }
            for item in sorted(assessment.items, key=lambda i: i.position)
        ],
    }


@router.post(
    "/parent/assessments/{assessment_id}/items/{item_id}/grade",
    response_model=SubmissionOut | None,
)
async def manual_grade(
    db: DbSession,
    parent: CurrentWriter,
    assessment_id: uuid.UUID,
    item_id: uuid.UUID,
    payload: ManualGradeRequest,
) -> Any:
    """Le parent tranche une reponse manuscrite ; l'epreuve se conclut si c'etait la derniere."""
    assessment = await svc.get_assessment(db, assessment_id)
    child = await load_child(db, parent, assessment.child_id)
    item = next((i for i in assessment.items if i.id == item_id), None)
    if item is None:
        raise NotFoundError("Question introuvable.")

    policy = await resolve_policy(db, child)
    device = None
    if assessment.device_id:
        candidate = await db.get(Device, assessment.device_id)
        if candidate and candidate.status == DeviceStatus.ACTIVE:
            device = candidate

    result = await svc.manual_grade_item(
        db,
        child=child,
        assessment=assessment,
        item=item,
        score=payload.score,
        parent_id=parent.id,
        policy=policy,
        comment=payload.comment,
        device=device,
    )
    await db.commit()
    return SubmissionOut(**result.to_dict()) if result else None


@router.post(
    "/parent/children/{child_id}/assessments", response_model=AssessmentOut, status_code=201
)
async def assign_assessment(
    db: DbSession,
    parent: CurrentWriter,
    child_id: uuid.UUID,
    payload: StartAssessmentRequest,
) -> AssessmentOut:
    """Le parent pousse une evaluation : "montre-moi que la lecon est sue"."""
    child = await load_child(db, parent, child_id)
    policy = await resolve_policy(db, child)
    assessment = await svc.start_assessment(
        db,
        child=child,
        policy=policy,
        kind=payload.kind,
        question_count=payload.question_count,
        seed=payload.seed,
        assigned_by_parent_id=parent.id,
    )
    await db.commit()
    loaded = await svc.get_assessment(db, assessment.id)
    return _serialize(loaded)
