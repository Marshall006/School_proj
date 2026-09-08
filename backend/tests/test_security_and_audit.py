"""Authentification, cloisonnement entre foyers, journal d'audit infalsifiable."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from app.models.audit import AuditEvent
from app.services import audit

# ---------------------------------------------------------------------------
# Authentification
# ---------------------------------------------------------------------------


async def test_inscription_puis_connexion(api):
    email = f"p-{uuid.uuid4().hex[:8]}@example.com"
    created = await api.post(
        "/auth/register",
        {
            "email": email,
            "password": "motdepasse-solide-1",
            "display_name": "Awa",
            "family_name": "Foyer Diop",
            "country_code": "SN",
        },
    )
    assert created.status_code == 201
    assert created.json()["family"]["country_code"] == "SN"

    duplicate = await api.post(
        "/auth/register",
        {
            "email": email,
            "password": "motdepasse-solide-1",
            "display_name": "Awa",
            "family_name": "Autre",
        },
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "email_taken"

    ok = await api.post("/auth/login", {"email": email, "password": "motdepasse-solide-1"})
    assert ok.status_code == 200

    ko = await api.post("/auth/login", {"email": email, "password": "mauvais-mot-de-passe"})
    assert ko.status_code == 401


async def test_mot_de_passe_trop_court_refuse(api):
    response = await api.post(
        "/auth/register",
        {
            "email": "court@example.com",
            "password": "1234",
            "display_name": "X",
            "family_name": "Y",
        },
    )
    assert response.status_code == 422


async def test_rotation_du_jeton_de_rafraichissement(api, parent):
    refresh = parent["tokens"]["refresh_token"]
    first = await api.post("/auth/refresh", {"refresh_token": refresh})
    assert first.status_code == 200

    # Le jeton consomme ne doit plus jamais fonctionner.
    replay = await api.post("/auth/refresh", {"refresh_token": refresh})
    assert replay.status_code == 401
    assert replay.json()["error"]["code"] == "refresh_expired"

    # Le nouveau jeton fonctionne, lui.
    second = await api.post("/auth/refresh", {"refresh_token": first.json()["refresh_token"]})
    assert second.status_code == 200


async def test_deconnexion_revoque_le_jeton(api, parent):
    refresh = parent["tokens"]["refresh_token"]
    assert (await api.post("/auth/logout", {"refresh_token": refresh})).status_code == 204
    assert (await api.post("/auth/refresh", {"refresh_token": refresh})).status_code == 401


async def test_acces_sans_jeton_refuse(api):
    api.parent_token = None
    assert (await api.get("/children")).status_code == 401


async def test_jeton_invalide_refuse(api):
    api.parent_token = "ceci.nest.pas.un.jeton"
    assert (await api.get("/children")).status_code == 401


async def test_jeton_appareil_refuse_sur_les_routes_parent(api, parent, child, device):
    """Un appareil enfant ne doit jamais piloter le tableau de bord."""
    api.parent_token = device["device_token"]
    response = await api.get("/children")
    assert response.status_code == 401


async def test_jeton_parent_refuse_sur_les_routes_appareil(api, parent, child, device):
    api.device_token = parent["tokens"]["access_token"]
    response = await api.get("/assessments/eligibility", as_device=True)
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Cloisonnement entre foyers
# ---------------------------------------------------------------------------


async def test_un_parent_ne_voit_pas_lenfant_dun_autre_foyer(api, client, parent, child, content):
    from tests.conftest import Api

    autre = Api(client)
    inscription = await autre.post(
        "/auth/register",
        {
            "email": f"autre-{uuid.uuid4().hex[:6]}@example.com",
            "password": "motdepasse-solide-2",
            "display_name": "Kossi",
            "family_name": "Foyer Voisin",
        },
    )
    autre.parent_token = inscription.json()["tokens"]["access_token"]

    assert (await autre.get("/children")).json() == []

    interdit = await autre.get(f"/children/{child['id']}")
    assert interdit.status_code == 403
    assert interdit.json()["error"]["code"] == "permission_denied"

    interdit = await autre.get(f"/children/{child['id']}/dashboard")
    assert interdit.status_code == 403

    interdit = await autre.post(
        "/unlock/parent-code", {"child_id": child["id"], "duration_minutes": 60}
    )
    assert interdit.status_code == 403


async def test_un_appareil_ne_touche_pas_a_une_autre_evaluation(
    api, client, db, parent, child, device
):
    started = await api.post("/assessments", {"kind": "unlock"}, as_device=True)
    exam = started.json()

    autre_enfant = (
        await api.post("/children", {"display_name": "Sara", "grade_code": "CM1"})
    ).json()
    pairing = await api.post("/devices/pairing-code", {"child_id": autre_enfant["id"]})
    claim = await api.post(
        "/devices/claim",
        {"pairing_code": pairing.json()["code"], "name": "Tablette 2", "platform": "android"},
    )
    api.device_token = claim.json()["device_token"]

    interdit = await api.get(f"/assessments/{exam['id']}", as_device=True)
    assert interdit.status_code == 403


# ---------------------------------------------------------------------------
# Journal d'audit
# ---------------------------------------------------------------------------


async def test_chaine_daudit_valide(db, api, parent, child, device):
    await api.post("/unlock/parent-code", {"child_id": child["id"], "duration_minutes": 60})
    family_id = uuid.UUID(parent["family"]["id"])

    result = await audit.verify_chain(db, family_id)
    assert result["valid"] is True
    assert result["checked"] >= 4


async def test_modification_dun_evenement_casse_la_chaine(db, api, parent, child):
    family_id = uuid.UUID(parent["family"]["id"])
    assert (await audit.verify_chain(db, family_id))["valid"] is True

    # Un attaquant maquille un evenement directement en base.
    event = (
        (
            await db.execute(
                select(AuditEvent).where(AuditEvent.family_id == family_id).order_by(AuditEvent.seq)
            )
        )
        .scalars()
        .first()
    )
    event.payload = {**(event.payload or {}), "falsifie": True}
    await db.commit()

    result = await audit.verify_chain(db, family_id)
    assert result["valid"] is False
    assert result["reason"] == "contenu modifie"
    assert result["broken_at_seq"] == event.seq


async def test_suppression_dun_evenement_casse_la_chaine(db, api, parent, child):
    family_id = uuid.UUID(parent["family"]["id"])
    events = (
        (
            await db.execute(
                select(AuditEvent).where(AuditEvent.family_id == family_id).order_by(AuditEvent.seq)
            )
        )
        .scalars()
        .all()
    )
    assert len(events) >= 2
    await db.delete(events[0])
    await db.commit()

    result = await audit.verify_chain(db, family_id)
    assert result["valid"] is False
    assert result["reason"] == "chainage rompu"


async def test_chaines_independantes_par_foyer(db, api, client, parent, child):
    from tests.conftest import Api

    autre = Api(client)
    inscription = await autre.post(
        "/auth/register",
        {
            "email": f"iso-{uuid.uuid4().hex[:6]}@example.com",
            "password": "motdepasse-solide-3",
            "display_name": "Ibrahima",
            "family_name": "Foyer Ba",
        },
    )
    autre_family = uuid.UUID(inscription.json()["family"]["id"])
    assert (await audit.verify_chain(db, autre_family))["valid"] is True
    assert (await audit.verify_chain(db, uuid.UUID(parent["family"]["id"])))["valid"] is True


async def test_endpoint_daudit(api, parent, child):
    response = await api.get("/family/audit?verify=true")
    assert response.status_code == 200
    body = response.json()
    assert body["integrity"]["valid"] is True
    assert body["events"] >= 2


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


def test_origines_cors_depuis_lenvironnement(monkeypatch):
    """Une liste en variable d'environnement doit s'ecrire simplement.

    Regression : pydantic-settings tentait un decodage JSON avant la
    validation, et `KODA_CORS_ORIGINS=http://a,http://b` faisait echouer le
    demarrage du serveur — bug decouvert en integration navigateur.
    """
    from app.core.config import Settings

    monkeypatch.setenv("KODA_CORS_ORIGINS", "http://a:3000, http://b:3001 ")
    assert Settings().cors_origins == ["http://a:3000", "http://b:3001"]

    monkeypatch.setenv("KODA_CORS_ORIGINS", '["http://x", "http://y"]')
    assert Settings().cors_origins == ["http://x", "http://y"]

    monkeypatch.delenv("KODA_CORS_ORIGINS")
    assert Settings().cors_origins == ["http://localhost:3000", "http://127.0.0.1:3000"]
