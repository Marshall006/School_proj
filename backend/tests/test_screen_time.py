"""Minuteur : pause ecran, hors ligne, manipulation d'horloge, butoir absolu."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.core.unlock_protocol import generate_device_secret
from app.models.device import Device
from app.models.enums import DevicePlatform, ScreenSessionState
from app.models.family import Child, Family
from app.services import screen_time

T0 = datetime(2026, 3, 15, 14, 0, tzinfo=UTC)
MIN = 60_000


@pytest.fixture
async def scene(db):
    family = Family(name="Foyer", country_code="FR")
    db.add(family)
    await db.flush()
    child = Child(family_id=family.id, display_name="Noam", grade_code="CM1")
    db.add(child)
    await db.flush()
    device = Device(
        child_id=child.id,
        name="Tablette",
        platform=DevicePlatform.ANDROID,
        device_secret=generate_device_secret(),
        boot_id="boot-1",
    )
    db.add(device)
    await db.flush()
    return {"family": family, "child": child, "device": device}


async def open_session(db, scene, minutes: int = 60):
    return await screen_time.start_session(
        db,
        child_id=scene["child"].id,
        device=scene["device"],
        duration_minutes=minutes,
        at=T0,
        boot_id="boot-1",
    )


# --- Comptabilite nominale -------------------------------------------------


async def test_le_temps_se_consomme_ecran_allume(db, scene):
    session = await open_session(db, scene, minutes=60)
    assert session.remaining_ms == 60 * MIN

    result = await screen_time.heartbeat(
        db, session, monotonic_ms=10 * MIN, screen_on=True, at=T0 + timedelta(minutes=10)
    )
    assert result.consumed_delta_ms == 10 * MIN
    assert session.remaining_ms == 50 * MIN
    assert session.state == ScreenSessionState.ACTIVE


async def test_ecran_eteint_le_minuteur_se_fige(db, scene):
    """Exigence produit : le temps ne court pas quand l'ecran est eteint."""
    session = await open_session(db, scene, minutes=60)
    await screen_time.heartbeat(
        db, session, monotonic_ms=5 * MIN, screen_on=True, at=T0 + timedelta(minutes=5)
    )
    assert session.consumed_ms == 5 * MIN

    result = await screen_time.heartbeat(
        db, session, monotonic_ms=25 * MIN, screen_on=False, at=T0 + timedelta(minutes=25)
    )
    assert result.consumed_delta_ms == 0
    assert session.consumed_ms == 5 * MIN
    assert session.state == ScreenSessionState.PAUSED

    await screen_time.heartbeat(
        db, session, monotonic_ms=30 * MIN, screen_on=True, at=T0 + timedelta(minutes=30)
    )
    assert session.state == ScreenSessionState.ACTIVE


async def test_expiration_quand_le_temps_est_epuise(db, scene):
    session = await open_session(db, scene, minutes=30)
    result = await screen_time.heartbeat(
        db, session, monotonic_ms=31 * MIN, screen_on=True, at=T0 + timedelta(minutes=31)
    )
    assert result.should_lock
    assert session.state == ScreenSessionState.EXPIRED
    assert session.remaining_ms == 0
    assert session.end_reason == "time_exhausted"


# --- Anti-triche -----------------------------------------------------------


async def test_impossible_de_consommer_plus_de_temps_quil_nen_passe(db, scene):
    """Une horloge acceleree ne peut pas 'bruler' le temps plus vite que le reel."""
    session = await open_session(db, scene, minutes=60)
    result = await screen_time.heartbeat(
        db, session, monotonic_ms=50 * MIN, screen_on=True, at=T0 + timedelta(minutes=2)
    )
    assert "delta_overflow" in result.anomalies
    assert result.consumed_delta_ms <= 3 * MIN


async def test_horloge_monotone_qui_recule_est_signalee(db, scene):
    session = await open_session(db, scene, minutes=60)
    await screen_time.heartbeat(
        db, session, monotonic_ms=20 * MIN, screen_on=True, at=T0 + timedelta(minutes=20)
    )
    result = await screen_time.heartbeat(
        db, session, monotonic_ms=5 * MIN, screen_on=True, at=T0 + timedelta(minutes=25)
    )
    assert "monotonic_rollback" in result.anomalies
    assert session.anomaly_count >= 1
    assert session.integrity_score < 1.0
    # Le temps ecoule cote serveur est tout de meme impute.
    assert session.consumed_ms >= 20 * MIN


async def test_horloge_murale_decalee_est_detectee(db, scene):
    session = await open_session(db, scene, minutes=60)
    faux_temps = int((T0 + timedelta(minutes=10, hours=3)).timestamp() * 1000)
    result = await screen_time.heartbeat(
        db,
        session,
        monotonic_ms=10 * MIN,
        device_wall_ms=faux_temps,
        screen_on=True,
        at=T0 + timedelta(minutes=10),
    )
    assert "clock_skew" in result.anomalies
    assert session.anomaly_count >= 1
    # Le decompte reste juste : il s'appuie sur l'horloge monotone.
    assert session.consumed_ms == 10 * MIN


async def test_redemarrage_detecte(db, scene):
    session = await open_session(db, scene, minutes=60)
    await screen_time.heartbeat(
        db, session, monotonic_ms=10 * MIN, screen_on=True, at=T0 + timedelta(minutes=10)
    )
    result = await screen_time.heartbeat(
        db,
        session,
        monotonic_ms=0,
        screen_on=True,
        boot_id="boot-2",
        at=T0 + timedelta(minutes=20),
    )
    assert "reboot_detected" in result.anomalies
    assert session.device_boot_id == "boot-2"


async def test_butoir_absolu_contre_les_pauses_a_repetition(db, scene):
    """Enchainer les pauses ne permet pas d'etaler 1 h sur trois jours."""
    session = await open_session(db, scene, minutes=60)
    assert session.wall_deadline_at == T0 + timedelta(minutes=180)  # 60 x 3

    result = await screen_time.heartbeat(
        db, session, monotonic_ms=MIN, screen_on=True, at=T0 + timedelta(minutes=200)
    )
    assert "wall_deadline" in result.anomalies
    assert session.state == ScreenSessionState.EXPIRED
    assert result.should_lock


# --- Hors ligne ------------------------------------------------------------


async def test_reconciliation_hors_ligne(db, scene):
    session = await open_session(db, scene, minutes=60)
    await screen_time.reconcile_offline(
        db, session, reported_active_ms=25 * MIN, at=T0 + timedelta(minutes=40)
    )
    assert session.consumed_ms == 25 * MIN
    assert session.offline_ms == 25 * MIN


async def test_sur_declaration_hors_ligne_bornee_par_le_serveur(db, scene):
    session = await open_session(db, scene, minutes=60)
    await screen_time.reconcile_offline(
        db, session, reported_active_ms=50 * MIN, at=T0 + timedelta(minutes=10)
    )
    assert session.consumed_ms <= 10 * MIN
    assert session.anomaly_count >= 1


# --- Actions ---------------------------------------------------------------


async def test_pause_et_reprise_explicites(db, scene):
    session = await open_session(db, scene, minutes=60)
    await screen_time.pause_session(db, session, at=T0 + timedelta(minutes=5))
    assert session.state == ScreenSessionState.PAUSED
    await screen_time.resume_session(
        db, session, monotonic_ms=5 * MIN, at=T0 + timedelta(minutes=30)
    )
    assert session.state == ScreenSessionState.ACTIVE
    # Le temps de pause n'est pas facture.
    await screen_time.heartbeat(
        db, session, monotonic_ms=10 * MIN, screen_on=True, at=T0 + timedelta(minutes=35)
    )
    assert session.consumed_ms == 5 * MIN


async def test_reprise_apres_le_butoir_expire_la_session(db, scene):
    session = await open_session(db, scene, minutes=30)
    await screen_time.pause_session(db, session, at=T0 + timedelta(minutes=5))
    await screen_time.resume_session(db, session, at=T0 + timedelta(hours=5))
    assert session.state == ScreenSessionState.EXPIRED


async def test_rallonge_parentale(db, scene):
    session = await open_session(db, scene, minutes=30)
    limite = session.wall_deadline_at
    await screen_time.extend_session(db, session, minutes=15, at=T0 + timedelta(minutes=10))
    assert session.total_ms == 45 * MIN
    assert session.wall_deadline_at > limite


async def test_rallonge_impossible_sur_session_fermee(db, scene):
    from app.core.errors import ConflictError

    session = await open_session(db, scene, minutes=30)
    await screen_time.end_session(db, session, at=T0 + timedelta(minutes=5))
    with pytest.raises(ConflictError):
        await screen_time.extend_session(db, session, minutes=15)


async def test_nouvelle_session_ferme_la_precedente(db, scene):
    first = await open_session(db, scene, minutes=30)
    second = await screen_time.start_session(
        db,
        child_id=scene["child"].id,
        device=scene["device"],
        duration_minutes=60,
        at=T0 + timedelta(minutes=10),
    )
    assert first.state == ScreenSessionState.ENDED
    assert first.end_reason == "superseded"
    assert second.state == ScreenSessionState.ACTIVE


async def test_battement_sur_session_fermee_demande_le_verrouillage(db, scene):
    session = await open_session(db, scene, minutes=30)
    await screen_time.end_session(db, session, at=T0 + timedelta(minutes=5))
    result = await screen_time.heartbeat(
        db, session, monotonic_ms=6 * MIN, at=T0 + timedelta(minutes=6)
    )
    assert result.should_lock
    assert "session_closed" in result.anomalies


# --- Quotas ----------------------------------------------------------------


async def test_minutes_accordees_du_jour(db, scene):
    await open_session(db, scene, minutes=60)
    await screen_time.start_session(
        db,
        child_id=scene["child"].id,
        device=scene["device"],
        duration_minutes=45,
        at=T0 + timedelta(hours=2),
    )
    total = await screen_time.minutes_granted_today(
        db, scene["child"].id, at=T0 + timedelta(hours=3)
    )
    assert total == 105


async def test_purge_des_sessions_perimees(db, scene):
    await open_session(db, scene, minutes=30)
    count = await screen_time.expire_stale_sessions(db, at=T0 + timedelta(hours=6))
    assert count == 1


async def test_session_perimee_nest_jamais_presentee_comme_active(db, scene):
    """Sans battement de coeur, c'est le butoir absolu qui ferme la session.

    Une tablette qu'on eteint et qu'on ne rallume pas ne doit pas apparaitre
    indefiniment comme "ouverte" dans le tableau de bord parental.
    """
    session = await open_session(db, scene, minutes=60)
    assert session.state == ScreenSessionState.ACTIVE

    # Juste avant le butoir : toujours vivante.
    still = await screen_time.active_session_for_device(
        db, scene["device"].id, at=T0 + timedelta(minutes=170)
    )
    assert still is not None

    # Apres le butoir : fermee au passage, sans intervention exterieure.
    gone = await screen_time.active_session_for_device(
        db, scene["device"].id, at=T0 + timedelta(minutes=200)
    )
    assert gone is None
    assert session.state == ScreenSessionState.EXPIRED
    assert session.end_reason == "wall_deadline"


async def test_meme_regle_cote_tableau_de_bord(db, scene):
    session = await open_session(db, scene, minutes=30)
    assert (
        await screen_time.active_session_for_child(
            db, scene["child"].id, at=T0 + timedelta(minutes=10)
        )
        is not None
    )
    assert (
        await screen_time.active_session_for_child(
            db, scene["child"].id, at=T0 + timedelta(hours=5)
        )
        is None
    )
    assert session.state == ScreenSessionState.EXPIRED
