"""Le jeu de demonstration et les commandes d'administration.

`make demo` est le premier geste de quiconque decouvre le projet : s'il casse,
la demonstration ne demarre pas. Ces tests le verrouillent, et verifient au
passage que l'historique produit est coherent (des evaluations, des sessions
fermees, des XP, un niveau estime).
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select

from app.content.demo import DEMO_EMAIL, DEMO_PASSWORD, seed_demo
from app.content.seed import seed_all
from app.core.security import verify_password
from app.models.access import ScreenSession, UnlockCode
from app.models.assessment import Assessment
from app.models.enums import ScreenSessionState
from app.models.family import Child, Parent
from app.models.progress import Mastery, XPLedgerEntry
from app.services import analytics, audit, screen_time, unlock
from app.services import assessment as assessment_svc
from app.services.policy import resolve_policy


async def test_le_foyer_de_demonstration_est_utilisable(db):
    await seed_all(db, countries=("FR",), levels=(4, 5))
    report = await seed_demo(db, days=6)

    assert report["created"] is True
    assert report["assessments"] > 0
    assert report["sessions"] > 0
    assert report["skipped"] == {}

    parent = (await db.execute(select(Parent).where(Parent.email == DEMO_EMAIL))).scalar_one()
    assert verify_password(DEMO_PASSWORD, parent.password_hash or "")

    children = list(
        (await db.execute(select(Child).where(Child.family_id == parent.family_id))).scalars()
    )
    assert {c.display_name for c in children} == {"Noam", "Aya"}
    assert all(child.xp_balance > 0 for child in children)


async def test_lhistorique_simule_est_coherent(db):
    await seed_all(db, countries=("FR",), levels=(4, 5))
    await seed_demo(db, days=8)
    parent = (await db.execute(select(Parent).where(Parent.email == DEMO_EMAIL))).scalar_one()
    child = (
        (await db.execute(select(Child).where(Child.family_id == parent.family_id)))
        .scalars()
        .first()
    )

    graded = await db.scalar(
        select(func.count(Assessment.id)).where(
            Assessment.child_id == child.id, Assessment.passed.is_not(None)
        )
    )
    assert graded > 0

    mastery = await db.scalar(select(func.count(Mastery.id)).where(Mastery.child_id == child.id))
    assert mastery > 0, "le niveau par notion doit etre estime"

    ledger = await db.scalar(
        select(func.count(XPLedgerEntry.id)).where(XPLedgerEntry.child_id == child.id)
    )
    assert ledger > 0

    # Les sessions passees sont refermees : aucune tablette ne reste "ouverte"
    # depuis la semaine derniere dans le tableau de bord.
    stale = await db.scalar(
        select(func.count(ScreenSession.id)).where(
            ScreenSession.child_id == child.id,
            ScreenSession.state == ScreenSessionState.ACTIVE,
        )
    )
    assert stale <= 1

    codes = await db.scalar(
        select(func.count(UnlockCode.id)).where(UnlockCode.child_id == child.id)
    )
    assert codes > 0


async def test_le_tableau_de_bord_se_construit_sur_ces_donnees(db):
    await seed_all(db, countries=("FR",), levels=(4, 5))
    await seed_demo(db, days=8)
    parent = (await db.execute(select(Parent).where(Parent.email == DEMO_EMAIL))).scalar_one()
    child = (
        (await db.execute(select(Child).where(Child.family_id == parent.family_id)))
        .scalars()
        .first()
    )

    policy = await resolve_policy(db, child)
    dashboard = await analytics.build_dashboard(db, child, policy)

    assert dashboard["totals"]["assessments_graded"] > 0
    assert dashboard["subjects"], "le detail par matiere doit etre renseigne"
    assert dashboard["mastery"]["topics_tracked"] > 0
    assert len(dashboard["screen_time_trend"]) == 14
    assert dashboard["recent_assessments"]

    integrity = await audit.verify_chain(db, parent.family_id)
    assert integrity["valid"] is True


async def test_seed_demo_est_idempotent(db):
    await seed_all(db, countries=("FR",), levels=(4,))
    first = await seed_demo(db, days=3)
    second = await seed_demo(db, days=3)
    assert first["created"] is True
    assert second["created"] is False
    assert second["email"] == DEMO_EMAIL


async def test_taches_de_maintenance(db):
    """`python -m app.cli housekeeping` ne doit jamais echouer sur une base vide."""
    assert await unlock.expire_stale_codes(db) == 0
    assert await screen_time.expire_stale_sessions(db) == 0
    assert await assessment_svc.expire_stale_assessments(db) == 0


def test_la_ligne_de_commande_expose_les_commandes_attendues():
    from app.cli import COMMANDS, build_parser

    assert set(COMMANDS) == {"seed", "demo", "stats", "housekeeping", "verify-audit"}
    parser = build_parser()
    assert parser.parse_args(["demo", "--days", "5"]).days == 5
    assert parser.parse_args(["seed", "--countries", "FR,BJ"]).countries == "FR,BJ"
    identifier = str(uuid.uuid4())
    assert parser.parse_args(["verify-audit", "--family", identifier]).family == identifier
