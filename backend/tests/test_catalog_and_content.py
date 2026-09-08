"""Banque pedagogique : couverture, coherence des items, questions du parent."""

from __future__ import annotations

from random import Random

import pytest
from sqlalchemy import select

from app.content.catalog import COUNTRIES, DEFAULT_SEED_LEVELS, TOPICS, topics_for_level
from app.content.generators import REGISTRY
from app.content.seed import content_stats, seed_all
from app.models.content import Question, Topic
from app.models.enums import AUTO_GRADED_TYPES, QuestionType
from app.services.grading import grade_answer
from tests.helpers import correct_answer, wrong_answer


async def test_seed_idempotent(db):
    first = await seed_all(db, countries=("FR",), levels=(4,))
    second = await seed_all(db, countries=("FR",), levels=(4,))
    assert first["questions"] > 100
    assert second["questions"] == 0
    assert second["topics"] == 0


async def test_couverture_multi_pays(db):
    await seed_all(db, countries=("FR", "BJ"), levels=(4, 5))
    stats = await content_stats(db)
    pays = {row["country_code"] for row in stats["coverage"]}
    assert pays == {"FR", "BJ"}
    for row in stats["coverage"]:
        assert row["questions"] > 50, row


async def test_localisation_des_enonces(db):
    """Un probleme de monnaie parle euros en France, francs CFA au Benin."""
    await seed_all(db, countries=("FR", "BJ"), levels=(5,))
    for country, devise in (("FR", "EUR"), ("BJ", "FCFA")):
        rows = (
            (
                await db.execute(
                    select(Question.prompt)
                    .join(Topic, Topic.id == Question.topic_id)
                    .where(Topic.country_code == country, Topic.code == "math.problemes")
                )
            )
            .scalars()
            .all()
        )
        assert any(devise in prompt for prompt in rows), country


async def test_histoire_specifique_au_pays(db):
    await seed_all(db, countries=("BJ",), levels=(5,))
    prompts = (
        (
            await db.execute(
                select(Question.prompt)
                .join(Topic, Topic.id == Question.topic_id)
                .where(Topic.code == "hg.histoire")
            )
        )
        .scalars()
        .all()
    )
    assert any("Abomey" in p or "Dahomey" in p for p in prompts)


async def test_tous_les_generateurs_sont_declares():
    manquants = [t.generator for t in TOPICS if t.generator not in REGISTRY]
    assert manquants == [], f"generateurs absents du registre : {manquants}"


@pytest.mark.parametrize("level", DEFAULT_SEED_LEVELS)
def test_chaque_notion_produit_des_items(level):
    country = COUNTRIES[0]
    for spec in topics_for_level(level):
        items = REGISTRY[spec.generator](Random(1), level, country)
        assert len(items) >= 4, f"{spec.code} au niveau {level} : {len(items)} items"


def test_items_generes_sont_bien_formes():
    """Chaque item doit etre corrigible : bareme present et coherent."""
    for country in COUNTRIES:
        for level in DEFAULT_SEED_LEVELS:
            for spec in topics_for_level(level):
                for item in REGISTRY[spec.generator](Random(3), level, country):
                    contexte = f"{country.code}/{level}/{spec.code}"
                    assert item["prompt"].strip(), contexte
                    assert 1 <= item["difficulty"] <= 5, contexte
                    assert item["answer"], contexte
                    assert isinstance(item["type"], QuestionType), contexte
                    if item["type"] in (QuestionType.MCQ_SINGLE, QuestionType.MCQ_MULTI):
                        ids = {c["id"] for c in item["choices"]}
                        assert set(item["answer"]["correct"]) <= ids, contexte
                        assert len(ids) == len(item["choices"]), contexte


def test_la_correction_valide_les_reponses_attendues():
    """Boucle de securite : chaque item genere doit se corriger juste."""
    verifies = 0
    for country in COUNTRIES:
        for level in DEFAULT_SEED_LEVELS:
            for spec in topics_for_level(level):
                for item in REGISTRY[spec.generator](Random(5), level, country):
                    if item["type"] not in AUTO_GRADED_TYPES:
                        continue
                    contexte = f"{country.code}/{level}/{spec.code}: {item['prompt'][:60]}"
                    bonne = correct_answer(item["type"].value, item["answer"])
                    assert grade_answer(item["type"], item["answer"], bonne).is_correct, contexte
                    mauvaise = wrong_answer(item["type"].value, item["answer"])
                    assert not grade_answer(item["type"], item["answer"], mauvaise).is_correct, (
                        contexte
                    )
                    verifies += 1
    assert verifies > 1000, f"seulement {verifies} items verifies"


def test_les_explications_sont_presentes():
    manquantes = 0
    total = 0
    for level in DEFAULT_SEED_LEVELS:
        for spec in topics_for_level(level):
            for item in REGISTRY[spec.generator](Random(7), level, COUNTRIES[0]):
                total += 1
                if not item.get("explanation"):
                    manquantes += 1
    assert manquantes / total < 0.02, f"{manquantes}/{total} items sans explication"


def test_les_interfaces_de_saisie_sont_coherentes():
    """Une division posee doit proposer la potence, une fraction son constructeur."""
    for level in (4, 5):
        for spec in topics_for_level(level):
            for item in REGISTRY[spec.generator](Random(11), level, COUNTRIES[0]):
                spec_saisie = item["input_spec"]
                if item["type"] in (
                    QuestionType.MCQ_SINGLE,
                    QuestionType.MCQ_MULTI,
                    QuestionType.TRUE_FALSE,
                ):
                    assert spec_saisie.get("keypad") == "none"
                if "division" in item.get("tags", []) and item["type"] == QuestionType.EXPRESSION:
                    assert spec_saisie.get("widget") == "long_division"
                if item["type"] == QuestionType.HANDWRITTEN:
                    assert spec_saisie.get("allow_handwriting") is True


# ---------------------------------------------------------------------------
# API du catalogue
# ---------------------------------------------------------------------------


async def test_catalogue_expose_les_pays_et_niveaux(api, content):
    countries = (await api.get("/catalog/countries")).json()
    codes = {c["code"] for c in countries}
    assert {"FR", "BJ", "CI", "SN"} <= codes
    france = next(c for c in countries if c["code"] == "FR")
    assert any(g["code"] == "CM1" for g in france["grades"])

    benin = next(c for c in countries if c["code"] == "BJ")
    assert any(g["code"] == "CI" for g in benin["grades"])  # cours d'initiation


async def test_catalogue_notions(api, parent, content):
    topics = await api.get("/catalog/topics?country_code=FR&grade_code=CM1")
    assert topics.status_code == 200
    codes = {t["code"] for t in topics.json()}
    assert "math.fractions" in codes

    filtre = await api.get("/catalog/topics?country_code=FR&grade_code=CM1&subject_code=francais")
    assert all(t["code"].startswith("fr.") for t in filtre.json())


async def test_parent_ajoute_sa_propre_question(api, db, parent, child, content):
    topics = (await api.get("/catalog/topics?country_code=FR&grade_code=CM1")).json()
    topic_id = topics[0]["id"]

    created = await api.post(
        "/catalog/questions",
        {
            "topic_id": topic_id,
            "type": "mcq_single",
            "difficulty": 2,
            "prompt": "Quelle est la capitale du departement etudie ce matin ?",
            "choices": [{"id": "a", "text": "Cotonou"}, {"id": "b", "text": "Lyon"}],
            "answer": {"correct": ["a"], "display": "Cotonou"},
            "explanation": "Vu ensemble pendant la lecon.",
        },
    )
    assert created.status_code == 201, created.text
    question = created.json()
    assert "personnalise" in question["tags"]

    listed = (await api.get(f"/catalog/questions?topic_id={topic_id}")).json()
    assert any(q["id"] == question["id"] for q in listed)

    deleted = await api.delete(f"/catalog/questions/{question['id']}")
    assert deleted.status_code == 204


async def test_couverture_exposee(api, content):
    stats = (await api.get("/catalog/coverage")).json()
    assert stats["total_questions"] > 100
    assert stats["total_subjects"] == 6
