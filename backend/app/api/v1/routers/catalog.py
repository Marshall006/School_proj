"""Catalogue pedagogique et questions personnalisees du parent."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from app.api.deps import CurrentParent, CurrentWriter, DbSession
from app.content.catalog import COUNTRIES
from app.content.seed import content_stats
from app.core.errors import NotFoundError
from app.models.content import GradeLevel, Question, Subject, Topic
from app.schemas.catalog import (
    CountryOut,
    CustomQuestionIn,
    GradeLevelOut,
    QuestionOut,
    SubjectOut,
    TopicOut,
)
from app.services import audit

router = APIRouter(prefix="/catalog", tags=["Catalogue pedagogique"])


@router.get("/countries", response_model=list[CountryOut])
async def list_countries() -> list[CountryOut]:
    """Pays couverts, avec leurs intitules de classes."""
    return [
        CountryOut(
            code=country.code,
            name=country.name,
            currency=country.currency,
            capital=country.capital,
            grades=[
                {"code": g.code, "name": g.name, "cycle": g.cycle, "age": g.age, "level": g.level}
                for g in country.grades
            ],
        )
        for country in COUNTRIES
    ]


@router.get("/subjects", response_model=list[SubjectOut])
async def list_subjects(db: DbSession) -> list[Subject]:
    return list((await db.execute(select(Subject).order_by(Subject.position))).scalars())


@router.get("/grades", response_model=list[GradeLevelOut])
async def list_grades(
    db: DbSession, country_code: str = Query(default="FR", min_length=2, max_length=2)
) -> list[GradeLevel]:
    return list(
        (
            await db.execute(
                select(GradeLevel)
                .where(GradeLevel.country_code == country_code.upper())
                .order_by(GradeLevel.position)
            )
        ).scalars()
    )


@router.get("/topics", response_model=list[TopicOut])
async def list_topics(
    db: DbSession,
    country_code: str = Query(min_length=2, max_length=2),
    grade_code: str = Query(min_length=1, max_length=16),
    subject_code: str | None = None,
) -> list[Topic]:
    query = (
        select(Topic)
        .where(
            Topic.country_code == country_code.upper(),
            Topic.grade_code == grade_code.upper(),
        )
        .order_by(Topic.position)
    )
    if subject_code:
        query = query.join(Subject, Subject.id == Topic.subject_id).where(
            Subject.code == subject_code
        )
    return list((await db.execute(query)).scalars())


@router.get("/coverage")
async def coverage(db: DbSession) -> dict[str, Any]:
    """Volume de la banque, par pays et par classe."""
    return await content_stats(db)


@router.get("/questions", response_model=list[QuestionOut])
async def list_questions(
    db: DbSession,
    parent: CurrentParent,
    topic_id: uuid.UUID,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[Question]:
    """Questions d'une notion (sans le corrige : il reste cote serveur)."""
    return list(
        (
            await db.execute(
                select(Question)
                .where(Question.topic_id == topic_id, Question.is_active.is_(True))
                .order_by(Question.difficulty)
                .limit(limit)
            )
        ).scalars()
    )


@router.post("/questions", response_model=QuestionOut, status_code=201)
async def create_custom_question(
    db: DbSession, parent: CurrentWriter, payload: CustomQuestionIn
) -> Question:
    """Le parent ajoute ses propres questions (la lecon du jour, un devoir precis).

    Ces items rejoignent la banque et sont selectionnables par le moteur
    adaptatif au meme titre que le contenu livre.
    """
    topic = await db.get(Topic, payload.topic_id)
    if topic is None:
        raise NotFoundError("Notion introuvable.")

    count = int(
        await db.scalar(
            select(func.count(Question.id)).where(Question.author_parent_id == parent.id)
        )
        or 0
    )
    question = Question(
        topic_id=topic.id,
        external_ref=f"custom-{parent.id.hex[:8]}-{count + 1:04d}",
        type=payload.type,
        difficulty=payload.difficulty,
        prompt=payload.prompt,
        instructions=payload.instructions,
        choices=payload.choices,
        answer=payload.answer,
        explanation=payload.explanation,
        points=payload.points,
        estimated_seconds=payload.estimated_seconds,
        tags=[*payload.tags, "personnalise"],
        source="parent",
        author_parent_id=parent.id,
    )
    db.add(question)
    await db.flush()
    await audit.record(
        db,
        family_id=parent.family_id,
        action="question.created",
        actor_type="parent",
        actor_id=parent.id,
        target_type="question",
        target_id=question.id,
        payload={"topic": topic.code},
    )
    await db.commit()
    return question


@router.delete("/questions/{question_id}", status_code=204)
async def delete_custom_question(
    db: DbSession, parent: CurrentWriter, question_id: uuid.UUID
) -> None:
    question = await db.get(Question, question_id)
    if question is None or question.author_parent_id != parent.id:
        raise NotFoundError("Question personnalisee introuvable.")
    question.is_active = False
    await db.commit()
