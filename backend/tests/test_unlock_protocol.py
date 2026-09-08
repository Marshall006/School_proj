"""Protocole KODA-UNLOCK : emission, verification hors ligne, anti-rejeu."""

from __future__ import annotations

import time

import pytest

from app.core.unlock_protocol import (
    BUCKET_SECONDS,
    CODE_DIGITS,
    UnlockKind,
    UnlockProtocolError,
    code_fingerprint,
    format_code,
    generate_device_secret,
    issue_code,
    lockout_seconds_for,
    minutes_to_units,
    peek_code,
    verify_code,
)

SECRET = generate_device_secret()
DEVICE = "11111111-2222-3333-4444-555555555555"


def test_code_shape():
    code = issue_code(secret_hex=SECRET, device_id=DEVICE, counter=1, duration_minutes=180)
    assert len(code) == CODE_DIGITS
    assert code.isdigit()
    assert format_code(code) == f"{code[:3]} {code[3:6]} {code[6:]}"


def test_roundtrip_carries_duration_and_kind():
    code = issue_code(
        secret_hex=SECRET,
        device_id=DEVICE,
        counter=5,
        duration_minutes=90,
        kind=UnlockKind.ASSESSMENT_REWARD,
    )
    payload = verify_code(code=code, secret_hex=SECRET, device_id=DEVICE, last_counter=4)
    assert payload.duration_minutes == 90
    assert payload.kind == UnlockKind.ASSESSMENT_REWARD
    assert payload.counter == 5


def test_duration_readable_before_verification():
    code = issue_code(
        secret_hex=SECRET,
        device_id=DEVICE,
        counter=1,
        duration_minutes=45,
        kind=UnlockKind.XP_REDEEM,
    )
    kind, minutes = peek_code(code)
    assert (kind, minutes) == (UnlockKind.XP_REDEEM, 45)


def test_human_separators_are_tolerated():
    code = issue_code(secret_hex=SECRET, device_id=DEVICE, counter=1, duration_minutes=60)
    for variant in (format_code(code), f"{code[:3]}-{code[3:6]}-{code[6:]}", f" {code} "):
        assert (
            verify_code(code=variant, secret_hex=SECRET, device_id=DEVICE, last_counter=0).counter
            == 1
        )


def test_replay_is_rejected():
    code = issue_code(secret_hex=SECRET, device_id=DEVICE, counter=7, duration_minutes=60)
    payload = verify_code(code=code, secret_hex=SECRET, device_id=DEVICE, last_counter=6)
    with pytest.raises(UnlockProtocolError):
        verify_code(code=code, secret_hex=SECRET, device_id=DEVICE, last_counter=payload.counter)


def test_newer_code_kills_older_ones():
    """Consommer le code n+1 invalide definitivement le code n."""
    old = issue_code(secret_hex=SECRET, device_id=DEVICE, counter=10, duration_minutes=30)
    new = issue_code(secret_hex=SECRET, device_id=DEVICE, counter=11, duration_minutes=30)
    accepted = verify_code(code=new, secret_hex=SECRET, device_id=DEVICE, last_counter=9)
    assert accepted.counter == 11
    with pytest.raises(UnlockProtocolError):
        verify_code(code=old, secret_hex=SECRET, device_id=DEVICE, last_counter=11)


def test_lookahead_window_bounds():
    code = issue_code(secret_hex=SECRET, device_id=DEVICE, counter=30, duration_minutes=30)
    assert (
        verify_code(
            code=code, secret_hex=SECRET, device_id=DEVICE, last_counter=20, lookahead=16
        ).counter
        == 30
    )
    with pytest.raises(UnlockProtocolError):
        verify_code(code=code, secret_hex=SECRET, device_id=DEVICE, last_counter=5, lookahead=16)


def test_other_device_secret_is_rejected():
    code = issue_code(secret_hex=SECRET, device_id=DEVICE, counter=1, duration_minutes=60)
    with pytest.raises(UnlockProtocolError):
        verify_code(
            code=code, secret_hex=generate_device_secret(), device_id=DEVICE, last_counter=0
        )


def test_other_device_id_is_rejected():
    code = issue_code(secret_hex=SECRET, device_id=DEVICE, counter=1, duration_minutes=60)
    with pytest.raises(UnlockProtocolError):
        verify_code(code=code, secret_hex=SECRET, device_id="autre-appareil", last_counter=0)


def test_expiry_even_offline():
    """Passe la fenetre temporelle, le code cesse de fonctionner sans reseau."""
    now = time.time()
    code = issue_code(secret_hex=SECRET, device_id=DEVICE, counter=1, duration_minutes=60, now=now)
    horizon = now + BUCKET_SECONDS[UnlockKind.PARENT_DIRECT] * 3
    with pytest.raises(UnlockProtocolError):
        verify_code(code=code, secret_hex=SECRET, device_id=DEVICE, last_counter=0, now=horizon)


def test_tolerance_across_bucket_boundary():
    now = time.time()
    code = issue_code(secret_hex=SECRET, device_id=DEVICE, counter=1, duration_minutes=60, now=now)
    later = now + BUCKET_SECONDS[UnlockKind.PARENT_DIRECT] - 1
    assert (
        verify_code(
            code=code, secret_hex=SECRET, device_id=DEVICE, last_counter=0, now=later
        ).counter
        == 1
    )


def test_emergency_codes_live_longer():
    now = time.time()
    code = issue_code(
        secret_hex=SECRET,
        device_id=DEVICE,
        counter=1,
        duration_minutes=60,
        kind=UnlockKind.EMERGENCY,
        now=now,
    )
    assert (
        verify_code(
            code=code, secret_hex=SECRET, device_id=DEVICE, last_counter=0, now=now + 6 * 3600
        ).kind
        == UnlockKind.EMERGENCY
    )


def test_altered_digit_is_rejected():
    code = issue_code(secret_hex=SECRET, device_id=DEVICE, counter=1, duration_minutes=60)
    for index in range(3, CODE_DIGITS):
        broken = list(code)
        broken[index] = str((int(broken[index]) + 1) % 10)
        with pytest.raises(UnlockProtocolError):
            verify_code(code="".join(broken), secret_hex=SECRET, device_id=DEVICE, last_counter=0)


def test_forged_duration_is_rejected():
    """Rallonger la duree en modifiant les deux premiers chiffres invalide la signature."""
    code = issue_code(secret_hex=SECRET, device_id=DEVICE, counter=1, duration_minutes=30)
    forged = "99" + code[2:]
    with pytest.raises(UnlockProtocolError):
        verify_code(code=forged, secret_hex=SECRET, device_id=DEVICE, last_counter=0)


def test_duration_constraints():
    assert minutes_to_units(180) == 36
    with pytest.raises(UnlockProtocolError):
        minutes_to_units(7)  # pas un multiple de 5
    with pytest.raises(UnlockProtocolError):
        minutes_to_units(0)
    with pytest.raises(UnlockProtocolError):
        minutes_to_units(600)  # au-dela de 495 minutes


def test_malformed_codes():
    for bad in ("", "12345", "abcdefghij", "1" * 20):
        with pytest.raises(UnlockProtocolError):
            peek_code(bad)


def test_fingerprint_is_stable_and_scoped():
    code = issue_code(secret_hex=SECRET, device_id=DEVICE, counter=1, duration_minutes=60)
    assert code_fingerprint(code, DEVICE) == code_fingerprint(format_code(code), DEVICE)
    assert code_fingerprint(code, DEVICE) != code_fingerprint(code, "autre")


def test_progressive_lockout():
    assert lockout_seconds_for(1) == 0
    assert lockout_seconds_for(5) == 300
    assert lockout_seconds_for(10) == 1800
    assert lockout_seconds_for(20) == 86400


def test_brute_force_resistance():
    """Force brute : la probabilite de tomber juste doit rester infime.

    Espace des etiquettes : 10^7. Combinaisons acceptees simultanement :
    16 compteurs x 3 tranches temporelles = 48, soit p ~ 4,8e-6 par essai.
    Sur 20 000 essais on attend donc moins d'une reussite en moyenne ; couple au
    verrouillage progressif de la saisie, l'attaque n'est pas praticable.
    Le secret et la graine sont figes pour que le test soit reproductible.
    """
    import random

    fixed_secret = "9f" * 32
    rng = random.Random(20240915)
    attempts = 20_000
    hits = 0
    for _ in range(attempts):
        candidate = f"{rng.randrange(1, 100):02d}{rng.randrange(5)}{rng.randrange(10**7):07d}"
        try:
            verify_code(code=candidate, secret_hex=fixed_secret, device_id=DEVICE, last_counter=0)
            hits += 1
        except UnlockProtocolError:
            pass
    assert hits == 0, f"{hits} collisions sur {attempts} essais : etiquette trop courte"
