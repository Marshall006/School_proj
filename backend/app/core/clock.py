"""Horloge injectable + detection de manipulation d'horloge cote appareil.

Toute la logique metier passe par `now()` : les tests peuvent ainsi voyager
dans le temps sans `sleep`, et la production reste sur UTC.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

_frozen_at: datetime | None = None
_offset = timedelta(0)


def now() -> datetime:
    if _frozen_at is not None:
        return _frozen_at
    return datetime.now(UTC) + _offset


def unix_now() -> float:
    return now().timestamp()


@contextmanager
def frozen_time(instant: datetime):
    """Fige l'horloge applicative (tests)."""
    global _frozen_at
    previous, _frozen_at = _frozen_at, instant.astimezone(UTC)
    try:
        yield _frozen_at
    finally:
        _frozen_at = previous


@contextmanager
def time_travel(delta: timedelta):
    """Decale l'horloge applicative (tests d'expiration, de carence...)."""
    global _offset
    previous, _offset = _offset, _offset + delta
    try:
        yield
    finally:
        _offset = previous


def ensure_utc(value: datetime | None) -> datetime | None:
    """SQLite rend des datetimes naives : on les recolle a UTC."""
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class ClockAssessment:
    """Verdict sur la coherence entre l'horloge murale d'un appareil et la notre."""

    skew_ms: int
    tampered: bool
    reason: str | None = None

    @property
    def trustworthy(self) -> bool:
        return not self.tampered


def assess_device_clock(
    *,
    device_wall_ms: int,
    server_time: datetime | None = None,
    tolerance_ms: int = 120_000,
) -> ClockAssessment:
    """Compare l'horloge annoncee par l'appareil a l'horloge serveur."""
    reference = (server_time or now()).timestamp() * 1000
    skew = int(device_wall_ms - reference)
    if abs(skew) > tolerance_ms:
        direction = "avance" if skew > 0 else "retard"
        return ClockAssessment(
            skew_ms=skew,
            tampered=True,
            reason=f"Horloge de l'appareil en {direction} de {abs(skew) // 1000} s.",
        )
    return ClockAssessment(skew_ms=skew, tampered=False)
