"""Fonctionnement hors ligne et validation parentale des reponses manuscrites."""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import select

from app.core import unlock_protocol as proto
from app.core.clock import now as clock_now
from app.core.clock import time_travel
from app.models.assessment import AssessmentItem
from app.models.content import Question
from app.models.enums import QuestionType
from tests.helpers import answer_key, as_uuid, correct_answer

# ---------------------------------------------------------------------------
# Hors ligne
# ---------------------------------------------------------------------------


async def test_code_valide_hors_ligne_puis_synchronise(api, db, parent, child, device):
    """La tablette valide le code sans reseau, puis rapporte au serveur.

    C'est le scenario "wifi coupe volontairement" : le code doit fonctionner
    hors ligne, et le temps consomme pendant la coupure doit etre decompte a la
    reconnexion. On verifie aussi qu'un code consomme *avant* son expiration
    reste accepte meme si la synchronisation arrive apres.
    """
    code = (
        await api.post("/unlock/parent-code", {"child_id": child["id"], "duration_minutes": 120})
    ).json()
    issued_at = clock_now()

    # --- L'appareil verifie seul, avec le secret recu a l'appairage ---------
    # `now` = horloge de l'appareil : c'est exactement ce que fait l'application
    # React Native, qui embarque la meme implementation du protocole.
    payload = proto.verify_code(
        code=code["code"],
        secret_hex=device["device_secret"],
        device_id=device["device_id"],
        last_counter=device["accepted_counter"],
        now=issued_at.timestamp(),
    )
    assert payload.duration_minutes == 120
    assert payload.kind == proto.UnlockKind.PARENT_DIRECT

    # --- La tablette retrouve le reseau 40 minutes plus tard ---------------
    with time_travel(timedelta(minutes=40)):
        response = await api.post(
            "/unlock/redeem",
            {
                "code": code["code"],
                "consumed_offline_at": issued_at.isoformat(),
                "offline_active_ms": 40 * 60_000,
            },
            as_device=True,
        )
        assert response.status_code == 200, response.text
        session = response.json()

    assert session["granted_minutes"] == 120
    # Les 40 minutes utilisees hors ligne sont bien decomptees.
    assert session["remaining_ms"] <= 80 * 60_000

    sessions = (await api.get(f"/children/{child['id']}/screen-sessions")).json()
    assert sessions[0]["offline_ms"] == 40 * 60_000

    codes = (await api.get(f"/unlock/codes?child_id={child['id']}")).json()
    assert codes[0]["consumed_offline"] is True


async def test_secret_appareil_permet_de_rejouer_toute_la_verification(
    api, db, parent, child, device
):
    """Le secret d'appairage suffit a valider n'importe quel code futur."""
    codes = []
    for minutes in (30, 60, 90):
        response = await api.post(
            "/unlock/parent-code", {"child_id": child["id"], "duration_minutes": minutes}
        )
        codes.append(response.json())

    last_counter = device["accepted_counter"]
    # Seul le dernier code emis reste utilisable une fois consomme.
    payload = proto.verify_code(
        code=codes[-1]["code"],
        secret_hex=device["device_secret"],
        device_id=device["device_id"],
        last_counter=last_counter,
        now=clock_now().timestamp(),
    )
    assert payload.duration_minutes == 90
    with pytest.raises(proto.UnlockProtocolError):
        proto.verify_code(
            code=codes[0]["code"],
            secret_hex=device["device_secret"],
            device_id=device["device_id"],
            last_counter=payload.counter,
            now=clock_now().timestamp(),
        )


async def test_code_revoque_est_refuse_et_signale_a_lappareil(api, parent, child, device):
    code = (
        await api.post("/unlock/parent-code", {"child_id": child["id"], "duration_minutes": 60})
    ).json()
    revoked = await api.post(f"/unlock/codes/{code['id']}/revoke")
    assert revoked.status_code == 200

    refused = await api.post("/unlock/redeem", {"code": code["code"]}, as_device=True)
    assert refused.status_code == 400
    assert "annulé" in refused.json()["error"]["message"]

    # La liste de revocation est transmise a l'appareil pour le mode hors ligne.
    sync = await api.post("/device/sync", {"device_wall_ms": None}, as_device=True)
    assert sync.status_code == 200
    assert len(sync.json()["revoked_code_fingerprints"]) == 1


async def test_synchronisation_signale_une_horloge_manipulee(api, parent, child, device):
    faux = int((clock_now() + timedelta(hours=4)).timestamp() * 1000)
    response = await api.post("/device/sync", {"device_wall_ms": faux}, as_device=True)
    assert response.status_code == 200
    data = response.json()
    assert data["clock_trustworthy"] is False
    assert abs(data["clock_skew_ms"]) > 3_600_000
    assert data["messages"]

    devices = (await api.get("/devices")).json()
    assert devices[0]["tamper_score"] > 0


async def test_synchronisation_transmet_les_regles_et_le_verrou(api, parent, child, device):
    response = await api.post("/device/sync", {}, as_device=True)
    data = response.json()
    assert data["child"]["display_name"] == "Noam"
    assert data["policy"]["pass_score_out_of_20"] == 14.0
    assert data["should_lock"] is True
    assert data["lookahead_window"] >= 8
    assert data["heartbeat_interval_seconds"] > 0


# ---------------------------------------------------------------------------
# Reponses manuscrites et arbitrage parental
# ---------------------------------------------------------------------------


async def _force_handwritten_exam(db, api, child) -> tuple[dict, str]:
    """Compose une epreuve puis transforme un item en question manuscrite."""
    started = await api.post("/assessments", {"kind": "unlock"}, as_device=True)
    exam = started.json()
    items = (
        (
            await db.execute(
                select(AssessmentItem)
                .where(AssessmentItem.assessment_id == as_uuid(exam["id"]))
                .order_by(AssessmentItem.position)
            )
        )
        .scalars()
        .all()
    )
    target = items[0]
    target.question_type = QuestionType.HANDWRITTEN
    question = await db.get(Question, target.question_id)
    question.type = QuestionType.HANDWRITTEN
    question.answer = {"value": 1234, "manual_fallback": True, "display": "1234"}
    await db.commit()
    return exam, str(target.id)


async def test_reponse_manuscrite_illisible_attend_le_parent(api, db, parent, child, device):
    # Seuil eleve : la reponse manuscrite devient decisive pour le verdict.
    await api.put(
        "/policies",
        {"period_type": "school", "child_id": child["id"], "pass_score_pct": 95.0},
    )
    exam, handwritten_id = await _force_handwritten_exam(db, api, child)
    key = await answer_key(db, exam["id"])

    answers = {}
    for item_id, (qtype, spec) in key.items():
        if item_id == handwritten_id:
            answers[item_id] = {
                "answer": {"has_strokes": True},
                "answer_mode": "handwritten",
                "strokes": {"paths": [[[0, 0], [10, 10]]], "width": 400, "height": 200},
            }
        else:
            answers[item_id] = {"answer": correct_answer(qtype, spec)}

    result = (
        await api.post(f"/assessments/{exam['id']}/submit", {"answers": answers}, as_device=True)
    ).json()

    # Le reste de l'epreuve etant juste, le verdict depend de l'ardoise.
    assert result["pending_manual_review"] is True
    assert result["status"] == "needs_review"
    assert result["unlock_code"] is None
    assert result["lockout"] is None  # on ne sanctionne pas tant qu'on n'a pas tranche

    pending = (await api.get("/parent/assessments/pending-review")).json()
    assert len(pending) == 1

    copie = (await api.get(f"/parent/assessments/{exam['id']}")).json()
    manuscrit = next(i for i in copie["items"] if i["id"] == handwritten_id)
    assert manuscrit["needs_manual_review"] is True
    assert manuscrit["strokes"]["paths"]  # le parent voit le trace

    graded = await api.post(
        f"/parent/assessments/{exam['id']}/items/{handwritten_id}/grade",
        {"score": 1.0, "comment": "Operation bien posee."},
    )
    assert graded.status_code == 200
    final = graded.json()
    assert final["passed"] is True
    assert final["unlock_code"] is not None


async def test_score_deja_suffisant_delivre_le_code_sans_attendre(api, db, parent, child, device):
    """Si l'ardoise ne peut plus changer le verdict, l'enfant n'attend pas."""
    await api.put(
        "/policies",
        {"period_type": "school", "child_id": child["id"], "pass_score_pct": 50.0},
    )
    exam, handwritten_id = await _force_handwritten_exam(db, api, child)
    key = await answer_key(db, exam["id"])
    answers = {}
    for item_id, (qtype, spec) in key.items():
        if item_id == handwritten_id:
            answers[item_id] = {
                "answer": {"has_strokes": True},
                "answer_mode": "handwritten",
                "strokes": {"paths": [[[0, 0]]]},
            }
        else:
            answers[item_id] = {"answer": correct_answer(qtype, spec)}

    result = (
        await api.post(f"/assessments/{exam['id']}/submit", {"answers": answers}, as_device=True)
    ).json()
    assert result["pending_manual_review"] is False
    assert result["passed"] is True
    assert result["unlock_code"] is not None


async def test_correction_detaillee_reste_consultable(api, db, parent, child, device):
    from tests.helpers import wrong_answer

    started = await api.post("/assessments", {"kind": "unlock"}, as_device=True)
    exam = started.json()
    key = await answer_key(db, exam["id"])
    answers = {
        item_id: {"answer": wrong_answer(qtype, spec)} for item_id, (qtype, spec) in key.items()
    }
    await api.post(f"/assessments/{exam['id']}/submit", {"answers": answers}, as_device=True)

    review = await api.get(f"/assessments/{exam['id']}/review", as_device=True)
    assert review.status_code == 200
    data = review.json()
    assert len(data["review"]) == len(exam["items"])
    assert all(item["expected"] is not None for item in data["review"])
    # Un code deja delivre ne se reaffiche jamais dans la correction.
    assert data["unlock_code"] is None


async def test_sauvegarde_continue_des_reponses(api, db, parent, child, device):
    started = await api.post("/assessments", {"kind": "unlock"}, as_device=True)
    exam = started.json()
    first = exam["items"][0]

    saved = await api.patch(
        f"/assessments/{exam['id']}/items/{first['id']}",
        {"answer": {"value": "42"}, "answer_mode": "assisted", "time_spent_ms": 12_000},
        as_device=True,
    )
    assert saved.status_code == 204

    resumed = (await api.get("/assessments/current", as_device=True)).json()
    assert resumed["id"] == exam["id"]
    restored = next(i for i in resumed["items"] if i["id"] == first["id"])
    assert restored["answered"] is True
    assert restored["answer"] == {"value": "42"}
