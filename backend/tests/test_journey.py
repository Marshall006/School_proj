"""Parcours complet, de bout en bout, tel que le vit une famille.

Ce test suit le scenario du cahier des charges :

- periode scolaire : les devoirs sont faits, le parent debloque directement ;
- vacances : le deverrouillage direct est coupe, l'evaluation devient le chemin ;
- echec : pas de code, correction detaillee et temps de carence ;
- le parent peut lever la carence ;
- reussite : code delivre automatiquement, temps d'ecran ouvert ;
- effort volontaire : les XP se convertissent en minutes supplementaires.
"""

from __future__ import annotations

from datetime import timedelta

from app.core.clock import now as clock_now
from tests.helpers import answer_key, correct_answer, wrong_answer

MIN = 60_000


async def test_parcours_complet(api, db, parent, child, device):
    child_id = child["id"]

    # === 1. Periode scolaire : deverrouillage parental direct ==============
    policy = (await api.get(f"/children/{child_id}/policy")).json()
    assert policy["period_type"] in ("school", "weekend")
    assert policy["allow_parent_direct_unlock"] is True
    assert policy["pass_score_out_of_20"] == 14.0

    response = await api.post(
        "/unlock/parent-code",
        {"child_id": child_id, "duration_minutes": 180, "note": "Devoirs faits"},
    )
    assert response.status_code == 201, response.text
    code = response.json()
    assert len(code["code"]) == 10
    assert code["duration_minutes"] == 180

    # L'appareil consomme le code.
    redeem = await api.post("/unlock/redeem", {"code": code["formatted"]}, as_device=True)
    assert redeem.status_code == 200, redeem.text
    session = redeem.json()
    assert session["granted_minutes"] == 180

    # Le meme code ne fonctionne pas deux fois.
    again = await api.post("/unlock/redeem", {"code": code["code"]}, as_device=True)
    assert again.status_code == 400
    assert again.json()["error"]["code"] == "invalid_unlock_code"

    # Le minuteur consomme du temps.
    heartbeat = await api.post(
        f"/screen/sessions/{session['session_id']}/heartbeat",
        {"monotonic_ms": 0, "screen_on": True},
        as_device=True,
    )
    assert heartbeat.status_code == 200
    assert heartbeat.json()["state"] == "active"

    stop = await api.post(f"/screen/sessions/{session['session_id']}/stop")
    assert stop.status_code == 200

    # === 2. Bascule en vacances ===========================================
    today = clock_now().date()
    calendar = await api.post(
        "/calendar",
        {
            "label": "Vacances de printemps",
            "period_type": "holiday",
            "start_date": (today - timedelta(days=2)).isoformat(),
            "end_date": (today + timedelta(days=12)).isoformat(),
        },
    )
    assert calendar.status_code == 201, calendar.text

    policy = (await api.get(f"/children/{child_id}/policy")).json()
    assert policy["period_type"] == "holiday"
    assert policy["allow_parent_direct_unlock"] is False

    refused = await api.post("/unlock/parent-code", {"child_id": child_id, "duration_minutes": 60})
    assert refused.status_code == 403
    assert refused.json()["error"]["code"] == "policy_forbids"

    # === 3. L'enfant echoue a l'evaluation ================================
    eligibility = (await api.get("/assessments/eligibility", as_device=True)).json()
    assert eligibility["allowed"] is True

    started = await api.post("/assessments", {"kind": "unlock"}, as_device=True)
    assert started.status_code == 201, started.text
    exam = started.json()
    assert len(exam["items"]) == policy["question_count"]
    assert sum(exam["blueprint_distribution"].values()) == len(exam["items"])
    # Le corrige n'est jamais transmis a l'enfant.
    assert all("answer" not in str(item.get("input_spec", {})) for item in exam["items"])

    key = await answer_key(db, exam["id"])
    answers = {
        item_id: {"answer": wrong_answer(qtype, spec), "answer_mode": "assisted"}
        for item_id, (qtype, spec) in key.items()
    }
    submitted = await api.post(
        f"/assessments/{exam['id']}/submit", {"answers": answers}, as_device=True
    )
    assert submitted.status_code == 200, submitted.text
    result = submitted.json()

    assert result["passed"] is False
    assert result["unlock_code"] is None
    assert result["score_out_of_20"] < 14.0
    # La correction detaillee est bien remise malgre l'echec.
    assert len(result["review"]) == len(exam["items"])
    assert all(item["expected"] is not None for item in result["review"])
    assert result["lockout"]["remaining_minutes"] > 0
    assert result["weak_topics"]

    # === 4. Le temps de carence bloque la nouvelle tentative ==============
    blocked = await api.post("/assessments", {"kind": "unlock"}, as_device=True)
    assert blocked.status_code == 423
    assert blocked.json()["error"]["code"] == "cooldown_active"

    lockout = (await api.get(f"/children/{child_id}/lockout")).json()
    assert lockout["reason"] == "failed_assessment"
    assert lockout["review_topics"]

    # === 5. Le parent leve la carence apres revision ======================
    released = await api.post(f"/children/{child_id}/lockout/release")
    assert released.json()["released"] is True
    assert (await api.get(f"/children/{child_id}/lockout")).json() is None

    # === 6. L'enfant reussit ==============================================
    started = await api.post("/assessments", {"kind": "unlock"}, as_device=True)
    assert started.status_code == 201, started.text
    exam = started.json()
    key = await answer_key(db, exam["id"])
    answers = {
        item_id: {
            "answer": correct_answer(qtype, spec),
            "answer_mode": "assisted",
            "time_spent_ms": 30_000,
        }
        for item_id, (qtype, spec) in key.items()
    }
    result = (
        await api.post(f"/assessments/{exam['id']}/submit", {"answers": answers}, as_device=True)
    ).json()

    assert result["passed"] is True, result
    assert result["score_out_of_20"] >= 14.0
    assert result["unlock_code"] is not None
    assert result["xp_earned"] > 0
    reward_code = result["unlock_code"]

    redeem = await api.post("/unlock/redeem", {"code": reward_code["code"]}, as_device=True)
    assert redeem.status_code == 200, redeem.text
    assert redeem.json()["granted_minutes"] == reward_code["duration_minutes"]

    # === 7. Conversion volontaire des XP en minutes =======================
    child_row = (await api.get(f"/children/{child_id}")).json()
    assert child_row["xp_balance"] > 0

    quote = await api.post("/unlock/xp/quote", {"child_id": child_id})
    assert quote.status_code == 200, quote.text

    # === 8. Le tableau de bord parental reflete tout cela =================
    dashboard = (await api.get(f"/children/{child_id}/dashboard")).json()
    assert dashboard["status"]["screen_state"] in ("unlocked", "paused")
    assert dashboard["totals"]["assessments_graded"] == 2
    assert dashboard["totals"]["assessments_passed"] == 1
    assert dashboard["subjects"], "le detail par matiere doit etre renseigne"
    assert dashboard["mastery"]["topics_tracked"] > 0
    assert dashboard["recent_assessments"]

    # === 9. Le journal d'audit est intact =================================
    audit = (await api.get("/family/audit?verify=true")).json()
    assert audit["integrity"]["valid"] is True
    assert audit["events"] > 5


async def test_le_plafond_quotidien_rogne_la_duree(api, db, parent, child, device):
    """Un code de 3 h delivre alors qu'il ne reste que 45 min n'en accorde que 45."""
    await api.put(
        "/policies",
        {"period_type": "school", "child_id": child["id"], "daily_cap_minutes": 45},
    )
    code = (
        await api.post("/unlock/parent-code", {"child_id": child["id"], "duration_minutes": 180})
    ).json()
    redeem = (await api.post("/unlock/redeem", {"code": code["code"]}, as_device=True)).json()
    assert redeem["granted_minutes"] == 45
    assert redeem["truncated_by_cap"] is True

    # Une fois le plafond atteint, plus rien ne passe.
    code2 = (
        await api.post("/unlock/parent-code", {"child_id": child["id"], "duration_minutes": 30})
    ).json()
    refused = await api.post("/unlock/redeem", {"code": code2["code"]}, as_device=True)
    assert refused.status_code == 423
    assert refused.json()["error"]["code"] == "daily_cap_reached"


async def test_limite_de_tentatives_quotidiennes(api, db, parent, child, device):
    await api.put(
        "/policies",
        {
            "period_type": "school",
            "child_id": child["id"],
            "max_attempts_per_day": 2,
            "cooldown_minutes": 0,
        },
    )
    for _ in range(2):
        started = await api.post("/assessments", {"kind": "unlock"}, as_device=True)
        assert started.status_code == 201
        exam = started.json()
        key = await answer_key(db, exam["id"])
        answers = {
            item_id: {"answer": wrong_answer(qtype, spec)} for item_id, (qtype, spec) in key.items()
        }
        await api.post(f"/assessments/{exam['id']}/submit", {"answers": answers}, as_device=True)
        await api.post(f"/children/{child['id']}/lockout/release")

    third = await api.post("/assessments", {"kind": "unlock"}, as_device=True)
    assert third.status_code == 409
    assert third.json()["error"]["code"] == "too_many_attempts"


async def test_evaluation_libre_ne_delivre_pas_de_code_mais_donne_des_xp(
    api, db, parent, child, device
):
    """L'auto-evaluation volontaire rapporte des XP, jamais un acces direct."""
    started = await api.post("/assessments", {"kind": "practice"}, as_device=True)
    assert started.status_code == 201
    exam = started.json()
    key = await answer_key(db, exam["id"])
    answers = {
        item_id: {"answer": correct_answer(qtype, spec)} for item_id, (qtype, spec) in key.items()
    }
    result = (
        await api.post(f"/assessments/{exam['id']}/submit", {"answers": answers}, as_device=True)
    ).json()
    assert result["passed"] is True
    assert result["unlock_code"] is None
    assert result["xp_earned"] > 0


async def test_appareil_revoque_perd_tout_acces(api, parent, child, device):
    devices = (await api.get("/devices")).json()
    revoke = await api.post(f"/devices/{devices[0]['id']}/revoke")
    assert revoke.status_code == 200
    refused = await api.get("/assessments/eligibility", as_device=True)
    assert refused.status_code == 403
    assert refused.json()["error"]["code"] == "device_revoked"


async def test_saisie_bloquee_apres_des_codes_errones(api, parent, child, device):
    for _ in range(5):
        response = await api.post("/unlock/redeem", {"code": "0000000000"}, as_device=True)
        assert response.status_code == 400
    blocked = await api.post("/unlock/redeem", {"code": "0000000000"}, as_device=True)
    assert blocked.status_code == 423
    assert blocked.json()["error"]["code"] == "device_locked"

    # Le parent peut debloquer la saisie.
    devices = (await api.get("/devices")).json()
    reset = await api.post(f"/devices/{devices[0]['id']}/unlock-attempts/reset")
    assert reset.status_code == 200
    assert reset.json()["failed_code_attempts"] == 0


async def test_un_second_code_ajoute_du_temps_sans_effacer_le_restant(
    api, db, parent, child, device
):
    """Convertir ses XP (ou recevoir une rallonge) pendant une session ajoute du temps.

    Regression : la consommation ouvrait une session neuve, ce qui faisait
    perdre le temps deja acquis — l'inverse de ce qu'on promet a l'enfant.
    """
    first = (
        await api.post("/unlock/parent-code", {"child_id": child["id"], "duration_minutes": 60})
    ).json()
    opened = (await api.post("/unlock/redeem", {"code": first["code"]}, as_device=True)).json()
    assert opened["granted_minutes"] == 60

    second = (
        await api.post("/unlock/parent-code", {"child_id": child["id"], "duration_minutes": 30})
    ).json()
    extended = (await api.post("/unlock/redeem", {"code": second["code"]}, as_device=True)).json()

    assert extended["session_id"] == opened["session_id"], "la session doit etre la meme"
    assert extended["granted_ms"] == 90 * 60_000, "les durees s'additionnent"
    assert "temps_ajoute_a_la_session_en_cours" in extended["warnings"]


async def test_la_carence_indique_la_copie_a_revoir(api, db, parent, child, device):
    """Pendant le temps de revision, l'enfant doit pouvoir relire sa correction."""
    from tests.helpers import wrong_answer

    started = await api.post("/assessments", {"kind": "unlock"}, as_device=True)
    exam = started.json()
    key = await answer_key(db, exam["id"])
    answers = {
        item_id: {"answer": wrong_answer(qtype, spec)} for item_id, (qtype, spec) in key.items()
    }
    result = (
        await api.post(f"/assessments/{exam['id']}/submit", {"answers": answers}, as_device=True)
    ).json()

    assert result["lockout"]["source_assessment_id"] == exam["id"]

    lockout = (await api.get(f"/children/{child['id']}/lockout")).json()
    assert lockout["source_assessment_id"] == exam["id"]

    review = await api.get(f"/assessments/{exam['id']}/review", as_device=True)
    assert review.status_code == 200
    assert len(review.json()["review"]) == len(exam["items"])
