"""Protocole KODA-UNLOCK v1 - codes de deverrouillage verifiables hors ligne.

Probleme resolu
---------------
La tablette de l'enfant est souvent hors ligne (avion, wifi coupe volontairement
pour "tricher"...). Le code saisi doit donc etre validable **sans reseau**, tout
en restant infalsifiable et non rejouable.

Solution : un OTP de type HOTP+TOTP hybride, signe par un secret d'appareil
partage une seule fois lors de l'appairage.

Format du code (10 chiffres, affiche en 3 groupes : `XXX XXX XXXX`)
-------------------------------------------------------------------
    d0 d1   -> duree accordee, en tranches de 5 minutes (00..99 => 0..495 min)
    d2      -> nature du code (voir UnlockKind)
    d3..d9  -> troncature decimale sur 7 chiffres de HMAC-SHA256

Entree signee :
    b"KODA1|<device_id>|<counter>|<duration_units>|<kind>|<time_bucket>"

Anti-rejeu (compteur facon HOTP)
--------------------------------
Le serveur incremente `counter` a chaque emission. L'appareil essaie les
compteurs `[last_accepted+1 .. last_accepted+W]`. Des qu'un code est accepte,
le compteur local saute a cette valeur : tous les codes plus anciens meurent.

Fenetre temporelle (facon TOTP)
-------------------------------
`time_bucket = floor(unix_time / bucket_seconds)` avec une tolerance de +/-1
tranche. Meme hors ligne, un code perime cesse donc de fonctionner. Le probleme
classique "je recule l'horloge de la tablette" ne donne rien : reculer l'horloge
ne fait qu'invalider les codes recents, et le compteur bloque le rejeu.

Force brute
-----------
Espace des etiquettes : 10^7. Combinaisons acceptables simultanement :
W (16) x 3 tranches = 48, soit p = 4,8e-6 par essai. Couple au verrouillage
progressif de l'appareil (5 essais -> 5 min, 10 -> 30 min, 15 -> 24 h + alerte
parentale), l'attaque est hors de portee.

Ce module est volontairement **pur** (aucune dependance, aucune I/O) : il est
duplique a l'identique en TypeScript dans `shared/unlock-protocol.ts` pour
l'application React Native, et couvert par des vecteurs de test communs.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass
from enum import IntEnum

PROTOCOL_VERSION = "KODA1"
CODE_DIGITS = 10
TAG_DIGITS = 7
DURATION_STEP_MINUTES = 5
MAX_DURATION_UNITS = 99
DEFAULT_LOOKAHEAD = 16
DEFAULT_BUCKET_TOLERANCE = 1
SECRET_BYTES = 32


class UnlockKind(IntEnum):
    """Nature d'un code. Le chiffre est transporte en clair dans le code."""

    PARENT_DIRECT = 0  # devoirs faits hors ligne, le parent debloque
    ASSESSMENT_REWARD = 1  # evaluation reussie au-dessus du seuil
    XP_REDEEM = 2  # conversion de points d'experience en minutes
    PARENT_BONUS = 3  # rallonge exceptionnelle
    EMERGENCY = 4  # deblocage de secours (appareil durablement hors ligne)


#: Duree d'une tranche temporelle, par nature de code (en secondes).
BUCKET_SECONDS: dict[UnlockKind, int] = {
    UnlockKind.PARENT_DIRECT: 1800,
    UnlockKind.ASSESSMENT_REWARD: 1800,
    UnlockKind.XP_REDEEM: 1800,
    UnlockKind.PARENT_BONUS: 1800,
    UnlockKind.EMERGENCY: 43200,  # 12 h : l'appareil peut etre longtemps hors ligne
}


class UnlockProtocolError(ValueError):
    """Code malforme, duree invalide ou signature incorrecte."""


@dataclass(frozen=True, slots=True)
class UnlockPayload:
    """Contenu utile d'un code, une fois verifie."""

    kind: UnlockKind
    duration_minutes: int
    counter: int
    time_bucket: int

    @property
    def duration_units(self) -> int:
        return self.duration_minutes // DURATION_STEP_MINUTES


# ---------------------------------------------------------------------------
# Primitives
# ---------------------------------------------------------------------------


def generate_device_secret() -> str:
    """Secret d'appareil (hex) remis une seule fois, lors de l'appairage."""
    return secrets.token_hex(SECRET_BYTES)


def current_bucket(kind: UnlockKind, now: float | None = None) -> int:
    now = time.time() if now is None else now
    return int(now // BUCKET_SECONDS[kind])


def _signing_input(
    device_id: str, counter: int, duration_units: int, kind: UnlockKind, time_bucket: int
) -> bytes:
    return "|".join(
        (
            PROTOCOL_VERSION,
            device_id,
            str(counter),
            str(duration_units),
            str(int(kind)),
            str(time_bucket),
        )
    ).encode("utf-8")


def _tag(
    secret_hex: str,
    device_id: str,
    counter: int,
    duration_units: int,
    kind: UnlockKind,
    time_bucket: int,
) -> int:
    """Troncature dynamique facon RFC 4226, ramenee a TAG_DIGITS chiffres."""
    key = bytes.fromhex(secret_hex)
    digest = hmac.new(
        key, _signing_input(device_id, counter, duration_units, kind, time_bucket), hashlib.sha256
    ).digest()
    offset = digest[-1] & 0x0F
    truncated = int.from_bytes(digest[offset : offset + 4], "big") & 0x7FFFFFFF
    return truncated % (10**TAG_DIGITS)


def normalize_code(raw: str) -> str:
    """Retire espaces, tirets et points ; tolere la saisie humaine."""
    return "".join(ch for ch in str(raw) if ch.isdigit())


def format_code(code: str) -> str:
    """Presentation lisible : `123 456 7890`."""
    code = normalize_code(code)
    if len(code) != CODE_DIGITS:
        return code
    return f"{code[0:3]} {code[3:6]} {code[6:10]}"


def minutes_to_units(minutes: int) -> int:
    if minutes <= 0:
        raise UnlockProtocolError("La duree doit etre strictement positive.")
    if minutes % DURATION_STEP_MINUTES:
        raise UnlockProtocolError(
            f"La duree doit etre un multiple de {DURATION_STEP_MINUTES} minutes."
        )
    units = minutes // DURATION_STEP_MINUTES
    if units > MAX_DURATION_UNITS:
        raise UnlockProtocolError(
            f"Duree maximale : {MAX_DURATION_UNITS * DURATION_STEP_MINUTES} minutes."
        )
    return units


# ---------------------------------------------------------------------------
# Emission
# ---------------------------------------------------------------------------


def issue_code(
    *,
    secret_hex: str,
    device_id: str,
    counter: int,
    duration_minutes: int,
    kind: UnlockKind = UnlockKind.PARENT_DIRECT,
    now: float | None = None,
) -> str:
    """Fabrique un code a 10 chiffres pour `counter` (deja incremente cote serveur)."""
    units = minutes_to_units(duration_minutes)
    kind = UnlockKind(kind)
    bucket = current_bucket(kind, now)
    tag = _tag(secret_hex, device_id, counter, units, kind, bucket)
    return f"{units:02d}{int(kind):01d}{tag:0{TAG_DIGITS}d}"


# ---------------------------------------------------------------------------
# Verification (identique cote serveur et cote appareil hors ligne)
# ---------------------------------------------------------------------------


def peek_code(code: str) -> tuple[UnlockKind, int]:
    """Lit la partie en clair (nature, duree) sans verifier la signature.

    Utile pour afficher "Code de 3 h" avant meme la validation, et pour choisir
    la taille de tranche temporelle a utiliser.
    """
    digits = normalize_code(code)
    if len(digits) != CODE_DIGITS:
        raise UnlockProtocolError(f"Un code KODA contient {CODE_DIGITS} chiffres.")
    units = int(digits[0:2])
    try:
        kind = UnlockKind(int(digits[2]))
    except ValueError as exc:  # pragma: no cover - defensif
        raise UnlockProtocolError("Nature de code inconnue.") from exc
    if units == 0:
        raise UnlockProtocolError("Duree nulle.")
    return kind, units * DURATION_STEP_MINUTES


def verify_code(
    *,
    code: str,
    secret_hex: str,
    device_id: str,
    last_counter: int,
    lookahead: int = DEFAULT_LOOKAHEAD,
    bucket_tolerance: int = DEFAULT_BUCKET_TOLERANCE,
    now: float | None = None,
) -> UnlockPayload:
    """Verifie un code et renvoie sa charge utile.

    Leve `UnlockProtocolError` si le code est malforme, perime, rejoue ou faux.
    L'appelant doit ensuite persister `payload.counter` comme nouveau
    `last_counter` (c'est ce qui tue definitivement les codes anterieurs).
    """
    digits = normalize_code(code)
    kind, duration_minutes = peek_code(digits)
    units = duration_minutes // DURATION_STEP_MINUTES
    provided = digits[3:]
    base_bucket = current_bucket(kind, now)

    for counter in range(last_counter + 1, last_counter + 1 + max(1, lookahead)):
        for offset in range(-bucket_tolerance, bucket_tolerance + 1):
            expected = _tag(secret_hex, device_id, counter, units, kind, base_bucket + offset)
            if hmac.compare_digest(f"{expected:0{TAG_DIGITS}d}", provided):
                return UnlockPayload(
                    kind=kind,
                    duration_minutes=duration_minutes,
                    counter=counter,
                    time_bucket=base_bucket + offset,
                )
    raise UnlockProtocolError("Code invalide, deja utilise ou expire.")


# ---------------------------------------------------------------------------
# Empreinte (journal d'audit / revocation)
# ---------------------------------------------------------------------------


def code_fingerprint(code: str, device_id: str) -> str:
    """Empreinte non reversible : on ne stocke jamais un code en clair."""
    digits = normalize_code(code)
    return hashlib.sha256(f"{PROTOCOL_VERSION}|{device_id}|{digits}".encode()).hexdigest()


# ---------------------------------------------------------------------------
# Verrouillage progressif apres erreurs de saisie
# ---------------------------------------------------------------------------

#: (nombre d'echecs cumules, duree de blocage en secondes)
LOCKOUT_LADDER: tuple[tuple[int, int], ...] = (
    (5, 5 * 60),
    (10, 30 * 60),
    (15, 24 * 3600),
)


def lockout_seconds_for(failed_attempts: int) -> int:
    """Duree de blocage de la saisie apres `failed_attempts` echecs consecutifs."""
    penalty = 0
    for threshold, seconds in LOCKOUT_LADDER:
        if failed_attempts >= threshold:
            penalty = seconds
    return penalty
