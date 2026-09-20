"""Fabriques d'items : petites fonctions qui produisent des questions valides.

Elles centralisent la forme du JSON attendu par le correcteur et par
l'interface enfant (`input_spec` decrit le clavier, la palette de symboles, le
gabarit d'opération posée et l'autorisation de l'ardoise manuscrite).
"""

from __future__ import annotations

from fractions import Fraction
from random import Random
from typing import Any

from app.models.enums import QuestionType


def jsonable(value: Any) -> Any:
    """Rend une valeur stockable en JSON.

    Les generateurs raisonnent en fractions exactes (`Fraction(3, 4)`) pour
    eviter les erreurs d'arrondi ; on les serialise en `"3/4"`, forme que le
    correcteur sait relire sans perte.
    """
    if isinstance(value, Fraction):
        return (
            value.numerator if value.denominator == 1 else f"{value.numerator}/{value.denominator}"
        )
    if isinstance(value, list | tuple):
        return [jsonable(v) for v in value]
    if isinstance(value, dict):
        return {k: jsonable(v) for k, v in value.items()}
    return value


# --- Claviers et gabarits proposes a l'enfant ------------------------------

KEYPAD_NUMERIC = {"keypad": "numeric", "allow_handwriting": True}
KEYPAD_DECIMAL = {"keypad": "decimal", "palette": [",", "-"], "allow_handwriting": True}
KEYPAD_MATH = {
    "keypad": "math",
    "palette": ["+", "-", "x", ":", "/", ",", "(", ")", "="],
    "allow_handwriting": True,
}
WIDGET_FRACTION = {
    "keypad": "fraction",
    "widget": "fraction_builder",
    "palette": ["/", "+", "-"],
    "allow_handwriting": True,
}
WIDGET_LONG_DIVISION = {
    "keypad": "numeric",
    "widget": "long_division",  # barres de division glissables (mode assiste)
    "template": "division_posée",
    "allow_handwriting": True,
}
WIDGET_COLUMN_OP = {
    "keypad": "numeric",
    "widget": "column_opération",  # opération posée en colonnes, retenues incluses
    "template": "opération_posée",
    "allow_handwriting": True,
}
WIDGET_CHOICE = {"keypad": "none", "allow_handwriting": False}
WIDGET_TEXT = {"keypad": "text", "allow_handwriting": True}
WIDGET_DRAG = {"keypad": "none", "widget": "drag_drop", "allow_handwriting": False}


def _base(
    prompt: str,
    qtype: QuestionType,
    *,
    difficulty: int,
    explanation: str | None,
    tags: list[str] | None,
    input_spec: dict[str, Any] | None,
    instructions: str | None = None,
    points: float = 1.0,
    estimated_seconds: int = 45,
    hints: list[str] | None = None,
    assets: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "type": qtype,
        "prompt": prompt,
        "instructions": instructions,
        "difficulty": max(1, min(5, difficulty)),
        "explanation": explanation,
        "tags": tags or [],
        "input_spec": input_spec or WIDGET_CHOICE,
        "points": points,
        "estimated_seconds": estimated_seconds,
        "hints": hints or [],
        "assets": assets or [],
        "choices": None,
        "answer": {},
    }


def mcq(
    prompt: str,
    options: list[str],
    correct_index: int,
    *,
    difficulty: int = 2,
    explanation: str | None = None,
    tags: list[str] | None = None,
    shuffle: Random | None = None,
    instructions: str | None = None,
    estimated_seconds: int = 40,
) -> dict[str, Any]:
    """QCM à réponse unique. `shuffle` melange les propositions de facon reproductible."""
    pairs = list(enumerate(options))
    if shuffle is not None:
        shuffle.shuffle(pairs)
    letters = "abcdefgh"
    choices = [{"id": letters[i], "text": text} for i, (_, text) in enumerate(pairs)]
    correct_id = next(
        letters[i] for i, (original, _) in enumerate(pairs) if original == correct_index
    )
    item = _base(
        prompt,
        QuestionType.MCQ_SINGLE,
        difficulty=difficulty,
        explanation=explanation,
        tags=tags,
        input_spec=WIDGET_CHOICE,
        instructions=instructions,
        estimated_seconds=estimated_seconds,
    )
    item["choices"] = choices
    item["answer"] = {"correct": [correct_id], "display": options[correct_index]}
    return item


def mcq_multi(
    prompt: str,
    options: list[str],
    correct_indexes: list[int],
    *,
    difficulty: int = 3,
    explanation: str | None = None,
    tags: list[str] | None = None,
    shuffle: Random | None = None,
) -> dict[str, Any]:
    pairs = list(enumerate(options))
    if shuffle is not None:
        shuffle.shuffle(pairs)
    letters = "abcdefgh"
    choices = [{"id": letters[i], "text": text} for i, (_, text) in enumerate(pairs)]
    correct_ids = [
        letters[i] for i, (original, _) in enumerate(pairs) if original in correct_indexes
    ]
    item = _base(
        prompt + " (plusieurs réponses possibles)",
        QuestionType.MCQ_MULTI,
        difficulty=difficulty,
        explanation=explanation,
        tags=tags,
        input_spec=WIDGET_CHOICE,
        estimated_seconds=55,
    )
    item["choices"] = choices
    item["answer"] = {
        "correct": correct_ids,
        "partial_credit": True,
        "display": ", ".join(options[i] for i in correct_indexes),
    }
    return item


def true_false(
    prompt: str,
    correct: bool,
    *,
    difficulty: int = 1,
    explanation: str | None = None,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    item = _base(
        prompt,
        QuestionType.TRUE_FALSE,
        difficulty=difficulty,
        explanation=explanation,
        tags=tags,
        input_spec=WIDGET_CHOICE,
        estimated_seconds=25,
    )
    item["choices"] = [{"id": "vrai", "text": "Vrai"}, {"id": "faux", "text": "Faux"}]
    item["answer"] = {"correct": correct, "display": "Vrai" if correct else "Faux"}
    return item


def numeric(
    prompt: str,
    value: Any,
    *,
    difficulty: int = 2,
    explanation: str | None = None,
    tags: list[str] | None = None,
    unit: str | None = None,
    tolerance: float = 0.0,
    accept: list[Any] | None = None,
    input_spec: dict[str, Any] | None = None,
    display: str | None = None,
    instructions: str | None = None,
    estimated_seconds: int = 50,
) -> dict[str, Any]:
    item = _base(
        prompt,
        QuestionType.NUMERIC,
        difficulty=difficulty,
        explanation=explanation,
        tags=tags,
        input_spec=input_spec or KEYPAD_NUMERIC,
        instructions=instructions,
        estimated_seconds=estimated_seconds,
    )
    item["answer"] = {
        "value": jsonable(value),
        "tolerance": tolerance,
        "unit": unit,
        "accept": jsonable(accept or []),
        "display": display or (f"{jsonable(value)} {unit}" if unit else str(jsonable(value))),
    }
    return item


def expression(
    prompt: str,
    value: Any,
    *,
    difficulty: int = 3,
    explanation: str | None = None,
    tags: list[str] | None = None,
    input_spec: dict[str, Any] | None = None,
    require_form: str | None = None,
    display: str | None = None,
    accept: list[Any] | None = None,
    instructions: str | None = None,
) -> dict[str, Any]:
    """Réponse saisie avec les composants assistes (fractions, opérations posées)."""
    item = _base(
        prompt,
        QuestionType.EXPRESSION,
        difficulty=difficulty,
        explanation=explanation,
        tags=tags,
        input_spec=input_spec or KEYPAD_MATH,
        instructions=instructions,
        estimated_seconds=70,
    )
    item["answer"] = {
        "value": jsonable(value),
        "accept": jsonable(accept or []),
        "require_form": require_form,
        "display": display or str(jsonable(value)),
    }
    return item


def short_text(
    prompt: str,
    accept: list[str],
    *,
    difficulty: int = 2,
    explanation: str | None = None,
    tags: list[str] | None = None,
    max_distance: int = 1,
    normalize: dict[str, Any] | None = None,
    instructions: str | None = None,
) -> dict[str, Any]:
    item = _base(
        prompt,
        QuestionType.SHORT_TEXT,
        difficulty=difficulty,
        explanation=explanation,
        tags=tags,
        input_spec=WIDGET_TEXT,
        instructions=instructions,
        estimated_seconds=45,
    )
    item["answer"] = {
        "accept": accept,
        "max_distance": max_distance,
        "normalize": normalize or {"lowercase": True, "accents": True, "punctuation": True},
        "display": accept[0],
    }
    return item


def fill_blank(
    prompt: str,
    blanks: list[list[str]],
    *,
    difficulty: int = 2,
    explanation: str | None = None,
    tags: list[str] | None = None,
    instructions: str | None = None,
) -> dict[str, Any]:
    """Texte à trous. `prompt` contient des `...` ; `blanks[i]` liste les acceptes."""
    item = _base(
        prompt,
        QuestionType.FILL_BLANK,
        difficulty=difficulty,
        explanation=explanation,
        tags=tags,
        input_spec=WIDGET_TEXT,
        instructions=instructions or "Complète chaque trou.",
        estimated_seconds=60,
        points=1.0,
    )
    item["answer"] = {
        "blanks": [
            {
                "accept": options,
                "max_distance": 0,
                "normalize": {"lowercase": True, "accents": True},
            }
            for options in blanks
        ],
        "display": " / ".join(options[0] for options in blanks),
    }
    return item


def ordering(
    prompt: str,
    items_in_order: list[str],
    *,
    difficulty: int = 3,
    explanation: str | None = None,
    tags: list[str] | None = None,
    shuffle: Random | None = None,
) -> dict[str, Any]:
    letters = "abcdefgh"
    ids = [letters[i] for i in range(len(items_in_order))]
    display = list(zip(ids, items_in_order, strict=True))
    shown = list(display)
    if shuffle is not None:
        shuffle.shuffle(shown)
    item = _base(
        prompt,
        QuestionType.ORDERING,
        difficulty=difficulty,
        explanation=explanation,
        tags=tags,
        input_spec=WIDGET_DRAG,
        instructions="Remets les éléments dans le bon ordre.",
        estimated_seconds=60,
    )
    item["choices"] = [{"id": i, "text": text} for i, text in shown]
    item["answer"] = {"order": ids, "display": " < ".join(items_in_order)}
    return item


def matching(
    prompt: str,
    pairs: dict[str, str],
    *,
    difficulty: int = 3,
    explanation: str | None = None,
    tags: list[str] | None = None,
    shuffle: Random | None = None,
) -> dict[str, Any]:
    left = list(pairs.keys())
    right = list(pairs.values())
    if shuffle is not None:
        shuffle.shuffle(right)
    item = _base(
        prompt,
        QuestionType.MATCHING,
        difficulty=difficulty,
        explanation=explanation,
        tags=tags,
        input_spec=WIDGET_DRAG,
        instructions="Relie chaque élément à sa réponse.",
        estimated_seconds=70,
    )
    item["choices"] = [
        {"id": "left", "items": left},
        {"id": "right", "items": right},
    ]
    item["answer"] = {"pairs": pairs, "display": ", ".join(f"{k} -> {v}" for k, v in pairs.items())}
    return item


def handwritten(
    prompt: str,
    value: Any,
    *,
    difficulty: int = 3,
    explanation: str | None = None,
    tags: list[str] | None = None,
    instructions: str | None = None,
) -> dict[str, Any]:
    """Item pose sur l'ardoise : l'enfant écrit, l'app transcrit, le parent arbitre."""
    item = _base(
        prompt,
        QuestionType.HANDWRITTEN,
        difficulty=difficulty,
        explanation=explanation,
        tags=tags,
        input_spec={"keypad": "none", "widget": "canvas", "allow_handwriting": True},
        instructions=instructions or "Pose et effectue l'opération sur l'ardoise.",
        estimated_seconds=120,
        points=2.0,
    )
    item["answer"] = {
        "value": jsonable(value),
        "manual_fallback": True,
        "display": str(jsonable(value)),
    }
    return item


# --- Aides de mise en forme ------------------------------------------------


def fmt_int(value: int) -> str:
    """Ecriture française des grands nombres : 1 234 567."""
    return f"{value:,}".replace(",", " ")


def fmt_decimal(value: float, decimals: int = 2) -> str:
    return f"{value:.{decimals}f}".replace(".", ",")


def money(value: float, country: Any) -> str:
    """Prix localise : 3,50 EUR en France, 350 FCFA en zone franc."""
    amount = value * country.money_scale
    if country.money_scale == 1:
        return f"{fmt_decimal(amount)} €"
    return f"{fmt_int(int(round(amount)))} FCFA"


def money_value(value: float, country: Any) -> float:
    amount = value * country.money_scale
    return round(amount, 2) if country.money_scale == 1 else float(int(round(amount)))
