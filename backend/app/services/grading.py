"""Moteur de correction.

Deux exigences fortes, tirees du terrain :

1. **Tolerance de saisie.** Un enfant qui ecrit `0,75`, `3/4`, `75 %` ou `.75`
   a la meme reponse juste. Une virgule francaise ou une espace insecable ne
   doivent jamais couter un point.
2. **Correction utile.** En cas d'echec, l'enfant n'a pas le code mais il a la
   correction detaillee : on ne dit pas seulement "faux", on tente de dire
   *pourquoi* (erreur de virgule, fraction inversee, signe oublie, faute
   d'accord...). C'est ce qui rend le temps de carence formateur.

Module volontairement pur : aucune I/O, aucune dependance externe.
"""

from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any

from app.models.enums import AUTO_GRADED_TYPES, QuestionType

CORRECT_THRESHOLD = 0.999  # un item n'est "juste" que s'il est entierement juste


@dataclass(slots=True)
class GradeResult:
    """Verdict pour une reponse."""

    score: float  # 0.0 .. 1.0 (credit partiel autorise)
    is_correct: bool
    needs_manual_review: bool = False
    expected: Any = None
    given: Any = None
    detail: str | None = None
    diagnosis: str | None = None
    per_part: list[dict[str, Any]] = field(default_factory=list)

    def as_feedback(self, explanation: str | None = None) -> dict[str, Any]:
        return {
            "score": round(self.score, 4),
            "is_correct": self.is_correct,
            "expected": self.expected,
            "given": self.given,
            "detail": self.detail,
            "diagnosis": self.diagnosis,
            "per_part": self.per_part,
            "explanation": explanation,
            "needs_manual_review": self.needs_manual_review,
        }


# ---------------------------------------------------------------------------
# Normalisation du texte
# ---------------------------------------------------------------------------

_PUNCT = re.compile(r"[^\w\s]", flags=re.UNICODE)
_SPACES = re.compile(r"\s+")


def strip_accents(text: str) -> str:
    return "".join(
        ch for ch in unicodedata.normalize("NFD", text) if unicodedata.category(ch) != "Mn"
    )


def normalize_text(
    text: Any,
    *,
    lowercase: bool = True,
    accents: bool = True,
    punctuation: bool = True,
    articles: bool = False,
) -> str:
    s = "" if text is None else str(text)
    s = s.replace(" ", " ").replace(" ", " ").strip()
    if lowercase:
        s = s.lower()
    if accents:
        s = strip_accents(s)
    if punctuation:
        s = _PUNCT.sub(" ", s)
    if articles:
        s = re.sub(r"\b(le|la|les|l|un|une|des|du|de|d)\b", " ", s)
    return _SPACES.sub(" ", s).strip()


def levenshtein(a: str, b: str) -> int:
    """Distance d'edition (implementation iterative, memoire O(min(n, m)))."""
    if a == b:
        return 0
    if len(a) < len(b):
        a, b = b, a
    if not b:
        return len(a)
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        current = [i]
        for j, cb in enumerate(b, start=1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (ca != cb)))
        previous = current
    return previous[-1]


# ---------------------------------------------------------------------------
# Normalisation des nombres
# ---------------------------------------------------------------------------

_MIXED = re.compile(r"^([+-]?\d+)\s+(\d+)\s*/\s*(\d+)$")  # "1 1/2"
_FRACTION = re.compile(r"^([+-]?\d+(?:[.,]\d+)?)\s*/\s*([+-]?\d+(?:[.,]\d+)?)$")
_NUMBER = re.compile(r"^[+-]?(?:\d+(?:[.,]\d*)?|[.,]\d+)$")
_UNIT_SUFFIX = re.compile(
    r"\s*(cm2|cm3|m2|m3|km/h|km|cm|mm|dm|hm|dam|m|kg|hg|dag|g|dg|cg|mg|t|l|dl|cl|ml|"
    r"h|min|s|eur|euros?|e|%|€|°c|°)\.?$",
    flags=re.IGNORECASE,
)


def parse_number(raw: Any) -> Fraction | None:
    """Convertit une saisie humaine en fraction exacte.

    Accepte : `3,14` `3.14` `3/4` `1 1/2` `50%` `1 000` `12 cm` `.5` `2e3`.
    Renvoie None si ce n'est pas un nombre.
    """
    if raw is None:
        return None
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int | float | Fraction):
        return Fraction(raw).limit_denominator(10**9)

    s = str(raw).strip().lower()
    if not s:
        return None
    s = s.replace(" ", " ").replace(" ", " ")
    s = s.replace("−", "-").replace("×", "*").replace("÷", "/")

    percent = False
    unit_match = _UNIT_SUFFIX.search(s)
    if unit_match:
        if unit_match.group(1) in {
            "%",
        }:
            percent = True
        s = s[: unit_match.start()].strip()

    # Espaces separateurs de milliers : "1 000 000" -> "1000000"
    if re.fullmatch(r"[+-]?\d{1,3}(?: \d{3})+(?:[.,]\d+)?", s):
        s = s.replace(" ", "")

    mixed = _MIXED.match(s)
    if mixed:
        whole, num, den = (int(g) for g in mixed.groups())
        if den == 0:
            return None
        sign = -1 if whole < 0 else 1
        return Fraction(abs(whole) * den + num, den) * sign

    frac = _FRACTION.match(s)
    if frac:
        try:
            num = Fraction(frac.group(1).replace(",", "."))
            den = Fraction(frac.group(2).replace(",", "."))
        except (ValueError, ZeroDivisionError):
            return None
        if den == 0:
            return None
        return num / den

    if _NUMBER.match(s):
        value = Fraction(s.replace(",", "."))
        return value / 100 if percent else value

    # Notation scientifique
    try:
        value = Fraction(float(s.replace(",", "."))).limit_denominator(10**9)
    except (ValueError, ZeroDivisionError, OverflowError):
        return None
    return value / 100 if percent else value


def numbers_match(given: Fraction, expected: Fraction, tolerance: float = 0.0) -> bool:
    if tolerance <= 0:
        return given == expected
    return abs(float(given) - float(expected)) <= tolerance + 1e-12


# ---------------------------------------------------------------------------
# Diagnostic des erreurs frequentes
# ---------------------------------------------------------------------------


def diagnose_numeric(given: Fraction | None, expected: Fraction) -> str | None:
    """Traduit un ecart typique en conseil comprehensible par un enfant."""
    if given is None:
        return "Je n'ai pas reconnu de nombre dans ta reponse."
    if given == expected:
        return None
    if given == -expected:
        return "Le resultat est bon mais le signe est inverse : attention au moins."
    if expected != 0:
        ratio = float(given) / float(expected)
        for power, label in ((10, "10"), (100, "100"), (1000, "1000")):
            if math.isclose(ratio, power, rel_tol=1e-6):
                return f"Ta reponse est {label} fois trop grande : verifie la virgule ou les zeros."
            if math.isclose(ratio, 1 / power, rel_tol=1e-6):
                return f"Ta reponse est {label} fois trop petite : verifie la virgule ou les zeros."
    if given != 0 and expected != 0 and given == 1 / expected:
        return "Tu as inverse la fraction (numerateur et denominateur echanges)."
    diff = abs(float(given) - float(expected))
    if math.isclose(diff, 1.0, rel_tol=1e-9):
        return "Il ne manque (ou il ne reste) qu'une unite : verifie ta retenue."
    if expected != 0 and abs(diff / float(expected)) < 0.05:
        return "Tu es tres proche : c'est sans doute une erreur de calcul en fin d'operation."
    return None


def diagnose_text(given: str, expected: str, options: dict[str, Any] | None = None) -> str | None:
    """Explique l'ecart, en respectant les regles de normalisation de l'item.

    `options` sont celles utilisees pour la correction : si l'item exige les
    accents, on doit pouvoir dire "il ne manque que les accents" plutot que de
    conclure a tort que la reponse est juste.
    """
    if not given.strip():
        return "Tu n'as rien ecrit."
    options = options or {}
    g = normalize_text(given, **options)
    e = normalize_text(expected, **options)
    if g == e:
        return None
    if strip_accents(g) == strip_accents(e):
        return "C'est le bon mot : il ne manque que les accents."
    g, e = strip_accents(g), strip_accents(e)
    distance = levenshtein(g, e)
    if distance == 1:
        return "Il n'y a qu'une lettre de difference : relis l'orthographe."
    if distance <= 2 and abs(len(g) - len(e)) <= 2:
        return "Le mot est presque juste : verifie l'orthographe."
    if sorted(g.split()) == sorted(e.split()):
        return "Tous les mots y sont, mais l'ordre n'est pas le bon."
    return None


# ---------------------------------------------------------------------------
# Extraction de la reponse de l'enfant
# ---------------------------------------------------------------------------


def _extract(answer: dict[str, Any] | None, *keys: str) -> Any:
    if not answer:
        return None
    for key in keys:
        if key in answer and answer[key] is not None:
            return answer[key]
    return answer.get("value")


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list | tuple | set):
        return list(value)
    return [value]


# ---------------------------------------------------------------------------
# Correcteurs par type
# ---------------------------------------------------------------------------


def _grade_mcq_single(spec: dict[str, Any], answer: dict[str, Any] | None) -> GradeResult:
    expected = _as_list(spec.get("correct", spec.get("value")))
    given = _extract(answer, "choice", "choices")
    given_one = _as_list(given)[:1]
    ok = bool(given_one) and str(given_one[0]) in {str(x) for x in expected}
    return GradeResult(
        score=1.0 if ok else 0.0,
        is_correct=ok,
        expected=expected,
        given=given,
        detail=None if ok else "Ce n'est pas la bonne proposition.",
    )


def _grade_mcq_multi(spec: dict[str, Any], answer: dict[str, Any] | None) -> GradeResult:
    expected = {str(x) for x in _as_list(spec.get("correct", spec.get("value")))}
    given = {str(x) for x in _as_list(_extract(answer, "choices", "choice"))}
    if not expected:
        return GradeResult(0.0, False, expected=[], given=sorted(given))
    hits = len(expected & given)
    wrong = len(given - expected)
    if spec.get("partial_credit", True):
        # Bareme "cases a cocher" : chaque bonne case rapporte, chaque mauvaise penalise.
        raw = (hits - wrong) / len(expected)
        score = max(0.0, min(1.0, raw))
    else:
        score = 1.0 if given == expected else 0.0
    detail = None
    if score < CORRECT_THRESHOLD:
        missing = sorted(expected - given)
        extra = sorted(given - expected)
        parts = []
        if missing:
            parts.append(f"il manque {', '.join(missing)}")
        if extra:
            parts.append(f"a tort : {', '.join(extra)}")
        detail = "Selection incomplete ou erronee (" + " ; ".join(parts) + ")."
    return GradeResult(
        score=score,
        is_correct=score >= CORRECT_THRESHOLD,
        expected=sorted(expected),
        given=sorted(given),
        detail=detail,
    )


def _grade_true_false(spec: dict[str, Any], answer: dict[str, Any] | None) -> GradeResult:
    expected = spec.get("correct", spec.get("value"))
    given = _extract(answer, "value", "choice")
    if isinstance(given, str):
        low = normalize_text(given)
        given = (
            True
            if low in {"vrai", "true", "oui", "v", "1"}
            else (False if low in {"faux", "false", "non", "f", "0"} else None)
        )
    ok = given is not None and bool(given) == bool(expected)
    return GradeResult(
        score=1.0 if ok else 0.0,
        is_correct=ok,
        expected=expected,
        given=given,
        detail=None if ok else "La proposition inverse etait attendue.",
    )


def _grade_numeric(spec: dict[str, Any], answer: dict[str, Any] | None) -> GradeResult:
    raw_given = _extract(answer, "value", "text", "transcript")
    given = parse_number(raw_given)
    tolerance = float(spec.get("tolerance", 0) or 0)

    candidates: list[Fraction] = []
    for key in ("value", "correct"):
        if key in spec and spec[key] is not None:
            parsed = parse_number(spec[key])
            if parsed is not None:
                candidates.append(parsed)
    for alt in _as_list(spec.get("accept")):
        parsed = parse_number(alt)
        if parsed is not None:
            candidates.append(parsed)

    if not candidates:
        return GradeResult(
            0.0, False, needs_manual_review=True, given=raw_given, detail="Bareme numerique absent."
        )

    ok = given is not None and any(numbers_match(given, c, tolerance) for c in candidates)
    expected_display = spec.get("display") or _fraction_display(candidates[0])

    unit_expected = spec.get("unit")
    unit_note = None
    if (
        ok
        and spec.get("require_unit")
        and unit_expected
        and isinstance(raw_given, str)
        and unit_expected.lower() not in raw_given.lower()
    ):
        ok = False
        unit_note = f"Le resultat est bon mais l'unite ({unit_expected}) manque."

    return GradeResult(
        score=1.0 if ok else 0.0,
        is_correct=ok,
        expected=expected_display,
        given=raw_given,
        detail=unit_note,
        diagnosis=None if ok else diagnose_numeric(given, candidates[0]),
    )


def _fraction_display(value: Fraction) -> str:
    if value.denominator == 1:
        return str(value.numerator)
    as_float = float(value)
    if abs(as_float - round(as_float, 6)) < 1e-12 and len(str(as_float)) <= 12:
        return str(as_float).replace(".", ",")
    return f"{value.numerator}/{value.denominator}"


def _grade_short_text(spec: dict[str, Any], answer: dict[str, Any] | None) -> GradeResult:
    raw_given = _extract(answer, "value", "text", "transcript") or ""
    accepted = [
        str(x) for x in _as_list(spec.get("accept", spec.get("correct", spec.get("value"))))
    ]
    if not accepted:
        return GradeResult(0.0, False, needs_manual_review=True, given=raw_given)

    opts = spec.get("normalize", {})
    kwargs = {
        "lowercase": opts.get("lowercase", True),
        "accents": opts.get("accents", True),
        "punctuation": opts.get("punctuation", True),
        "articles": opts.get("articles", False),
    }
    given_norm = normalize_text(raw_given, **kwargs)
    max_distance = int(spec.get("max_distance", 0))

    ok = False
    for candidate in accepted:
        cand_norm = normalize_text(candidate, **kwargs)
        if given_norm == cand_norm:
            ok = True
            break
        if max_distance and given_norm and levenshtein(given_norm, cand_norm) <= max_distance:
            ok = True
            break

    return GradeResult(
        score=1.0 if ok else 0.0,
        is_correct=ok,
        expected=accepted[0],
        given=raw_given,
        diagnosis=None if ok else diagnose_text(str(raw_given), accepted[0], kwargs),
    )


def _grade_fill_blank(spec: dict[str, Any], answer: dict[str, Any] | None) -> GradeResult:
    blanks = spec.get("blanks") or []
    given_values = _as_list(_extract(answer, "values", "value"))
    if not blanks:
        return GradeResult(0.0, False, needs_manual_review=True, given=given_values)

    per_part: list[dict[str, Any]] = []
    hits = 0
    for index, blank in enumerate(blanks):
        sub_answer = {"value": given_values[index] if index < len(given_values) else None}
        sub = _grade_short_text(blank, sub_answer)
        hits += 1 if sub.is_correct else 0
        per_part.append(
            {
                "index": index,
                "is_correct": sub.is_correct,
                "expected": sub.expected,
                "given": sub.given,
                "diagnosis": sub.diagnosis,
            }
        )
    score = hits / len(blanks)
    return GradeResult(
        score=score,
        is_correct=score >= CORRECT_THRESHOLD,
        expected=[b.get("accept", b.get("value")) for b in blanks],
        given=given_values,
        per_part=per_part,
        detail=None if score >= CORRECT_THRESHOLD else f"{hits}/{len(blanks)} trous corrects.",
    )


def _grade_ordering(spec: dict[str, Any], answer: dict[str, Any] | None) -> GradeResult:
    expected = [str(x) for x in _as_list(spec.get("order", spec.get("correct")))]
    given = [str(x) for x in _as_list(_extract(answer, "order", "values", "value"))]
    if not expected:
        return GradeResult(0.0, False, needs_manual_review=True, given=given)
    if given == expected:
        return GradeResult(1.0, True, expected=expected, given=given)
    # Credit partiel : proportion de paires consecutives correctement ordonnees.
    pairs_ok = sum(
        1
        for i in range(len(expected) - 1)
        if _index_of(given, expected[i]) >= 0
        and _index_of(given, expected[i]) < _index_of(given, expected[i + 1])
    )
    score = pairs_ok / max(1, len(expected) - 1)
    return GradeResult(
        score=score,
        is_correct=False,
        expected=expected,
        given=given,
        detail="L'ordre n'est pas tout a fait le bon.",
        diagnosis=("Tu as inverse l'ordre du debut a la fin." if given == expected[::-1] else None),
    )


def _index_of(seq: list[str], value: str) -> int:
    try:
        return seq.index(value)
    except ValueError:
        return -1


def _grade_matching(spec: dict[str, Any], answer: dict[str, Any] | None) -> GradeResult:
    expected = {str(k): str(v) for k, v in (spec.get("pairs") or {}).items()}
    raw = _extract(answer, "pairs", "value") or {}
    given = {str(k): str(v) for k, v in raw.items()} if isinstance(raw, dict) else {}
    if not expected:
        return GradeResult(0.0, False, needs_manual_review=True, given=given)
    hits = sum(1 for k, v in expected.items() if given.get(k) == v)
    score = hits / len(expected)
    return GradeResult(
        score=score,
        is_correct=score >= CORRECT_THRESHOLD,
        expected=expected,
        given=given,
        per_part=[
            {"key": k, "expected": v, "given": given.get(k), "is_correct": given.get(k) == v}
            for k, v in expected.items()
        ],
        detail=None
        if score >= CORRECT_THRESHOLD
        else f"{hits}/{len(expected)} associations justes.",
    )


def _grade_expression(spec: dict[str, Any], answer: dict[str, Any] | None) -> GradeResult:
    """Saisie assistee : fraction, operation posee, expression a valeur numerique.

    On compare les **valeurs** (3/4 == 0,75) sauf si le bareme exige une forme
    canonique (`require_form: "fraction_irreductible"`).
    """
    raw_given = _extract(answer, "value", "expression", "text", "transcript")
    result = _grade_numeric(spec, {"value": raw_given})
    if not result.is_correct:
        return result

    require = spec.get("require_form")
    if require == "fraction_irreductible":
        parsed_str = str(raw_given).strip()
        if "/" in parsed_str:
            num, _, den = parsed_str.partition("/")
            try:
                if math.gcd(int(num), int(den)) != 1:
                    return GradeResult(
                        score=0.5,
                        is_correct=False,
                        expected=result.expected,
                        given=raw_given,
                        detail="La valeur est bonne mais la fraction n'est pas irreductible.",
                        diagnosis="Simplifie ta fraction en divisant en haut et en bas.",
                    )
            except ValueError:
                pass
    return result


def _grade_handwritten(spec: dict[str, Any], answer: dict[str, Any] | None) -> GradeResult:
    """Ardoise : on tente la correction automatique sur la transcription fournie.

    Si l'appareil n'a pas su transcrire, l'item part en validation parentale
    plutot que d'etre compte faux : un enfant ne doit jamais etre penalise par
    la reconnaissance d'ecriture.
    """
    transcript = _extract(answer, "transcript", "value", "text")
    has_strokes = bool((answer or {}).get("strokes") or (answer or {}).get("has_strokes"))
    if transcript in (None, ""):
        return GradeResult(
            score=0.0,
            is_correct=False,
            needs_manual_review=has_strokes,
            expected=spec.get("display") or spec.get("value"),
            given=None,
            detail=(
                "Reponse manuscrite a valider par un parent." if has_strokes else "Aucune reponse."
            ),
        )
    sub = (
        _grade_numeric(spec, {"value": transcript})
        if _looks_numeric(spec)
        else _grade_short_text(spec, {"value": transcript})
    )
    if not sub.is_correct:
        # Doute sur la transcription : on laisse le parent trancher.
        sub.needs_manual_review = bool(spec.get("manual_fallback", True)) and has_strokes
    return sub


def _looks_numeric(spec: dict[str, Any]) -> bool:
    return any(key in spec and parse_number(spec[key]) is not None for key in ("value", "correct"))


_GRADERS = {
    QuestionType.MCQ_SINGLE: _grade_mcq_single,
    QuestionType.MCQ_MULTI: _grade_mcq_multi,
    QuestionType.TRUE_FALSE: _grade_true_false,
    QuestionType.NUMERIC: _grade_numeric,
    QuestionType.SHORT_TEXT: _grade_short_text,
    QuestionType.FILL_BLANK: _grade_fill_blank,
    QuestionType.ORDERING: _grade_ordering,
    QuestionType.MATCHING: _grade_matching,
    QuestionType.EXPRESSION: _grade_expression,
    QuestionType.HANDWRITTEN: _grade_handwritten,
}


def grade_answer(
    question_type: QuestionType | str,
    answer_spec: dict[str, Any] | None,
    given_answer: dict[str, Any] | None,
) -> GradeResult:
    """Point d'entree unique du correcteur."""
    qtype = QuestionType(question_type)
    spec = answer_spec or {}

    if given_answer is None or (isinstance(given_answer, dict) and not given_answer):
        return GradeResult(
            score=0.0,
            is_correct=False,
            expected=spec.get("display") or spec.get("value") or spec.get("correct"),
            given=None,
            detail="Aucune reponse donnee.",
        )

    grader = _GRADERS.get(qtype)
    if grader is None:  # VOICE (V2) et tout type non encore automatisable
        return GradeResult(
            score=0.0,
            is_correct=False,
            needs_manual_review=True,
            given=given_answer,
            detail="Ce type de reponse demande une validation humaine.",
        )
    return grader(spec, given_answer)


def is_auto_gradable(question_type: QuestionType | str) -> bool:
    return QuestionType(question_type) in AUTO_GRADED_TYPES
