"""Registre des generateurs : `TopicSpec.generator` -> fonction."""

from __future__ import annotations

from collections.abc import Callable
from random import Random
from typing import Any

from app.content import gen_francais, gen_math, gen_monde

Generator = Callable[[Random, int, Any], list[dict[str, Any]]]

REGISTRY: dict[str, Generator] = {
    # Mathematiques
    "numeration": gen_math.numeration,
    "addition_soustraction": gen_math.addition_soustraction,
    "multiplication": gen_math.multiplication,
    "division": gen_math.division,
    "fractions": gen_math.fractions,
    "decimaux": gen_math.decimaux,
    "mesures": gen_math.mesures,
    "geometrie": gen_math.geometrie,
    "problemes": gen_math.problemes,
    "proportionnalite": gen_math.proportionnalite,
    # Francais
    "conjugaison": gen_francais.conjugaison,
    "grammaire": gen_francais.grammaire,
    "orthographe": gen_francais.orthographe,
    "vocabulaire": gen_francais.vocabulaire,
    "comprehension": gen_francais.comprehension,
    # Sciences, histoire-geo, anglais, civique
    "sciences_vivant": gen_monde.sciences_vivant,
    "sciences_matiere": gen_monde.sciences_matiere,
    "geographie": gen_monde.geographie,
    "histoire": gen_monde.histoire,
    "anglais_vocabulaire": gen_monde.anglais_vocabulaire,
    "civique": gen_monde.civique,
}


def get(name: str) -> Generator | None:
    return REGISTRY.get(name)
