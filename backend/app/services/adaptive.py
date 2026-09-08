"""Moteur adaptatif : estimation de maitrise et assemblage d'epreuves.

Deux idees directrices.

**Estimer plutot que compter.** Un simple pourcentage de reussite oublie que
les questions n'ont pas la meme difficulte. On maintient donc, par (enfant,
notion), une aptitude `ability` sur une echelle logistique facon Elo, comparee
a la difficulte calibree de chaque item. La probabilite de reussite predite
guide ensuite le choix des questions.

**Equilibrer plutot que punir.** Une epreuve composee uniquement des lacunes
demoralise. Chaque epreuve melange donc trois intentions :

===================  =====  ==========================================
Bloc                 Part   Objectif
===================  =====  ==========================================
remediation          40 %   notions fragiles ou a revoir (repetition espacee)
apprentissage        40 %   notions du programme en cours d'acquisition
consolidation        20 %   notions acquises : on entretient la confiance
===================  =====  ==========================================

La difficulte visee par bloc est celle qui donne une probabilite de reussite
proche de la "zone proximale de developpement" (~75 %), et non le maximum.

Le tirage est **reproductible** : a graine egale, epreuve egale (indispensable
pour les tests et pour rejouer un examen conteste).
"""

from __future__ import annotations

import math
import random
import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from app.core.clock import now as clock_now
from app.models.enums import MasteryBand

# --- Echelle de difficulte -------------------------------------------------

#: Correspondance entre difficulte editoriale (1..5) et difficulte logistique.
DIFFICULTY_TO_LOGIT: dict[int, float] = {1: -1.2, 2: -0.6, 3: 0.0, 4: 0.6, 5: 1.2}
LOGIT_SCALE = 0.9  # pente de la courbe logistique

#: Cible de reussite par bloc : on cherche l'effort juste, pas l'echec.
BUCKET_TARGET_P: dict[str, float] = {
    "remediation": 0.80,
    "apprentissage": 0.70,
    "consolidation": 0.88,
}
BUCKET_WEIGHTS: dict[str, float] = {
    "remediation": 0.40,
    "apprentissage": 0.40,
    "consolidation": 0.20,
}

EWMA_ALPHA = 0.3
ABILITY_K_BASE = 0.45
ABILITY_K_FLOOR = 0.12
ITEM_CALIBRATION_K = 0.04


# ---------------------------------------------------------------------------
# Etat de maitrise (structure legere, decouplee de l'ORM)
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class MasteryState:
    topic_id: uuid.UUID
    subject_code: str
    ability: float = 0.0
    ewma: float = 0.5
    attempts: int = 0
    correct: int = 0
    streak: int = 0
    ease: float = 2.5
    interval_days: float = 0.0
    next_review_at: datetime | None = None
    last_seen_at: datetime | None = None

    @property
    def band(self) -> MasteryBand:
        return band_for(self.ewma, self.attempts)

    def is_due(self, at: datetime | None = None) -> bool:
        if self.next_review_at is None:
            return self.attempts == 0
        return self.next_review_at <= (at or clock_now())


def band_for(ewma: float, attempts: int) -> MasteryBand:
    if attempts < 3:
        return MasteryBand.UNKNOWN
    if ewma < 0.45:
        return MasteryBand.FRAGILE
    if ewma < 0.7:
        return MasteryBand.EN_COURS
    if ewma < 0.9:
        return MasteryBand.ACQUIS
    return MasteryBand.EXPERT


def item_logit(difficulty: int, calibrated: float = 0.0) -> float:
    """Difficulte effective : valeur editoriale corrigee par l'observation."""
    base = DIFFICULTY_TO_LOGIT.get(int(difficulty), 0.0)
    return base + max(-1.0, min(1.0, calibrated))


def predicted_success(ability: float, difficulty_logit: float) -> float:
    """Probabilite de reussite (modele logistique a un parametre)."""
    return 1.0 / (1.0 + math.exp(-(ability - difficulty_logit) / LOGIT_SCALE))


def target_difficulty_logit(ability: float, target_p: float) -> float:
    """Difficulte donnant exactement `target_p` de chances de reussite."""
    target_p = min(max(target_p, 0.02), 0.98)
    return ability - LOGIT_SCALE * math.log(target_p / (1 - target_p))


# ---------------------------------------------------------------------------
# Mise a jour apres correction
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class MasteryUpdate:
    state: MasteryState
    predicted: float
    delta_ability: float
    item_calibration_delta: float
    band_before: MasteryBand
    band_after: MasteryBand

    @property
    def improved_band(self) -> bool:
        order = list(MasteryBand)
        return order.index(self.band_after) > order.index(self.band_before)


def update_mastery(
    state: MasteryState,
    *,
    score: float,
    difficulty: int,
    calibrated_difficulty: float = 0.0,
    at: datetime | None = None,
) -> MasteryUpdate:
    """Applique une reponse notee (0..1) a l'etat de maitrise.

    - aptitude : ajustement Elo, d'autant plus fort que l'historique est court ;
    - moyenne mobile : photographie du niveau recent ;
    - repetition espacee : quand faut-il revoir cette notion ?
    """
    at = at or clock_now()
    score = min(max(float(score), 0.0), 1.0)
    band_before = state.band

    logit = item_logit(difficulty, calibrated_difficulty)
    predicted = predicted_success(state.ability, logit)

    # K decroissant : on apprend vite au debut, on stabilise ensuite.
    k = max(ABILITY_K_FLOOR, ABILITY_K_BASE / (1 + state.attempts / 12))
    delta = k * (score - predicted)
    state.ability = round(max(-3.0, min(3.0, state.ability + delta)), 5)

    state.ewma = round((1 - EWMA_ALPHA) * state.ewma + EWMA_ALPHA * score, 5)
    state.attempts += 1
    state.correct += 1 if score >= 0.999 else 0
    state.streak = state.streak + 1 if score >= 0.6 else 0
    state.last_seen_at = at

    _schedule_review(state, score, at)

    return MasteryUpdate(
        state=state,
        predicted=predicted,
        delta_ability=delta,
        # Calibrage de l'item : plus de reussites qu'attendu => item plus facile.
        item_calibration_delta=ITEM_CALIBRATION_K * (predicted - score),
        band_before=band_before,
        band_after=state.band,
    )


def _schedule_review(state: MasteryState, score: float, at: datetime) -> None:
    """Repetition espacee (SM-2 allege, tolerant au credit partiel)."""
    quality = score * 5.0
    if score < 0.6:
        state.interval_days = 0.0
        state.ease = max(1.3, state.ease - 0.2)
        state.next_review_at = at  # a revoir des que possible
        return
    state.ease = min(
        3.0, max(1.3, state.ease + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)))
    )
    if state.interval_days <= 0:
        state.interval_days = 1.0
    elif state.interval_days <= 1:
        state.interval_days = 3.0
    else:
        state.interval_days = round(min(180.0, state.interval_days * state.ease), 2)
    state.next_review_at = at + timedelta(days=state.interval_days)


# ---------------------------------------------------------------------------
# Assemblage de l'epreuve
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class TopicCandidate:
    """Notion eligible, avec le nombre de questions disponibles."""

    topic_id: uuid.UUID
    subject_code: str
    name: str = ""
    question_count: int = 0
    is_core: bool = True
    position: int = 0


@dataclass(slots=True)
class BlueprintSlot:
    position: int
    bucket: str
    topic_id: uuid.UUID
    subject_code: str
    target_logit: float
    target_p: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "position": self.position,
            "bucket": self.bucket,
            "topic_id": str(self.topic_id),
            "subject_code": self.subject_code,
            "target_logit": round(self.target_logit, 3),
            "target_p": round(self.target_p, 3),
        }


@dataclass(slots=True)
class Blueprint:
    slots: list[BlueprintSlot] = field(default_factory=list)
    seed: int = 0
    rationale: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "seed": self.seed,
            "slots": [s.to_dict() for s in self.slots],
            "rationale": self.rationale,
            "distribution": self.distribution,
        }

    @property
    def distribution(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for slot in self.slots:
            counts[slot.bucket] = counts.get(slot.bucket, 0) + 1
        return counts


def classify_topics(
    candidates: Sequence[TopicCandidate],
    mastery: dict[uuid.UUID, MasteryState],
    at: datetime | None = None,
) -> dict[str, list[TopicCandidate]]:
    """Repartit les notions disponibles dans les trois blocs."""
    at = at or clock_now()
    buckets: dict[str, list[TopicCandidate]] = {
        "remediation": [],
        "apprentissage": [],
        "consolidation": [],
    }
    for candidate in candidates:
        if candidate.question_count <= 0:
            continue
        state = mastery.get(candidate.topic_id)
        if state is None:
            buckets["apprentissage"].append(candidate)
            continue
        band = state.band
        if band == MasteryBand.FRAGILE or (state.is_due(at) and state.ewma < 0.7):
            buckets["remediation"].append(candidate)
        elif band in (MasteryBand.ACQUIS, MasteryBand.EXPERT) and not state.is_due(at):
            buckets["consolidation"].append(candidate)
        else:
            buckets["apprentissage"].append(candidate)

    # Priorite interne : le plus fragile / le plus en retard d'abord.
    def weakness(candidate: TopicCandidate) -> tuple[float, float, int]:
        state = mastery.get(candidate.topic_id)
        overdue = 0.0
        if state and state.next_review_at:
            overdue = -(at - state.next_review_at).total_seconds()
        return (state.ewma if state else 0.5, overdue, candidate.position)

    buckets["remediation"].sort(key=weakness)
    buckets["apprentissage"].sort(key=weakness)
    buckets["consolidation"].sort(key=lambda c: -weakness(c)[0])
    return buckets


def allocate_counts(total: int, available: dict[str, list[TopicCandidate]]) -> dict[str, int]:
    """Repartit `total` questions selon les poids cibles, en comblant les manques.

    Si un bloc est vide (aucune lacune connue : tant mieux), sa part est
    redistribuee sur les blocs restants au prorata.
    """
    weights = {b: w for b, w in BUCKET_WEIGHTS.items() if available.get(b)}
    if not weights:
        return {}
    scale = sum(weights.values())
    raw = {b: total * w / scale for b, w in weights.items()}
    counts = {b: int(math.floor(v)) for b, v in raw.items()}
    remainder = total - sum(counts.values())
    # Les places restantes vont aux blocs dont la partie decimale est la plus forte.
    for bucket, _ in sorted(raw.items(), key=lambda kv: (-(kv[1] % 1), kv[0])):
        if remainder <= 0:
            break
        counts[bucket] += 1
        remainder -= 1
    return {b: c for b, c in counts.items() if c > 0}


def build_blueprint(
    *,
    candidates: Sequence[TopicCandidate],
    mastery: dict[uuid.UUID, MasteryState],
    question_count: int,
    difficulty_bias: float = 0.0,
    seed: int | None = None,
    at: datetime | None = None,
) -> Blueprint:
    """Construit le plan de l'epreuve : quelle notion, a quelle difficulte, et pourquoi."""
    at = at or clock_now()
    seed = seed if seed is not None else random.SystemRandom().getrandbits(48)
    rng = random.Random(seed)

    buckets = classify_topics(candidates, mastery, at)
    counts = allocate_counts(question_count, buckets)

    slots: list[BlueprintSlot] = []
    position = 0
    for bucket, count in counts.items():
        pool = buckets[bucket]
        if not pool:
            continue
        # Rotation ponderee : les premieres notions (les plus prioritaires) sortent
        # plus souvent, sans jamais exclure les autres.
        picks = _weighted_sample(pool, count, rng)
        target_p = min(0.95, max(0.35, BUCKET_TARGET_P[bucket] - 0.12 * difficulty_bias))
        for candidate in picks:
            state = mastery.get(candidate.topic_id)
            ability = state.ability if state else 0.0
            slots.append(
                BlueprintSlot(
                    position=position,
                    bucket=bucket,
                    topic_id=candidate.topic_id,
                    subject_code=candidate.subject_code,
                    target_logit=target_difficulty_logit(ability, target_p),
                    target_p=target_p,
                )
            )
            position += 1

    rng.shuffle(slots)
    for index, slot in enumerate(slots):
        slot.position = index

    return Blueprint(
        slots=slots,
        seed=seed,
        rationale={
            "requested": question_count,
            "allocated": counts,
            "pool_sizes": {b: len(v) for b, v in buckets.items()},
            "difficulty_bias": difficulty_bias,
            "weak_topics": [str(c.topic_id) for c in buckets["remediation"][:5]],
        },
    )


def _weighted_sample(
    pool: Sequence[TopicCandidate], count: int, rng: random.Random
) -> list[TopicCandidate]:
    """Tire `count` notions avec repetition seulement si le vivier est trop petit."""
    if not pool:
        return []
    unique = min(count, len(pool))
    weights = [1.0 / (1 + index * 0.35) for index in range(len(pool))]
    chosen: list[TopicCandidate] = []
    remaining = list(pool)
    remaining_weights = list(weights)
    for _ in range(unique):
        pick = rng.choices(range(len(remaining)), weights=remaining_weights, k=1)[0]
        chosen.append(remaining.pop(pick))
        remaining_weights.pop(pick)
    while len(chosen) < count:  # vivier plus petit que le nombre de questions
        chosen.append(pool[rng.randrange(len(pool))])
    return chosen


# ---------------------------------------------------------------------------
# Choix de la question dans une notion
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class QuestionCandidate:
    question_id: uuid.UUID
    topic_id: uuid.UUID
    difficulty: int
    calibrated: float = 0.0
    times_served: int = 0
    last_served_rank: int = 0  # 0 = jamais vue recemment ; plus grand = vue plus recemment


def select_question(
    slot: BlueprintSlot,
    pool: Iterable[QuestionCandidate],
    rng: random.Random,
    *,
    exclude: set[uuid.UUID] | None = None,
    recency_penalty: float = 0.8,
) -> QuestionCandidate | None:
    """Choisit l'item dont la difficulte colle le mieux a la cible du creneau."""
    exclude = exclude or set()
    best: tuple[float, float, QuestionCandidate] | None = None
    for candidate in pool:
        if candidate.question_id in exclude:
            continue
        distance = abs(item_logit(candidate.difficulty, candidate.calibrated) - slot.target_logit)
        penalty = recency_penalty * candidate.last_served_rank
        jitter = rng.random() * 1e-3  # depart d'egalite deterministe
        cost = distance + penalty + jitter
        if best is None or cost < best[0]:
            best = (cost, distance, candidate)
    return best[2] if best else None


# ---------------------------------------------------------------------------
# Diagnostic pour le tableau de bord parental
# ---------------------------------------------------------------------------


def identify_gaps(
    states: Iterable[MasteryState], *, limit: int = 5, at: datetime | None = None
) -> list[dict[str, Any]]:
    """Lacunes classees par urgence : c'est ce que le parent voit en premier."""
    at = at or clock_now()
    scored: list[tuple[float, MasteryState]] = []
    for state in states:
        if state.attempts == 0:
            continue
        urgency = (1.0 - state.ewma) * 2.0
        if state.next_review_at and state.next_review_at <= at:
            urgency += 0.5
        if state.band == MasteryBand.FRAGILE:
            urgency += 0.5
        urgency += min(0.5, state.attempts / 40)  # une lacune repetee compte double
        scored.append((urgency, state))
    scored.sort(key=lambda pair: -pair[0])
    return [
        {
            "topic_id": str(state.topic_id),
            "subject_code": state.subject_code,
            "band": state.band.value,
            "ewma": round(state.ewma, 3),
            "success_rate": round(state.correct / state.attempts, 3) if state.attempts else None,
            "attempts": state.attempts,
            "urgency": round(urgency, 3),
            "due": state.is_due(at),
        }
        for urgency, state in scored[:limit]
    ]
