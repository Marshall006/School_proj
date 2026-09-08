"""Chargement de la banque pedagogique.

Le remplissage est **idempotent** et **deterministe** : chaque question porte
une reference stable (`external_ref`), et le tirage aleatoire est ensemence par
cette meme reference. Relancer le seed n'ajoute donc jamais de doublon et
produit exactement la meme banque, ce qui rend les tests et les migrations de
contenu previsibles.
"""

from __future__ import annotations

import hashlib
import logging
from random import Random
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.content import generators
from app.content.catalog import (
    COUNTRIES,
    COUNTRY_BY_CODE,
    DEFAULT_SEED_COUNTRIES,
    DEFAULT_SEED_LEVELS,
    SUBJECTS,
    TOPICS,
    grades_at_level,
    topics_for_level,
)
from app.models.content import GradeLevel, Question, Subject, Topic

logger = logging.getLogger("koda.seed")


def _stable_seed(*parts: str) -> int:
    digest = hashlib.sha256("|".join(parts).encode()).digest()
    return int.from_bytes(digest[:6], "big")


async def seed_subjects(db: AsyncSession) -> int:
    existing = {row.code for row in (await db.execute(select(Subject))).scalars()}
    created = 0
    for spec in SUBJECTS:
        if spec["code"] in existing:
            continue
        db.add(Subject(**spec))
        created += 1
    await db.flush()
    return created


async def seed_grade_levels(db: AsyncSession, countries: tuple[str, ...]) -> int:
    existing = {
        (row.country_code, row.code) for row in (await db.execute(select(GradeLevel))).scalars()
    }
    created = 0
    for country in COUNTRIES:
        if country.code not in countries:
            continue
        for grade in country.grades:
            if (country.code, grade.code) in existing:
                continue
            db.add(
                GradeLevel(
                    country_code=country.code,
                    code=grade.code,
                    name=grade.name,
                    cycle=grade.cycle,
                    position=grade.level,
                    typical_age=grade.age,
                )
            )
            created += 1
    await db.flush()
    return created


async def seed_topics(db: AsyncSession, countries: tuple[str, ...], levels: tuple[int, ...]) -> int:
    subjects = {row.code: row.id for row in (await db.execute(select(Subject))).scalars()}
    existing = {
        (row.country_code, row.grade_code, row.code)
        for row in (await db.execute(select(Topic))).scalars()
    }
    created = 0
    for country_code in countries:
        for level in levels:
            for grade in grades_at_level(country_code, level):
                for spec in topics_for_level(level):
                    key = (country_code, grade.code, spec.code)
                    if key in existing:
                        continue
                    db.add(
                        Topic(
                            subject_id=subjects[spec.subject],
                            country_code=country_code,
                            grade_code=grade.code,
                            code=spec.code,
                            name=spec.name,
                            description=spec.description,
                            position=spec.position,
                            is_core=spec.is_core,
                            tags=[spec.subject, f"niveau{level}"],
                        )
                    )
                    created += 1
    await db.flush()
    return created


async def seed_questions(
    db: AsyncSession, countries: tuple[str, ...], levels: tuple[int, ...]
) -> int:
    """Genere la banque d'items pour chaque (pays, classe, notion)."""
    topic_rows = list((await db.execute(select(Topic))).scalars())
    topics_by_key = {(t.country_code, t.grade_code, t.code): t for t in topic_rows}

    existing_refs = {
        row for row in (await db.execute(select(Question.external_ref))).scalars() if row
    }
    spec_by_code = {t.code: t for t in TOPICS}
    created = 0

    for country_code in countries:
        country = COUNTRY_BY_CODE.get(country_code)
        if country is None:
            continue
        for level in levels:
            for grade in grades_at_level(country_code, level):
                for spec in topics_for_level(level):
                    topic = topics_by_key.get((country_code, grade.code, spec.code))
                    if topic is None:
                        continue
                    generator = generators.get(spec_by_code[spec.code].generator)
                    if generator is None:
                        continue
                    rng = Random(_stable_seed(country_code, grade.code, spec.code))
                    try:
                        items = generator(rng, level, country)
                    except Exception:  # pragma: no cover - un generateur ne doit pas tout casser
                        logger.exception(
                            "Generateur %s en echec pour %s/%s",
                            spec.generator,
                            country_code,
                            grade.code,
                        )
                        continue

                    for index, item in enumerate(items):
                        ref = f"{country_code}-{grade.code}-{spec.code}-{index:03d}"
                        if ref in existing_refs:
                            continue
                        db.add(
                            Question(
                                topic_id=topic.id,
                                external_ref=ref,
                                type=item["type"],
                                difficulty=item["difficulty"],
                                prompt=item["prompt"],
                                instructions=item.get("instructions"),
                                choices=item.get("choices"),
                                answer=item["answer"],
                                explanation=item.get("explanation"),
                                hints=item.get("hints") or [],
                                assets=item.get("assets") or [],
                                input_spec=item.get("input_spec") or {},
                                points=item.get("points", 1.0),
                                estimated_seconds=item.get("estimated_seconds", 45),
                                tags=item.get("tags") or [],
                                source="koda-core",
                            )
                        )
                        existing_refs.add(ref)
                        created += 1
                    if created and created % 500 == 0:
                        await db.flush()
    await db.flush()
    return created


async def seed_all(
    db: AsyncSession,
    *,
    countries: tuple[str, ...] = DEFAULT_SEED_COUNTRIES,
    levels: tuple[int, ...] = DEFAULT_SEED_LEVELS,
) -> dict[str, int]:
    """Remplit (ou complete) la banque. Sans effet si tout est deja la."""
    report = {
        "subjects": await seed_subjects(db),
        "grade_levels": await seed_grade_levels(db, countries),
        "topics": await seed_topics(db, countries, levels),
        "questions": await seed_questions(db, countries, levels),
    }
    await db.commit()
    report["total_questions"] = int(await db.scalar(select(func.count(Question.id))) or 0)
    logger.info("Banque pedagogique : %s", report)
    return report


async def content_stats(db: AsyncSession) -> dict[str, Any]:
    """Photographie de la banque, exposee dans /health et le tableau de bord."""
    rows = (
        await db.execute(
            select(
                Topic.country_code,
                Topic.grade_code,
                func.count(Question.id),
            )
            .join(Question, Question.topic_id == Topic.id)
            .group_by(Topic.country_code, Topic.grade_code)
        )
    ).all()
    by_scope = [{"country_code": c, "grade_code": g, "questions": int(n)} for c, g, n in rows]
    total = sum(row["questions"] for row in by_scope)
    return {
        "total_questions": total,
        "total_topics": int(await db.scalar(select(func.count(Topic.id))) or 0),
        "total_subjects": int(await db.scalar(select(func.count(Subject.id))) or 0),
        "coverage": sorted(by_scope, key=lambda r: (r["country_code"], r["grade_code"])),
    }
