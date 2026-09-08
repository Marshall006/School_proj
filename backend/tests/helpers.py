"""Utilitaires de test : fabriquer des reponses justes ou fausses a une epreuve."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select

from app.models.assessment import Assessment, AssessmentItem
from app.models.content import Question


def correct_answer(question_type: str, spec: dict[str, Any]) -> dict[str, Any]:
    """Construit la reponse attendue a partir du bareme (usage test uniquement)."""
    match question_type:
        case "mcq_single":
            return {"choice": spec["correct"][0]}
        case "mcq_multi":
            return {"choices": list(spec["correct"])}
        case "true_false":
            return {"value": spec["correct"]}
        case "short_text":
            return {"value": spec["accept"][0]}
        case "fill_blank":
            return {"values": [b["accept"][0] for b in spec["blanks"]]}
        case "ordering":
            return {"order": list(spec["order"])}
        case "matching":
            return {"pairs": dict(spec["pairs"])}
        case "handwritten":
            return {"transcript": str(spec["value"]), "has_strokes": True}
        case _:  # numeric, expression
            return {"value": spec.get("value")}


def wrong_answer(question_type: str, spec: dict[str, Any]) -> dict[str, Any]:
    match question_type:
        case "mcq_single":
            return {"choice": "z"}
        case "mcq_multi":
            return {"choices": ["z"]}
        case "true_false":
            return {"value": not spec["correct"]}
        case "short_text":
            return {"value": "reponse manifestement fausse"}
        case "fill_blank":
            return {"values": ["zzz" for _ in spec["blanks"]]}
        case "ordering":
            return {"order": list(reversed(spec["order"]))}
        case "matching":
            return {"pairs": dict.fromkeys(spec["pairs"], "zzz")}
        case "handwritten":
            return {"transcript": "-999999", "has_strokes": True}
        case _:
            return {"value": -999999}


def as_uuid(value) -> uuid.UUID:
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


async def answer_key(db, assessment_id) -> dict[str, tuple[str, dict[str, Any]]]:
    """Renvoie {item_id: (type, bareme)} en lisant directement la base."""
    assessment_id = as_uuid(assessment_id)
    rows = (
        await db.execute(
            select(AssessmentItem, Question)
            .join(Question, Question.id == AssessmentItem.question_id)
            .where(AssessmentItem.assessment_id == assessment_id)
            .order_by(AssessmentItem.position)
        )
    ).all()
    return {str(item.id): (item.question_type.value, question.answer) for item, question in rows}


async def refresh_assessment(db, assessment_id) -> Assessment:
    db.expire_all()
    return (
        await db.execute(select(Assessment).where(Assessment.id == as_uuid(assessment_id)))
    ).scalar_one()
