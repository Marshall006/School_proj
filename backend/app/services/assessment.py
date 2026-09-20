"""Orchestration des evaluations : composer, corriger, recompenser ou sanctionner.

C'est ici que se joue le coeur du produit :

1. verifier qu'une tentative est permise (carence, quota du jour, regles) ;
2. composer une epreuve equilibree avec le moteur adaptatif ;
3. corriger, y compris avec credit partiel et diagnostic pedagogique ;
4. delivrer le code d'acces **ou** ouvrir le temps de carence avec la
   correction detaillee et la liste des notions a revoir.

Cas particulier soigne : si une reponse manuscrite attend la validation d'un
parent, on ne bloque pas l'enfant pour autant. Si le score deja acquis suffit,
il obtient son code immediatement ; si meme le meilleur des cas ne suffit pas,
l'echec est prononce tout de suite ; entre les deux seulement, on attend.
"""

from __future__ import annotations

import random
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core import unlock_protocol as proto
from app.core.clock import now as clock_now
from app.core.errors import (
    ConflictError,
    CooldownActiveError,
    NoContentAvailableError,
    NotFoundError,
    PolicyForbidsError,
)
from app.models.access import UnlockCode
from app.models.assessment import Assessment, AssessmentItem
from app.models.content import Question, Subject, Topic
from app.models.device import Device
from app.models.enums import (
    AnswerMode,
    AssessmentKind,
    AssessmentStatus,
    LockoutReason,
    QuestionType,
)
from app.models.family import Child
from app.models.progress import Mastery
from app.services import adaptive, audit, grading, lockouts, unlock, xp
from app.services.policy import EffectivePolicy

RECENT_WINDOW = 40  # items recemment vus, evites en priorite


# ---------------------------------------------------------------------------
# Resultats
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class SubmissionResult:
    assessment: Assessment
    passed: bool
    pending_manual_review: bool
    score_pct: float
    score_out_of_20: float
    issued_code: unlock.IssuedCode | None
    lockout: Any | None
    xp_total: int
    xp_grants: list[xp.XPGrant]
    review: list[dict[str, Any]]
    weak_topics: list[dict[str, Any]] = field(default_factory=list)
    mastery_moves: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "assessment_id": str(self.assessment.id),
            "status": self.assessment.status.value,
            "passed": self.passed,
            "pending_manual_review": self.pending_manual_review,
            "score_pct": round(self.score_pct, 2),
            "score_out_of_20": round(self.score_out_of_20, 2),
            "pass_score_pct": self.assessment.pass_score_pct,
            "pass_score_out_of_20": round(self.assessment.pass_score_pct * 0.2, 2),
            "points_earned": round(self.assessment.points_earned, 2),
            "points_max": round(self.assessment.points_max, 2),
            "unlock_code": self.issued_code.to_dict() if self.issued_code else None,
            "lockout": lockouts.describe(self.lockout) if self.lockout else None,
            "xp_earned": self.xp_total,
            "xp_detail": [
                {"amount": g.amount, "reason": g.reason.value, "label": g.label}
                for g in self.xp_grants
            ],
            "review": self.review,
            "weak_topics": self.weak_topics,
            "mastery_moves": self.mastery_moves,
        }


@dataclass(slots=True)
class EligibilityReport:
    allowed: bool
    reason: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Eligibilite
# ---------------------------------------------------------------------------


async def attempts_today(
    db: AsyncSession,
    child_id: uuid.UUID,
    *,
    kind: AssessmentKind = AssessmentKind.UNLOCK,
    at: datetime | None = None,
) -> int:
    at = at or clock_now()
    start = at.replace(hour=0, minute=0, second=0, microsecond=0)
    return int(
        await db.scalar(
            select(func.count(Assessment.id)).where(
                Assessment.child_id == child_id,
                Assessment.kind == kind,
                Assessment.created_at >= start,
            )
        )
        or 0
    )


async def failures_today(
    db: AsyncSession, child_id: uuid.UUID, *, at: datetime | None = None
) -> int:
    at = at or clock_now()
    start = at.replace(hour=0, minute=0, second=0, microsecond=0)
    return int(
        await db.scalar(
            select(func.count(Assessment.id)).where(
                Assessment.child_id == child_id,
                Assessment.passed.is_(False),
                Assessment.created_at >= start,
            )
        )
        or 0
    )


async def check_eligibility(
    db: AsyncSession,
    child: Child,
    policy: EffectivePolicy,
    *,
    kind: AssessmentKind = AssessmentKind.UNLOCK,
    at: datetime | None = None,
) -> EligibilityReport:
    """Peut-on lancer une evaluation maintenant ? (sans lever d'exception)"""
    at = at or clock_now()

    if kind == AssessmentKind.UNLOCK and not policy.allow_assessment_unlock:
        return EligibilityReport(
            False,
            "policy_forbids",
            {"message": "Le déverrouillage par évaluation est désactivé."},
        )

    blocking = await lockouts.active_lockout(db, child.id, at=at)
    if blocking and kind in (AssessmentKind.UNLOCK, AssessmentKind.PLACEMENT):
        return EligibilityReport(False, "cooldown_active", lockouts.describe(blocking, at))

    if kind == AssessmentKind.UNLOCK:
        used = await attempts_today(db, child.id, kind=kind, at=at)
        if used >= policy.max_attempts_per_day:
            return EligibilityReport(
                False,
                "too_many_attempts",
                {
                    "attempts_today": used,
                    "max_attempts_per_day": policy.max_attempts_per_day,
                    "message": "Nombre de tentatives du jour atteint.",
                },
            )

    return EligibilityReport(True)


# ---------------------------------------------------------------------------
# Composition
# ---------------------------------------------------------------------------


async def _topic_candidates(
    db: AsyncSession, child: Child, policy: EffectivePolicy
) -> list[adaptive.TopicCandidate]:
    """Notions du programme de l'enfant qui disposent reellement de questions."""
    query = (
        select(
            Topic.id,
            Subject.code,
            Topic.name,
            Topic.is_core,
            Topic.position,
            func.count(Question.id).label("question_count"),
        )
        .join(Subject, Subject.id == Topic.subject_id)
        .join(Question, (Question.topic_id == Topic.id) & (Question.is_active.is_(True)))
        .where(Topic.country_code == child.country_code, Topic.grade_code == child.grade_code)
        .group_by(Topic.id, Subject.code, Topic.name, Topic.is_core, Topic.position)
    )
    if policy.subject_codes:
        query = query.where(Subject.code.in_(policy.subject_codes))

    rows = (await db.execute(query)).all()
    return [
        adaptive.TopicCandidate(
            topic_id=row.id,
            subject_code=row.code,
            name=row.name,
            question_count=int(row.question_count),
            is_core=bool(row.is_core),
            position=int(row.position),
        )
        for row in rows
    ]


async def _mastery_states(
    db: AsyncSession, child_id: uuid.UUID
) -> dict[uuid.UUID, adaptive.MasteryState]:
    rows = list((await db.execute(select(Mastery).where(Mastery.child_id == child_id))).scalars())
    return {
        row.topic_id: adaptive.MasteryState(
            topic_id=row.topic_id,
            subject_code=row.subject_code,
            ability=row.ability,
            ewma=row.ewma,
            attempts=row.attempts,
            correct=row.correct,
            streak=row.streak,
            ease=row.ease,
            interval_days=row.interval_days,
            next_review_at=row.next_review_at,
            last_seen_at=row.last_seen_at,
        )
        for row in rows
    }


async def _recent_question_ids(db: AsyncSession, child_id: uuid.UUID) -> dict[uuid.UUID, int]:
    """Questions vues recemment, ponderees par fraicheur (1 = la plus recente)."""
    rows = (
        await db.execute(
            select(AssessmentItem.question_id)
            .join(Assessment, Assessment.id == AssessmentItem.assessment_id)
            .where(Assessment.child_id == child_id, AssessmentItem.question_id.is_not(None))
            .order_by(AssessmentItem.created_at.desc())
            .limit(RECENT_WINDOW)
        )
    ).all()
    ranks: dict[uuid.UUID, int] = {}
    for index, row in enumerate(rows):
        qid = row[0]
        if qid is not None and qid not in ranks:
            ranks[qid] = max(1, RECENT_WINDOW - index)
    return ranks


def _question_snapshot(question: Question) -> dict[str, Any]:
    """Enonce fige, **sans la correction** : le client ne recoit jamais la reponse."""
    return {
        "question_id": str(question.id),
        "type": question.type.value,
        "difficulty": question.difficulty,
        "prompt": question.prompt,
        "instructions": question.instructions,
        "choices": question.choices,
        "assets": question.assets,
        "input_spec": question.input_spec or {},
        "points": question.points,
        "estimated_seconds": question.estimated_seconds,
        "topic_id": str(question.topic_id),
        "tags": question.tags,
    }


async def start_assessment(
    db: AsyncSession,
    *,
    child: Child,
    policy: EffectivePolicy,
    device: Device | None = None,
    kind: AssessmentKind = AssessmentKind.UNLOCK,
    question_count: int | None = None,
    seed: int | None = None,
    at: datetime | None = None,
    assigned_by_parent_id: uuid.UUID | None = None,
) -> Assessment:
    """Compose et ouvre une epreuve."""
    at = at or clock_now()

    eligibility = await check_eligibility(db, child, policy, kind=kind, at=at)
    if not eligibility.allowed:
        if eligibility.reason == "cooldown_active":
            raise CooldownActiveError(
                "Tu dois attendre la fin du temps de carence pour retenter.",
                details=eligibility.details,
            )
        if eligibility.reason == "policy_forbids":
            raise PolicyForbidsError(
                eligibility.details.get("message", "Regle du foyer."), details=eligibility.details
            )
        raise ConflictError(
            eligibility.details.get("message", "Tentative impossible."),
            code=eligibility.reason or "not_eligible",
            details=eligibility.details,
        )

    # Une epreuve ouverte a la fois : on abandonne l'ancienne.
    for stale in await _open_assessments(db, child.id):
        stale.status = AssessmentStatus.ABANDONED

    candidates = await _topic_candidates(db, child, policy)
    if not candidates:
        raise NoContentAvailableError(
            "Aucune question disponible pour ce niveau et ces matieres.",
            details={
                "country_code": child.country_code,
                "grade_code": child.grade_code,
                "subject_codes": policy.subject_codes,
            },
        )

    mastery = await _mastery_states(db, child.id)
    count = question_count or policy.question_count
    blueprint = adaptive.build_blueprint(
        candidates=candidates,
        mastery=mastery,
        question_count=count,
        difficulty_bias=policy.difficulty_bias,
        seed=seed,
        at=at,
    )

    topic_ids = {slot.topic_id for slot in blueprint.slots}
    questions = list(
        (
            await db.execute(
                select(Question).where(
                    Question.topic_id.in_(topic_ids), Question.is_active.is_(True)
                )
            )
        ).scalars()
    )
    by_topic: dict[uuid.UUID, list[Question]] = {}
    for question in questions:
        by_topic.setdefault(question.topic_id, []).append(question)

    recent = await _recent_question_ids(db, child.id)
    rng = random.Random(blueprint.seed)

    assessment = Assessment(
        child_id=child.id,
        device_id=device.id if device else None,
        kind=kind,
        status=AssessmentStatus.IN_PROGRESS,
        policy_snapshot=policy.to_dict(),
        blueprint=blueprint.to_dict(),
        seed=blueprint.seed,
        pass_score_pct=policy.pass_score_pct,
        question_count=len(blueprint.slots),
        started_at=at,
        expires_at=at + timedelta(minutes=policy.time_limit_minutes),
        assigned_by_parent_id=assigned_by_parent_id,
    )
    db.add(assessment)
    await db.flush()

    used: set[uuid.UUID] = set()
    points_max = 0.0
    position = 0
    for slot in blueprint.slots:
        pool = [
            adaptive.QuestionCandidate(
                question_id=q.id,
                topic_id=q.topic_id,
                difficulty=q.difficulty,
                calibrated=q.difficulty_elo,
                times_served=q.times_served,
                last_served_rank=recent.get(q.id, 0) / RECENT_WINDOW,
            )
            for q in by_topic.get(slot.topic_id, [])
        ]
        picked = adaptive.select_question(slot, pool, rng, exclude=used)
        if picked is None:  # vivier epuise : on autorise une redite plutot qu'un trou
            picked = adaptive.select_question(slot, pool, rng)
        if picked is None:
            continue
        used.add(picked.question_id)
        question = next(q for q in questions if q.id == picked.question_id)

        item = AssessmentItem(
            assessment_id=assessment.id,
            question_id=question.id,
            topic_id=question.topic_id,
            subject_code=slot.subject_code,
            position=position,
            question_type=question.type,
            difficulty=question.difficulty,
            snapshot={**_question_snapshot(question), "bucket": slot.bucket},
            points_max=question.points,
        )
        db.add(item)
        question.times_served += 1
        points_max += question.points
        position += 1

    if position == 0:
        raise NoContentAvailableError("Impossible de composer une epreuve avec ce contenu.")

    assessment.question_count = position
    assessment.points_max = points_max
    await db.flush()

    await audit.record(
        db,
        family_id=child.family_id,
        action="assessment.started",
        actor_type="child",
        actor_id=child.id,
        target_type="assessment",
        target_id=assessment.id,
        payload={
            "kind": kind.value,
            "question_count": position,
            "seed": blueprint.seed,
            "distribution": blueprint.distribution,
        },
    )
    return assessment


async def _open_assessments(db: AsyncSession, child_id: uuid.UUID) -> list[Assessment]:
    return list(
        (
            await db.execute(
                select(Assessment).where(
                    Assessment.child_id == child_id,
                    Assessment.status == AssessmentStatus.IN_PROGRESS,
                )
            )
        ).scalars()
    )


async def get_assessment(db: AsyncSession, assessment_id: uuid.UUID) -> Assessment:
    assessment = (
        await db.execute(
            select(Assessment)
            .where(Assessment.id == assessment_id)
            .options(selectinload(Assessment.items))
        )
    ).scalar_one_or_none()
    if assessment is None:
        raise NotFoundError("Évaluation introuvable.")
    return assessment


# ---------------------------------------------------------------------------
# Reponses
# ---------------------------------------------------------------------------


async def save_answer(
    db: AsyncSession,
    assessment: Assessment,
    item: AssessmentItem,
    *,
    answer: dict[str, Any] | None,
    answer_mode: AnswerMode | None = None,
    strokes: dict[str, Any] | None = None,
    scratchpad: dict[str, Any] | None = None,
    time_spent_ms: int | None = None,
    at: datetime | None = None,
) -> AssessmentItem:
    """Enregistre (ou met a jour) la reponse d'un item. Sauvegarde continue."""
    at = at or clock_now()
    if assessment.status != AssessmentStatus.IN_PROGRESS:
        raise ConflictError("Cette évaluation est déjà terminée.")
    if assessment.expires_at and at > assessment.expires_at:
        raise ConflictError("Le temps imparti est ecoule.", code="assessment_expired")

    item.answer = answer
    if answer_mode:
        item.answer_mode = answer_mode
    if strokes is not None:
        item.strokes = strokes
    if scratchpad is not None:
        item.scratchpad = scratchpad
    if time_spent_ms is not None:
        item.time_spent_ms = max(item.time_spent_ms, int(time_spent_ms))
    item.answered_at = at
    return item


# ---------------------------------------------------------------------------
# Correction
# ---------------------------------------------------------------------------


async def _answer_spec(db: AsyncSession, item: AssessmentItem) -> dict[str, Any]:
    if item.question_id is None:
        return {}
    question = await db.get(Question, item.question_id)
    return dict(question.answer or {}) if question else {}


async def _grade_items(db: AsyncSession, assessment: Assessment) -> tuple[float, float, int]:
    """Corrige chaque item. Renvoie (points acquis, points en attente, nb a valider)."""
    earned = 0.0
    pending = 0.0
    to_review = 0

    for item in assessment.items:
        spec = await _answer_spec(db, item)
        answer = dict(item.answer or {})
        if item.strokes:
            answer.setdefault("has_strokes", True)

        result = grading.grade_answer(item.question_type, spec, answer or None)
        explanation = None
        if item.question_id:
            question = await db.get(Question, item.question_id)
            if question:
                explanation = question.explanation
                # Calibrage empirique de la difficulte de l'item.
                question.times_correct += 1 if result.is_correct else 0
                if item.time_spent_ms:
                    seen = max(1, question.times_served)
                    question.avg_seconds = round(
                        (question.avg_seconds * (seen - 1) + item.time_spent_ms / 1000) / seen, 2
                    )

        item.score = result.score
        item.is_correct = result.is_correct
        item.needs_manual_review = result.needs_manual_review
        item.points_awarded = round(result.score * item.points_max, 4)
        item.feedback = result.as_feedback(explanation)

        if result.needs_manual_review:
            pending += item.points_max
            to_review += 1
        else:
            earned += item.points_awarded

    return earned, pending, to_review


def _review_payload(assessment: Assessment) -> list[dict[str, Any]]:
    """Correction detaillee remise a l'enfant, meme (surtout) en cas d'echec."""
    review: list[dict[str, Any]] = []
    for item in sorted(assessment.items, key=lambda i: i.position):
        snapshot = item.snapshot or {}
        feedback = item.feedback or {}
        review.append(
            {
                "position": item.position,
                "topic_id": str(item.topic_id) if item.topic_id else None,
                "subject_code": item.subject_code,
                "bucket": snapshot.get("bucket"),
                "prompt": snapshot.get("prompt"),
                "choices": snapshot.get("choices"),
                "type": item.question_type.value,
                "difficulty": item.difficulty,
                "your_answer": feedback.get("given"),
                "expected": feedback.get("expected"),
                "is_correct": item.is_correct,
                "score": round(item.score, 3),
                "points": f"{round(item.points_awarded, 2)}/{round(item.points_max, 2)}",
                "explanation": feedback.get("explanation"),
                "diagnosis": feedback.get("diagnosis"),
                "detail": feedback.get("detail"),
                "per_part": feedback.get("per_part") or [],
                "needs_manual_review": item.needs_manual_review,
                "time_spent_ms": item.time_spent_ms,
            }
        )
    return review


async def _apply_mastery(
    db: AsyncSession, child: Child, assessment: Assessment, at: datetime
) -> tuple[list[dict[str, Any]], int]:
    """Met a jour la maitrise par notion et renvoie les mouvements notables."""
    states = await _mastery_states(db, child.id)
    existing = {
        row.topic_id: row
        for row in (await db.execute(select(Mastery).where(Mastery.child_id == child.id))).scalars()
    }
    moves: list[dict[str, Any]] = []
    cleared = 0

    for item in assessment.items:
        if item.topic_id is None or item.needs_manual_review:
            continue
        state = states.get(item.topic_id) or adaptive.MasteryState(
            topic_id=item.topic_id, subject_code=item.subject_code or "?"
        )
        calibrated = 0.0
        question = await db.get(Question, item.question_id) if item.question_id else None
        if question:
            calibrated = question.difficulty_elo

        update = adaptive.update_mastery(
            state,
            score=item.score,
            difficulty=item.difficulty,
            calibrated_difficulty=calibrated,
            at=at,
        )
        states[item.topic_id] = state

        if question:
            question.difficulty_elo = round(
                max(-1.5, min(1.5, question.difficulty_elo + update.item_calibration_delta)), 5
            )

        row = existing.get(item.topic_id)
        if row is None:
            row = Mastery(
                child_id=child.id, topic_id=item.topic_id, subject_code=item.subject_code or "?"
            )
            db.add(row)
            existing[item.topic_id] = row
        row.ability = state.ability
        row.ewma = state.ewma
        row.attempts = state.attempts
        row.correct = state.correct
        row.streak = state.streak
        row.ease = state.ease
        row.interval_days = state.interval_days
        row.next_review_at = state.next_review_at
        row.last_seen_at = state.last_seen_at
        row.band = state.band
        row.subject_code = item.subject_code or row.subject_code

        if update.improved_band:
            moves.append(
                {
                    "topic_id": str(item.topic_id),
                    "subject_code": item.subject_code,
                    "from": update.band_before.value,
                    "to": update.band_after.value,
                }
            )
            if update.band_before.value in {"fragile", "unknown"} and update.band_after.value in {
                "acquis",
                "expert",
                "en_cours",
            }:
                cleared += 1

    return moves, cleared


async def submit_assessment(
    db: AsyncSession,
    *,
    child: Child,
    assessment: Assessment,
    policy: EffectivePolicy,
    device: Device | None = None,
    at: datetime | None = None,
) -> SubmissionResult:
    """Corrige, decide, recompense ou sanctionne."""
    at = at or clock_now()
    if assessment.status not in (AssessmentStatus.IN_PROGRESS, AssessmentStatus.SUBMITTED):
        raise ConflictError("Cette évaluation a déjà été corrigée.")

    assessment.submitted_at = at
    if assessment.started_at:
        assessment.duration_seconds = int((at - assessment.started_at).total_seconds())

    earned, pending, to_review = await _grade_items(db, assessment)
    points_max = assessment.points_max or sum(i.points_max for i in assessment.items) or 1.0
    assessment.points_max = points_max
    assessment.points_earned = round(earned, 4)

    threshold_points = points_max * assessment.pass_score_pct / 100.0
    best_case = earned + pending

    passed = earned >= threshold_points - 1e-9
    pending_review = False
    if not passed and to_review and best_case >= threshold_points - 1e-9:
        # Le verdict depend d'une reponse manuscrite : on attend le parent.
        pending_review = True

    score_pct = round(100.0 * earned / points_max, 4)
    assessment.score_pct = score_pct
    assessment.score_out_of_20 = round(score_pct * 0.2, 2)
    assessment.graded_at = at

    moves, cleared = await _apply_mastery(db, child, assessment, at)

    # --- Experience --------------------------------------------------------
    streak = xp.update_streak(child, at.date())
    already = await xp.xp_earned_today(db, child.id, at=at)
    multiplier = (
        policy.practice_xp_multiplier if assessment.kind == AssessmentKind.PRACTICE else 1.0
    )
    xp_total, grants = xp.compute_assessment_xp(
        item_scores=[
            (i.score, i.difficulty) for i in assessment.items if not i.needs_manual_review
        ],
        passed=passed,
        score_pct=score_pct,
        cleared_weaknesses=cleared,
        streak_days=streak,
        practice_multiplier=multiplier,
        xp_already_today=already,
    )
    await xp.record_xp(db, child, grants, ref_type="assessment", ref_id=assessment.id)
    assessment.xp_earned = xp_total

    # --- Verdict -----------------------------------------------------------
    issued: unlock.IssuedCode | None = None
    lockout = None
    weak = _weak_topics_from(assessment)

    if pending_review:
        assessment.status = AssessmentStatus.NEEDS_REVIEW
        assessment.passed = None
    else:
        assessment.passed = passed
        assessment.status = AssessmentStatus.GRADED
        if passed and assessment.kind == AssessmentKind.UNLOCK and device is not None:
            issued = await unlock.issue_code(
                db,
                child=child,
                device=device,
                duration_minutes=policy.reward_minutes,
                kind=proto.UnlockKind.ASSESSMENT_REWARD,
                assessment_id=assessment.id,
                note=f"Évaluation réussie : {assessment.score_out_of_20}/20",
                at=at,
            )
            assessment.reward_minutes = issued.record.duration_minutes
            assessment.unlock_code_id = issued.record.id
        elif not passed and assessment.kind == AssessmentKind.UNLOCK:
            failures = await failures_today(db, child.id, at=at)
            minutes = lockouts.escalated_minutes(
                policy.cooldown_minutes, failures, policy.cooldown_escalation
            )
            lockout = await lockouts.open_lockout(
                db,
                child_id=child.id,
                reason=LockoutReason.FAILED_ASSESSMENT,
                minutes=minutes,
                message=(
                    f"Score {assessment.score_out_of_20}/20, il fallait "
                    f"{round(assessment.pass_score_pct * 0.2, 1)}/20. "
                    "Profite de ce temps pour revoir la correction."
                ),
                source_assessment_id=assessment.id,
                review_topics=weak,
                at=at,
            )
            assessment.lockout_id = lockout.id

    await audit.record(
        db,
        family_id=child.family_id,
        action="assessment.graded",
        actor_type="child",
        actor_id=child.id,
        target_type="assessment",
        target_id=assessment.id,
        payload={
            "score_pct": score_pct,
            "passed": assessment.passed,
            "pending_manual_review": pending_review,
            "xp": xp_total,
            "reward_minutes": assessment.reward_minutes,
        },
    )

    return SubmissionResult(
        assessment=assessment,
        passed=bool(passed and not pending_review),
        pending_manual_review=pending_review,
        score_pct=score_pct,
        score_out_of_20=assessment.score_out_of_20 or 0.0,
        issued_code=issued,
        lockout=lockout,
        xp_total=xp_total,
        xp_grants=grants,
        review=_review_payload(assessment),
        weak_topics=weak,
        mastery_moves=moves,
    )


def _weak_topics_from(assessment: Assessment) -> list[dict[str, Any]]:
    """Notions ratees pendant cette epreuve : c'est le programme de revision."""
    seen: dict[str, dict[str, Any]] = {}
    for item in assessment.items:
        if item.is_correct or item.topic_id is None:
            continue
        key = str(item.topic_id)
        entry = seen.setdefault(
            key,
            {
                "topic_id": key,
                "subject_code": item.subject_code,
                "missed": 0,
                "sample_prompt": (item.snapshot or {}).get("prompt"),
            },
        )
        entry["missed"] += 1
    return sorted(seen.values(), key=lambda e: -e["missed"])


# ---------------------------------------------------------------------------
# Validation parentale d'une reponse manuscrite
# ---------------------------------------------------------------------------


async def manual_grade_item(
    db: AsyncSession,
    *,
    child: Child,
    assessment: Assessment,
    item: AssessmentItem,
    score: float,
    parent_id: uuid.UUID,
    policy: EffectivePolicy,
    comment: str | None = None,
    device: Device | None = None,
    at: datetime | None = None,
) -> SubmissionResult | None:
    """Le parent tranche une reponse manuscrite ; si tout est tranche, on conclut."""
    at = at or clock_now()
    score = min(max(float(score), 0.0), 1.0)

    item.manual_grade = score
    item.score = score
    item.is_correct = score >= grading.CORRECT_THRESHOLD
    item.points_awarded = round(score * item.points_max, 4)
    item.needs_manual_review = False
    item.graded_by_parent_id = parent_id
    item.parent_comment = comment
    item.feedback = {
        **(item.feedback or {}),
        "score": score,
        "is_correct": item.is_correct,
        "manual": True,
        "parent_comment": comment,
        "needs_manual_review": False,
    }

    await audit.record(
        db,
        family_id=child.family_id,
        action="assessment.manual_grade",
        actor_type="parent",
        actor_id=parent_id,
        target_type="assessment_item",
        target_id=item.id,
        payload={"score": score, "assessment_id": str(assessment.id)},
    )

    if any(i.needs_manual_review for i in assessment.items):
        return None
    if assessment.status != AssessmentStatus.NEEDS_REVIEW:
        return None

    return await finalize_after_review(
        db, child=child, assessment=assessment, policy=policy, device=device, at=at
    )


async def finalize_after_review(
    db: AsyncSession,
    *,
    child: Child,
    assessment: Assessment,
    policy: EffectivePolicy,
    device: Device | None = None,
    at: datetime | None = None,
) -> SubmissionResult:
    """Conclut une evaluation dont toutes les reponses manuscrites sont tranchees."""
    at = at or clock_now()
    earned = sum(i.points_awarded for i in assessment.items)
    points_max = assessment.points_max or 1.0
    score_pct = round(100.0 * earned / points_max, 4)
    passed = score_pct >= assessment.pass_score_pct - 1e-9

    assessment.points_earned = round(earned, 4)
    assessment.score_pct = score_pct
    assessment.score_out_of_20 = round(score_pct * 0.2, 2)
    assessment.passed = passed
    assessment.status = AssessmentStatus.GRADED
    assessment.graded_at = at

    moves, _ = await _apply_mastery(db, child, assessment, at)

    issued: unlock.IssuedCode | None = None
    lockout = None
    weak = _weak_topics_from(assessment)

    if passed and assessment.kind == AssessmentKind.UNLOCK and device is not None:
        issued = await unlock.issue_code(
            db,
            child=child,
            device=device,
            duration_minutes=policy.reward_minutes,
            kind=proto.UnlockKind.ASSESSMENT_REWARD,
            assessment_id=assessment.id,
            note="Évaluation validée après correction parentale",
            at=at,
        )
        assessment.reward_minutes = issued.record.duration_minutes
        assessment.unlock_code_id = issued.record.id
    elif not passed and assessment.kind == AssessmentKind.UNLOCK:
        failures = await failures_today(db, child.id, at=at)
        lockout = await lockouts.open_lockout(
            db,
            child_id=child.id,
            reason=LockoutReason.FAILED_ASSESSMENT,
            minutes=lockouts.escalated_minutes(
                policy.cooldown_minutes, failures, policy.cooldown_escalation
            ),
            message="Évaluation non validée après correction.",
            source_assessment_id=assessment.id,
            review_topics=weak,
            at=at,
        )
        assessment.lockout_id = lockout.id

    return SubmissionResult(
        assessment=assessment,
        passed=passed,
        pending_manual_review=False,
        score_pct=score_pct,
        score_out_of_20=assessment.score_out_of_20 or 0.0,
        issued_code=issued,
        lockout=lockout,
        xp_total=assessment.xp_earned,
        xp_grants=[],
        review=_review_payload(assessment),
        weak_topics=weak,
        mastery_moves=moves,
    )


async def expire_stale_assessments(db: AsyncSession, *, at: datetime | None = None) -> int:
    at = at or clock_now()
    stale = list(
        (
            await db.execute(
                select(Assessment).where(
                    Assessment.status == AssessmentStatus.IN_PROGRESS,
                    Assessment.expires_at <= at,
                )
            )
        ).scalars()
    )
    for assessment in stale:
        assessment.status = AssessmentStatus.EXPIRED
    return len(stale)


async def pending_codes_for_child(
    db: AsyncSession, child_id: uuid.UUID, *, at: datetime | None = None
) -> list[UnlockCode]:
    at = at or clock_now()
    return list(
        (
            await db.execute(
                select(UnlockCode).where(
                    UnlockCode.child_id == child_id,
                    UnlockCode.status == "issued",
                    UnlockCode.expires_at > at,
                )
            )
        ).scalars()
    )


__all__ = [
    "AnswerMode",
    "AssessmentKind",
    "AssessmentStatus",
    "EligibilityReport",
    "QuestionType",
    "SubmissionResult",
    "check_eligibility",
    "finalize_after_review",
    "get_assessment",
    "manual_grade_item",
    "save_answer",
    "start_assessment",
    "submit_assessment",
]
