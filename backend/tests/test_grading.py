"""Correcteur : tolerance de saisie, credit partiel, diagnostic pedagogique."""

from __future__ import annotations

from fractions import Fraction

import pytest

from app.models.enums import QuestionType as Q
from app.services.grading import (
    grade_answer,
    is_auto_gradable,
    levenshtein,
    normalize_text,
    parse_number,
)

# --- Lecture des nombres ---------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("42", Fraction(42)),
        ("3,14", Fraction(157, 50)),
        ("3.14", Fraction(157, 50)),
        ("3/4", Fraction(3, 4)),
        ("1 1/2", Fraction(3, 2)),
        ("-2,5", Fraction(-5, 2)),
        ("50%", Fraction(1, 2)),
        ("1 000", Fraction(1000)),
        ("1 234 567", Fraction(1234567)),
        ("12 cm", Fraction(12)),
        ("2,5 kg", Fraction(5, 2)),
        (",5", Fraction(1, 2)),
        ("0", Fraction(0)),
        (7, Fraction(7)),
        (2.5, Fraction(5, 2)),
    ],
)
def test_parse_number(raw, expected):
    assert parse_number(raw) == expected


@pytest.mark.parametrize("raw", ["", "abc", None, "3/0", "//", True, False])
def test_parse_number_rejects(raw):
    assert parse_number(raw) is None


def test_espace_insecable_est_toleree():
    assert parse_number("1 000") == Fraction(1000)
    assert parse_number("1 000") == Fraction(1000)


# --- Normalisation du texte ------------------------------------------------


def test_normalize_text():
    assert normalize_text("Élysée !") == "elysee"
    assert normalize_text("  Le  Chat  ") == "le chat"
    assert normalize_text("le chat", articles=True) == "chat"


def test_levenshtein():
    assert levenshtein("chat", "chat") == 0
    assert levenshtein("chat", "chats") == 1
    assert levenshtein("", "abc") == 3


# --- QCM -------------------------------------------------------------------


def test_qcm_simple():
    spec = {"correct": ["b"]}
    assert grade_answer(Q.MCQ_SINGLE, spec, {"choice": "b"}).is_correct
    assert not grade_answer(Q.MCQ_SINGLE, spec, {"choice": "a"}).is_correct


def test_qcm_multiple_credit_partiel():
    spec = {"correct": ["a", "c"], "partial_credit": True}
    assert grade_answer(Q.MCQ_MULTI, spec, {"choices": ["a", "c"]}).score == 1.0
    assert grade_answer(Q.MCQ_MULTI, spec, {"choices": ["a"]}).score == 0.5
    # Une case cochee a tort annule une bonne reponse.
    assert grade_answer(Q.MCQ_MULTI, spec, {"choices": ["a", "b"]}).score == 0.0
    assert grade_answer(Q.MCQ_MULTI, spec, {"choices": ["b", "d"]}).score == 0.0


def test_vrai_faux_accepte_les_mots():
    spec = {"correct": True}
    for given in (True, "vrai", "Vrai", "oui", "1"):
        assert grade_answer(Q.TRUE_FALSE, spec, {"value": given}).is_correct
    for given in (False, "faux", "non"):
        assert not grade_answer(Q.TRUE_FALSE, spec, {"value": given}).is_correct


# --- Numerique -------------------------------------------------------------


def test_numerique_formes_equivalentes():
    spec = {"value": 0.75}
    for given in ("0,75", "0.75", "3/4", "75%", ".75"):
        assert grade_answer(Q.NUMERIC, spec, {"value": given}).is_correct, given


def test_numerique_tolerance():
    spec = {"value": 3.14159, "tolerance": 0.01}
    assert grade_answer(Q.NUMERIC, spec, {"value": "3,14"}).is_correct
    assert not grade_answer(Q.NUMERIC, spec, {"value": "3,1"}).is_correct


def test_numerique_unite_exigee():
    spec = {"value": 12, "unit": "cm", "require_unit": True}
    assert grade_answer(Q.NUMERIC, spec, {"value": "12 cm"}).is_correct
    result = grade_answer(Q.NUMERIC, spec, {"value": "12"})
    assert not result.is_correct
    assert "unité" in (result.detail or "")


@pytest.mark.parametrize(
    ("expected", "given", "fragment"),
    [
        (56, "560", "10 fois trop grande"),
        (560, "56", "10 fois trop petite"),
        (7, "-7", "signe"),
        (25, "24", "retenue"),
    ],
)
def test_diagnostic_numerique(expected, given, fragment):
    result = grade_answer(Q.NUMERIC, {"value": expected}, {"value": given})
    assert not result.is_correct
    assert fragment in (result.diagnosis or "")


# --- Texte -----------------------------------------------------------------


def test_texte_accents_et_casse():
    spec = {"accept": ["Élysée"]}
    assert grade_answer(Q.SHORT_TEXT, spec, {"value": "elysee"}).is_correct
    assert grade_answer(Q.SHORT_TEXT, spec, {"value": "ELYSEE"}).is_correct


def test_texte_distance_configurable():
    strict = {"accept": ["Paris"], "max_distance": 0}
    lache = {"accept": ["Paris"], "max_distance": 1}
    assert not grade_answer(Q.SHORT_TEXT, strict, {"value": "Pari"}).is_correct
    assert grade_answer(Q.SHORT_TEXT, lache, {"value": "Pari"}).is_correct


def test_diagnostic_texte_accents():
    result = grade_answer(
        Q.SHORT_TEXT, {"accept": ["élève"], "normalize": {"accents": False}}, {"value": "eleve"}
    )
    assert "accents" in (result.diagnosis or "")


# --- Autres formats --------------------------------------------------------


def test_texte_a_trous():
    spec = {"blanks": [{"accept": ["ai"]}, {"accept": ["sont"]}]}
    plein = grade_answer(Q.FILL_BLANK, spec, {"values": ["ai", "sont"]})
    assert plein.is_correct and plein.score == 1.0
    moitie = grade_answer(Q.FILL_BLANK, spec, {"values": ["ai", "son"]})
    assert moitie.score == 0.5
    assert moitie.per_part[1]["is_correct"] is False


def test_remise_en_ordre_credit_partiel():
    spec = {"order": ["a", "b", "c", "d"]}
    assert grade_answer(Q.ORDERING, spec, {"order": ["a", "b", "c", "d"]}).score == 1.0
    inverse = grade_answer(Q.ORDERING, spec, {"order": ["d", "c", "b", "a"]})
    assert inverse.score == 0.0
    assert "inverse" in (inverse.diagnosis or "")
    presque = grade_answer(Q.ORDERING, spec, {"order": ["a", "b", "d", "c"]})
    assert 0 < presque.score < 1


def test_associations():
    spec = {"pairs": {"1": "a", "2": "b", "3": "c"}}
    assert grade_answer(Q.MATCHING, spec, {"pairs": {"1": "a", "2": "b", "3": "c"}}).is_correct
    partiel = grade_answer(Q.MATCHING, spec, {"pairs": {"1": "a", "2": "c", "3": "b"}})
    assert round(partiel.score, 3) == round(1 / 3, 3)


def test_expression_fraction_irreductible():
    spec = {"value": "3/4", "require_form": "fraction_irreductible"}
    assert grade_answer(Q.EXPRESSION, spec, {"value": "3/4"}).is_correct
    non_simplifiee = grade_answer(Q.EXPRESSION, spec, {"value": "6/8"})
    assert not non_simplifiee.is_correct
    assert non_simplifiee.score == 0.5  # la valeur est juste, la forme non
    assert "Simplifie" in (non_simplifiee.diagnosis or "")


def test_manuscrit_sans_transcription_part_en_revue_parentale():
    result = grade_answer(Q.HANDWRITTEN, {"value": 42}, {"has_strokes": True})
    assert result.needs_manual_review
    assert not result.is_correct


def test_manuscrit_avec_transcription_correcte():
    result = grade_answer(Q.HANDWRITTEN, {"value": 42}, {"transcript": "42", "has_strokes": True})
    assert result.is_correct
    assert not result.needs_manual_review


def test_manuscrit_transcription_douteuse_demande_un_arbitrage():
    result = grade_answer(Q.HANDWRITTEN, {"value": 42}, {"transcript": "4Z", "has_strokes": True})
    assert not result.is_correct
    assert result.needs_manual_review


def test_absence_de_reponse():
    result = grade_answer(Q.NUMERIC, {"value": 1}, None)
    assert result.score == 0.0
    assert not result.needs_manual_review
    assert "Aucune réponse" in (result.detail or "")


def test_type_vocal_demande_une_validation_humaine():
    result = grade_answer(Q.VOICE, {"value": "bonjour"}, {"audio": "..."})
    assert result.needs_manual_review


def test_auto_gradable():
    assert is_auto_gradable(Q.MCQ_SINGLE)
    assert not is_auto_gradable(Q.HANDWRITTEN)
    assert not is_auto_gradable(Q.VOICE)
