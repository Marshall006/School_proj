"""Experience, conversion en minutes, resolution des regles et couvre-feu."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime

import pytest

from app.content.numerals import en_lettres
from app.models.enums import PeriodType
from app.models.family import Child
from app.models.policy import CalendarPeriod
from app.services.lockouts import escalated_minutes
from app.services.policy import (
    EffectivePolicy,
    _default_policy,
    is_within_curfew,
    next_curfew_end,
    resolve_period_type,
)
from app.services.xp import (
    apply_diminishing,
    base_xp_for_answer,
    compute_assessment_xp,
    diminishing_factor,
    quote_conversion,
    update_streak,
)

# --- Gains d'experience ----------------------------------------------------


def test_gain_proportionnel_a_la_difficulte():
    assert base_xp_for_answer(1.0, 1) < base_xp_for_answer(1.0, 3)
    assert base_xp_for_answer(1.0, 3) < base_xp_for_answer(1.0, 5)


def test_credit_partiel_rapporte_partiellement():
    assert base_xp_for_answer(0.5, 3) == pytest.approx(base_xp_for_answer(1.0, 3) / 2)


def test_rendement_decroissant():
    assert diminishing_factor(0) == 1.0
    assert diminishing_factor(400) == 0.5
    assert diminishing_factor(900) == 0.25
    frais = apply_diminishing(100, 0)
    fatigue = apply_diminishing(100, 700)
    assert frais > fatigue * 3


def test_le_farming_ne_paie_pas():
    """Enchainer les evaluations faciles rapporte de moins en moins."""
    scores = [(1.0, 1)] * 20
    premier, _ = compute_assessment_xp(
        item_scores=scores, passed=True, score_pct=100.0, xp_already_today=0
    )
    dixieme, _ = compute_assessment_xp(
        item_scores=scores, passed=True, score_pct=100.0, xp_already_today=1500
    )
    assert dixieme < premier / 3


def test_bonus_de_reussite_et_de_sans_faute():
    sans_faute, grants = compute_assessment_xp(
        item_scores=[(1.0, 3)] * 10, passed=True, score_pct=100.0
    )
    juste_passe, _ = compute_assessment_xp(
        item_scores=[(1.0, 3)] * 7 + [(0.0, 3)] * 3, passed=True, score_pct=70.0
    )
    assert sans_faute > juste_passe
    assert {g.reason.value for g in grants} >= {
        "correct_answer",
        "assessment_passed",
        "perfect_score",
    }


def test_lacune_comblee_rapporte_gros():
    sans, _ = compute_assessment_xp(item_scores=[(1.0, 3)] * 5, passed=True, score_pct=80.0)
    avec, grants = compute_assessment_xp(
        item_scores=[(1.0, 3)] * 5, passed=True, score_pct=80.0, cleared_weaknesses=2
    )
    assert avec > sans
    assert any(g.reason.value == "weakness_cleared" for g in grants)


def test_bonus_de_serie_plafonne():
    _, grants = compute_assessment_xp(
        item_scores=[(1.0, 3)], passed=True, score_pct=100.0, streak_days=30
    )
    serie = next(g for g in grants if g.reason.value == "streak_bonus")
    assert serie.amount <= 50


def test_echec_rapporte_quand_meme_les_bonnes_reponses():
    total, grants = compute_assessment_xp(
        item_scores=[(1.0, 3)] * 4 + [(0.0, 3)] * 6, passed=False, score_pct=40.0
    )
    assert total > 0
    assert not any(g.reason.value == "assessment_passed" for g in grants)


# --- Conversion XP -> minutes ---------------------------------------------


def test_conversion_arrondie_au_pas_de_cinq_minutes():
    quote = quote_conversion(
        xp_balance=1000,
        xp_to_spend=None,
        minutes_per_100_xp=15,
        daily_bonus_used_minutes=0,
        daily_bonus_cap_minutes=60,
    )
    assert quote.minutes % 5 == 0
    assert quote.minutes == 60  # plafonne
    assert quote.capped_by_daily_limit


def test_conversion_partielle():
    quote = quote_conversion(
        xp_balance=500,
        xp_to_spend=200,
        minutes_per_100_xp=15,
        daily_bonus_used_minutes=0,
        daily_bonus_cap_minutes=120,
    )
    assert quote.minutes == 30
    assert quote.xp_spent == 200
    assert quote.xp_remaining == 300


def test_solde_insuffisant():
    quote = quote_conversion(
        xp_balance=10,
        xp_to_spend=None,
        minutes_per_100_xp=15,
        daily_bonus_used_minutes=0,
        daily_bonus_cap_minutes=60,
    )
    assert not quote.ok
    assert "au moins" in (quote.reason or "")


def test_plafond_quotidien_atteint():
    quote = quote_conversion(
        xp_balance=10_000,
        xp_to_spend=None,
        minutes_per_100_xp=15,
        daily_bonus_used_minutes=60,
        daily_bonus_cap_minutes=60,
    )
    assert not quote.ok
    assert "Plafond" in (quote.reason or "")


def test_conversion_desactivee():
    quote = quote_conversion(
        xp_balance=1000,
        xp_to_spend=None,
        minutes_per_100_xp=0,
        daily_bonus_used_minutes=0,
        daily_bonus_cap_minutes=60,
    )
    assert not quote.ok


def test_serie_de_jours():
    child = Child(family_id=None, display_name="X", grade_code="CM1")
    child.streak_days = 0
    child.last_activity_on = None
    assert update_streak(child, date(2026, 3, 10)) == 1
    assert update_streak(child, date(2026, 3, 10)) == 1  # deux fois le meme jour
    assert update_streak(child, date(2026, 3, 11)) == 2
    assert update_streak(child, date(2026, 3, 15)) == 1  # trou : la serie repart


# --- Regles et periodes ----------------------------------------------------


def test_periode_deduite_du_calendrier():
    vacances = CalendarPeriod(
        family_id=None,
        label="Vacances de printemps",
        period_type=PeriodType.HOLIDAY,
        start_date=date(2026, 4, 4),
        end_date=date(2026, 4, 20),
    )
    assert resolve_period_type([vacances], date(2026, 4, 10)) == PeriodType.HOLIDAY
    assert resolve_period_type([vacances], date(2026, 3, 10)) == PeriodType.SCHOOL  # un mardi
    assert resolve_period_type([vacances], date(2026, 3, 14)) == PeriodType.WEEKEND  # un samedi


def test_vacances_coupent_le_deverrouillage_direct_par_defaut():
    """En vacances il n'y a plus de devoirs : l'evaluation devient le seul chemin."""
    scolaire = _default_policy(PeriodType.SCHOOL, "Europe/Paris")
    vacances = _default_policy(PeriodType.HOLIDAY, "Europe/Paris")
    assert scolaire.allow_parent_direct_unlock
    assert not vacances.allow_parent_direct_unlock
    assert vacances.allow_assessment_unlock


def test_seuil_converti_en_note_sur_vingt():
    policy = _default_policy(PeriodType.SCHOOL, "Europe/Paris")
    assert policy.pass_score_pct == 70.0
    assert policy.pass_score_out_of_20 == 14.0


def curfew_policy(start: str | None, end: str | None) -> EffectivePolicy:
    base = _default_policy(PeriodType.SCHOOL, "Europe/Paris")
    return replace(base, curfew_start=start, curfew_end=end)


@pytest.mark.parametrize(
    ("heure_utc", "attendu"),
    [
        (datetime(2026, 3, 10, 20, 0, tzinfo=UTC), True),  # 21 h a Paris
        (datetime(2026, 3, 10, 23, 0, tzinfo=UTC), True),  # minuit
        (datetime(2026, 3, 10, 4, 0, tzinfo=UTC), True),  # 5 h
        (datetime(2026, 3, 10, 12, 0, tzinfo=UTC), False),  # 13 h
        (datetime(2026, 3, 10, 6, 30, tzinfo=UTC), False),  # 7 h 30
    ],
)
def test_couvre_feu_traverse_minuit(heure_utc, attendu):
    policy = curfew_policy("21:00", "07:00")
    assert is_within_curfew(policy, heure_utc) is attendu


def test_couvre_feu_sur_la_journee():
    policy = curfew_policy("13:00", "15:00")
    assert is_within_curfew(policy, datetime(2026, 3, 10, 13, 0, tzinfo=UTC))  # 14 h a Paris
    assert not is_within_curfew(policy, datetime(2026, 3, 10, 15, 0, tzinfo=UTC))  # 16 h


def test_couvre_feu_desactivable():
    assert not is_within_curfew(curfew_policy(None, None), datetime(2026, 3, 10, 23, tzinfo=UTC))
    assert not is_within_curfew(
        curfew_policy("21:00", "21:00"), datetime(2026, 3, 10, 23, tzinfo=UTC)
    )


def test_fin_du_couvre_feu():
    policy = curfew_policy("21:00", "07:00")
    fin = next_curfew_end(policy, datetime(2026, 3, 10, 23, 0, tzinfo=UTC))
    assert fin is not None and fin > datetime(2026, 3, 10, 23, 0, tzinfo=UTC)
    assert next_curfew_end(policy, datetime(2026, 3, 10, 12, 0, tzinfo=UTC)) is None


def test_escalade_du_temps_de_carence():
    assert escalated_minutes(120, failures_today=1, escalation=1.5) == 120
    assert escalated_minutes(120, failures_today=2, escalation=1.5) == 180
    assert escalated_minutes(120, failures_today=3, escalation=1.5) == 270
    assert escalated_minutes(120, failures_today=5, escalation=1.0) == 120  # escalade neutre


# --- Ecriture des nombres --------------------------------------------------


@pytest.mark.parametrize(
    ("valeur", "texte"),
    [
        (0, "zero"),
        (21, "vingt et un"),
        (71, "soixante et onze"),
        (80, "quatre-vingts"),
        (81, "quatre-vingt-un"),
        (100, "cent"),
        (200, "deux cents"),
        (201, "deux cent un"),
        (1000, "mille"),
        (80_000, "quatre-vingt mille"),
        (200_000, "deux cent mille"),
        (3247, "trois mille deux cent quarante-sept"),
        (1_000_000, "un million"),
        (300_000_000, "trois cents millions"),
    ],
)
def test_ecriture_en_lettres(valeur, texte):
    assert en_lettres(valeur) == texte
