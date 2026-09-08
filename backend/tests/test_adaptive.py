"""Moteur adaptatif : maitrise, epreuve equilibree, repetition espacee."""

from __future__ import annotations

import random
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.models.enums import MasteryBand
from app.services.adaptive import (
    BUCKET_TARGET_P,
    BUCKET_WEIGHTS,
    MasteryState,
    QuestionCandidate,
    TopicCandidate,
    allocate_counts,
    band_for,
    build_blueprint,
    classify_topics,
    identify_gaps,
    item_logit,
    predicted_success,
    select_question,
    target_difficulty_logit,
    update_mastery,
)

NOW = datetime(2026, 3, 15, 10, 0, tzinfo=UTC)


def make_topics(n: int, subject: str = "math") -> list[TopicCandidate]:
    return [
        TopicCandidate(
            topic_id=uuid.uuid4(),
            subject_code=subject,
            name=f"Notion {i}",
            question_count=10,
            position=i,
        )
        for i in range(n)
    ]


# --- Modele de niveau ------------------------------------------------------


def test_probabilite_de_reussite_est_monotone():
    assert predicted_success(0.0, 0.0) == pytest.approx(0.5)
    assert predicted_success(2.0, 0.0) > 0.8
    assert predicted_success(-2.0, 0.0) < 0.2


def test_difficulte_cible_inverse_la_prediction():
    for ability in (-1.0, 0.0, 1.5):
        for target in (0.6, 0.75, 0.9):
            logit = target_difficulty_logit(ability, target)
            assert predicted_success(ability, logit) == pytest.approx(target, abs=1e-9)


def test_paliers_de_maitrise():
    assert band_for(0.9, attempts=1) == MasteryBand.UNKNOWN  # trop peu de donnees
    assert band_for(0.2, attempts=10) == MasteryBand.FRAGILE
    assert band_for(0.6, attempts=10) == MasteryBand.EN_COURS
    assert band_for(0.8, attempts=10) == MasteryBand.ACQUIS
    assert band_for(0.95, attempts=10) == MasteryBand.EXPERT


def test_le_niveau_monte_avec_les_reussites():
    state = MasteryState(topic_id=uuid.uuid4(), subject_code="math")
    for _ in range(20):
        update_mastery(state, score=1.0, difficulty=3, at=NOW)
    assert state.ability > 1.0
    assert state.band == MasteryBand.EXPERT
    assert state.attempts == 20


def test_le_niveau_descend_avec_les_echecs():
    state = MasteryState(topic_id=uuid.uuid4(), subject_code="math", ability=1.5, ewma=0.9)
    for _ in range(15):
        update_mastery(state, score=0.0, difficulty=3, at=NOW)
    assert state.ability < 0.5
    assert state.band == MasteryBand.FRAGILE


def test_apprentissage_plus_rapide_au_debut():
    """Le pas d'ajustement decroit avec l'experience : le modele se stabilise."""
    neuf = MasteryState(topic_id=uuid.uuid4(), subject_code="math")
    chevronne = MasteryState(topic_id=uuid.uuid4(), subject_code="math", attempts=60)
    delta_neuf = update_mastery(neuf, score=1.0, difficulty=3, at=NOW).delta_ability
    delta_chevronne = update_mastery(chevronne, score=1.0, difficulty=3, at=NOW).delta_ability
    assert delta_neuf > delta_chevronne * 2


def test_repetition_espacee():
    state = MasteryState(topic_id=uuid.uuid4(), subject_code="math")
    update_mastery(state, score=1.0, difficulty=3, at=NOW)
    assert state.interval_days == 1.0
    update_mastery(state, score=1.0, difficulty=3, at=NOW + timedelta(days=1))
    assert state.interval_days == 3.0
    update_mastery(state, score=1.0, difficulty=3, at=NOW + timedelta(days=4))
    assert state.interval_days > 3.0
    # Un echec ramene la notion en revision immediate.
    update_mastery(state, score=0.0, difficulty=3, at=NOW + timedelta(days=10))
    assert state.interval_days == 0.0
    assert state.is_due(NOW + timedelta(days=10))


def test_calibrage_de_litem():
    """Un item reussi plus souvent que prevu est signale comme plus facile."""
    fort = MasteryState(topic_id=uuid.uuid4(), subject_code="math", ability=2.0)
    update = update_mastery(fort, score=0.0, difficulty=1, at=NOW)
    assert update.item_calibration_delta > 0  # l'item etait plus dur qu'annonce

    faible = MasteryState(topic_id=uuid.uuid4(), subject_code="math", ability=-2.0)
    update = update_mastery(faible, score=1.0, difficulty=5, at=NOW)
    assert update.item_calibration_delta < 0


# --- Composition de l'epreuve ---------------------------------------------


def test_repartition_des_trois_blocs():
    topics = make_topics(12)
    mastery = {}
    for index, topic in enumerate(topics):
        state = MasteryState(topic_id=topic.topic_id, subject_code="math", attempts=10)
        state.ewma = 0.2 if index < 4 else (0.6 if index < 8 else 0.95)
        mastery[topic.topic_id] = state

    blueprint = build_blueprint(
        candidates=topics, mastery=mastery, question_count=10, seed=42, at=NOW
    )
    distribution = blueprint.distribution
    assert sum(distribution.values()) == 10
    assert distribution["remediation"] == 4  # 40 %
    assert distribution["apprentissage"] == 4  # 40 %
    assert distribution["consolidation"] == 2  # 20 %


def test_epreuve_reproductible_a_graine_egale():
    topics = make_topics(10)
    mastery: dict = {}
    first = build_blueprint(candidates=topics, mastery=mastery, question_count=8, seed=7, at=NOW)
    second = build_blueprint(candidates=topics, mastery=mastery, question_count=8, seed=7, at=NOW)
    assert [s.topic_id for s in first.slots] == [s.topic_id for s in second.slots]
    assert [s.bucket for s in first.slots] == [s.bucket for s in second.slots]


def test_sans_lacune_la_part_de_remediation_est_redistribuee():
    topics = make_topics(6)
    mastery = {
        t.topic_id: MasteryState(topic_id=t.topic_id, subject_code="math", ewma=0.95, attempts=10)
        for t in topics
    }
    blueprint = build_blueprint(
        candidates=topics, mastery=mastery, question_count=10, seed=1, at=NOW
    )
    assert blueprint.distribution.get("remediation", 0) == 0
    assert sum(blueprint.distribution.values()) == 10


def test_notion_jamais_vue_va_en_apprentissage():
    topics = make_topics(3)
    buckets = classify_topics(topics, {}, NOW)
    assert len(buckets["apprentissage"]) == 3
    assert not buckets["remediation"]


def test_notion_en_retard_de_revision_va_en_remediation():
    topic = make_topics(1)[0]
    state = MasteryState(
        topic_id=topic.topic_id,
        subject_code="math",
        ewma=0.65,
        attempts=8,
        next_review_at=NOW - timedelta(days=3),
    )
    buckets = classify_topics([topic], {topic.topic_id: state}, NOW)
    assert len(buckets["remediation"]) == 1


def test_allocation_toujours_exacte():
    topics = make_topics(9)
    available = {
        "remediation": topics[:3],
        "apprentissage": topics[3:6],
        "consolidation": topics[6:],
    }
    for total in range(1, 31):
        counts = allocate_counts(total, available)
        assert sum(counts.values()) == total


def test_allocation_respecte_les_poids():
    topics = make_topics(30)
    available = {
        "remediation": topics[:10],
        "apprentissage": topics[10:20],
        "consolidation": topics[20:],
    }
    counts = allocate_counts(100, available)
    for bucket, weight in BUCKET_WEIGHTS.items():
        assert abs(counts[bucket] / 100 - weight) < 0.02


def test_difficulte_visee_par_bloc():
    topics = make_topics(9)
    mastery = {}
    for index, topic in enumerate(topics):
        state = MasteryState(topic_id=topic.topic_id, subject_code="math", attempts=10)
        state.ewma = 0.2 if index < 3 else (0.6 if index < 6 else 0.95)
        mastery[topic.topic_id] = state
    blueprint = build_blueprint(
        candidates=topics, mastery=mastery, question_count=9, seed=3, at=NOW
    )
    for slot in blueprint.slots:
        assert slot.target_p == pytest.approx(BUCKET_TARGET_P[slot.bucket])


def test_biais_de_difficulte_durcit_lepreuve():
    topics = make_topics(6)
    doux = build_blueprint(
        candidates=topics, mastery={}, question_count=6, difficulty_bias=-1.0, seed=5, at=NOW
    )
    dur = build_blueprint(
        candidates=topics, mastery={}, question_count=6, difficulty_bias=1.0, seed=5, at=NOW
    )
    assert dur.slots[0].target_p < doux.slots[0].target_p


def test_petit_vivier_ne_laisse_pas_de_trou():
    topics = make_topics(2)
    blueprint = build_blueprint(candidates=topics, mastery={}, question_count=10, seed=9, at=NOW)
    assert len(blueprint.slots) == 10


def test_notion_sans_question_est_ignoree():
    topics = make_topics(3)
    topics[0].question_count = 0
    buckets = classify_topics(topics, {}, NOW)
    assert len(buckets["apprentissage"]) == 2


# --- Choix de l'item -------------------------------------------------------


def test_choix_de_litem_le_plus_proche_de_la_cible():
    topics = make_topics(1)
    blueprint = build_blueprint(candidates=topics, mastery={}, question_count=1, seed=1, at=NOW)
    slot = blueprint.slots[0]
    pool = [
        QuestionCandidate(question_id=uuid.uuid4(), topic_id=slot.topic_id, difficulty=d)
        for d in (1, 2, 3, 4, 5)
    ]
    picked = select_question(slot, pool, random.Random(0))
    distances = [abs(item_logit(c.difficulty) - slot.target_logit) for c in pool]
    assert abs(item_logit(picked.difficulty) - slot.target_logit) == min(distances)


def test_exclusion_evite_les_doublons():
    topics = make_topics(1)
    blueprint = build_blueprint(candidates=topics, mastery={}, question_count=1, seed=1, at=NOW)
    slot = blueprint.slots[0]
    pool = [
        QuestionCandidate(question_id=uuid.uuid4(), topic_id=slot.topic_id, difficulty=3)
        for _ in range(3)
    ]
    first = select_question(slot, pool, random.Random(0))
    second = select_question(slot, pool, random.Random(0), exclude={first.question_id})
    assert second.question_id != first.question_id


def test_questions_recentes_sont_evitees():
    topics = make_topics(1)
    blueprint = build_blueprint(candidates=topics, mastery={}, question_count=1, seed=1, at=NOW)
    slot = blueprint.slots[0]
    vue_recemment = QuestionCandidate(
        question_id=uuid.uuid4(), topic_id=slot.topic_id, difficulty=3, last_served_rank=1.0
    )
    jamais_vue = QuestionCandidate(
        question_id=uuid.uuid4(), topic_id=slot.topic_id, difficulty=3, last_served_rank=0.0
    )
    picked = select_question(slot, [vue_recemment, jamais_vue], random.Random(0))
    assert picked.question_id == jamais_vue.question_id


def test_pool_vide_renvoie_none():
    topics = make_topics(1)
    blueprint = build_blueprint(candidates=topics, mastery={}, question_count=1, seed=1, at=NOW)
    assert select_question(blueprint.slots[0], [], random.Random(0)) is None


# --- Diagnostic ------------------------------------------------------------


def test_lacunes_classees_par_urgence():
    states = [
        MasteryState(topic_id=uuid.uuid4(), subject_code="math", ewma=0.9, attempts=10),
        MasteryState(topic_id=uuid.uuid4(), subject_code="francais", ewma=0.15, attempts=12),
        MasteryState(topic_id=uuid.uuid4(), subject_code="math", ewma=0.5, attempts=6),
    ]
    gaps = identify_gaps(states, limit=3, at=NOW)
    assert gaps[0]["subject_code"] == "francais"
    assert gaps[0]["urgency"] > gaps[-1]["urgency"]


def test_notion_jamais_travaillee_nest_pas_une_lacune():
    state = MasteryState(topic_id=uuid.uuid4(), subject_code="math", attempts=0)
    assert identify_gaps([state], at=NOW) == []
