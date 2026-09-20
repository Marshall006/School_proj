"""Generateurs de questions de mathématiques.

Chaque fonction recoit un generateur aleatoire *déjà ensemence* (le tirage est
donc reproductible : même pays, même classe, même banque de questions), l'indice
de niveau et le contexte pays (monnaie, prenoms, lieux).

Les enonces sont localises : un problème de monnaie parle d'euros en France et
de francs CFA au Bénin, en Cote d'Ivoire ou au Senegal, avec des ordres de
grandeur credibles dans chaque cas.
"""

from __future__ import annotations

from fractions import Fraction
from random import Random
from typing import Any

from app.content.common import (
    KEYPAD_DECIMAL,
    KEYPAD_NUMERIC,
    WIDGET_COLUMN_OP,
    WIDGET_FRACTION,
    WIDGET_LONG_DIVISION,
    expression,
    fmt_decimal,
    fmt_int,
    handwritten,
    mcq,
    money,
    money_value,
    numeric,
    ordering,
    short_text,
    true_false,
)
from app.content.numerals import en_lettres

#: Plage de nombres manipules, par indice de niveau.
RANGE_BY_LEVEL = {1: 20, 2: 100, 3: 1_000, 4: 10_000, 5: 1_000_000, 6: 100_000_000}


def _span(level: int) -> int:
    return RANGE_BY_LEVEL.get(level, 1_000)


def _diff(level: int, base: int) -> int:
    """Ajuste la difficulte editoriale à la classe."""
    return max(1, min(5, base))


# ---------------------------------------------------------------------------
# Numeration
# ---------------------------------------------------------------------------


def numeration(rng: Random, level: int, country: Any) -> list[dict[str, Any]]:
    span = _span(level)
    items: list[dict[str, Any]] = []
    positions = ["unités", "dizaines", "centaines", "milliers"][: 2 + min(2, level - 1)]

    for _ in range(3):
        n = rng.randint(span // 10, span - 1)
        index = rng.randrange(len(positions))
        digit = (n // (10**index)) % 10
        items.append(
            numeric(
                f"Dans le nombre {fmt_int(n)}, quel est le chiffre des {positions[index]} ?",
                digit,
                difficulty=_diff(level, 2),
                explanation=(
                    f"On compte les rangs à partir de la droite : "
                    f"{' , '.join(positions)}. Le chiffre des {positions[index]} de "
                    f"{fmt_int(n)} est {digit}."
                ),
                tags=["numeration", "valeur_position"],
            )
        )

    if level >= 3:
        for _ in range(2):
            n = rng.randint(span // 10, span - 1)
            count = n // 10
            items.append(
                numeric(
                    f"Combien de dizaines entières contient le nombre {fmt_int(n)} ?",
                    count,
                    difficulty=_diff(level, 3),
                    explanation=(
                        f"Attention : on demande le *nombre* de dizaines, pas le chiffre "
                        f"des dizaines. {fmt_int(n)} = {fmt_int(count)} dizaines et "
                        f"{n % 10} unités."
                    ),
                    tags=["numeration", "piege_classique"],
                )
            )

    for _ in range(2):
        n = rng.randint(span // 20, span - 1)
        items.append(
            numeric(
                f"Écris en chiffres : {en_lettres(n)}.",
                n,
                difficulty=_diff(level, 2),
                explanation=f"{en_lettres(n)} s'écrit {fmt_int(n)}.",
                tags=["numeration", "lecture"],
            )
        )

    for _ in range(2):
        pool = sorted({rng.randint(span // 10, span - 1) for _ in range(4)})
        while len(pool) < 4:
            pool = sorted(set(pool) | {rng.randint(span // 10, span - 1)})
        rng.shuffle(pool)
        biggest = max(pool)
        items.append(
            mcq(
                "Quel est le plus grand de ces nombres ?",
                [fmt_int(v) for v in pool],
                pool.index(biggest),
                difficulty=_diff(level, 2),
                explanation=(
                    "Pour comparer, on regarde d'abord le nombre de chiffres, "
                    "puis les chiffres de gauche à droite."
                ),
                tags=["numeration", "comparaison"],
            )
        )

    for _ in range(2):
        values = sorted({rng.randint(span // 10, span - 1) for _ in range(4)})
        if len(values) < 4:
            continue
        items.append(
            ordering(
                "Range ces nombres du plus petit au plus grand.",
                [fmt_int(v) for v in values],
                difficulty=_diff(level, 3),
                explanation="On compare rang par rang, en partant de la gauche.",
                tags=["numeration", "rangement"],
                shuffle=rng,
            )
        )

    if level >= 4:
        for _ in range(2):
            n = rng.randint(1000, span - 1)
            rounded = int(round(n, -2))
            items.append(
                numeric(
                    f"Arrondis {fmt_int(n)} à la centaine la plus proche.",
                    rounded,
                    difficulty=_diff(level, 3),
                    explanation=(
                        f"On regarde le chiffre des dizaines ({(n // 10) % 10}) : "
                        f"s'il est inférieur à 5 on arrondit en dessous, sinon au-dessus. "
                        f"On obtient {fmt_int(rounded)}."
                    ),
                    tags=["numeration", "arrondi"],
                )
            )

    n = rng.randint(span // 10, span - 2)
    items.append(
        numeric(
            f"Quel nombre vient juste après {fmt_int(n)} ?",
            n + 1,
            difficulty=1,
            explanation=f"Le successeur de {fmt_int(n)} est {fmt_int(n + 1)}.",
            tags=["numeration", "suite"],
        )
    )
    return items


# ---------------------------------------------------------------------------
# Addition / soustraction
# ---------------------------------------------------------------------------


def addition_soustraction(rng: Random, level: int, country: Any) -> list[dict[str, Any]]:
    span = _span(level)
    items: list[dict[str, Any]] = []

    for _ in range(3):
        a, b = rng.randint(span // 10, span - 1), rng.randint(span // 10, span - 1)
        items.append(
            expression(
                f"Calcule : {fmt_int(a)} + {fmt_int(b)}",
                a + b,
                difficulty=_diff(level, 2),
                explanation=f"{fmt_int(a)} + {fmt_int(b)} = {fmt_int(a + b)}.",
                tags=["addition", "calcul_pose"],
                input_spec=WIDGET_COLUMN_OP,
                instructions="Pose l'opération en colonnes si tu en as besoin.",
            )
        )

    for _ in range(3):
        a = rng.randint(span // 5, span - 1)
        b = rng.randint(span // 20, a - 1)
        items.append(
            expression(
                f"Calcule : {fmt_int(a)} - {fmt_int(b)}",
                a - b,
                difficulty=_diff(level, 3),
                explanation=f"{fmt_int(a)} - {fmt_int(b)} = {fmt_int(a - b)}.",
                tags=["soustraction", "calcul_pose"],
                input_spec=WIDGET_COLUMN_OP,
            )
        )

    for _ in range(2):
        a = rng.randint(span // 10, span - 1)
        total = a + rng.randint(span // 10, span // 2)
        items.append(
            numeric(
                f"Complète : {fmt_int(a)} + ... = {fmt_int(total)}",
                total - a,
                difficulty=_diff(level, 3),
                explanation=(
                    f"Il s'agit d'une soustraction cachee : "
                    f"{fmt_int(total)} - {fmt_int(a)} = {fmt_int(total - a)}."
                ),
                tags=["addition", "complement"],
            )
        )

    for _ in range(2):
        a, b, c = (rng.randint(2, max(9, span // 100)) * 10 for _ in range(3))
        items.append(
            numeric(
                f"Calcule mentalement : {a} + {b} + {c}",
                a + b + c,
                difficulty=_diff(level, 2),
                explanation="On peut regrouper les nombres pour aller plus vite.",
                tags=["calcul_mental"],
                estimated_seconds=30,
            )
        )

    if level >= 4:
        a, b = rng.randint(1000, span - 1), rng.randint(1000, span - 1)
        items.append(
            handwritten(
                f"Pose et effectue : {fmt_int(a)} + {fmt_int(b)}",
                a + b,
                difficulty=_diff(level, 3),
                explanation=f"Le résultat est {fmt_int(a + b)}.",
                tags=["addition", "ardoise"],
            )
        )
    return items


# ---------------------------------------------------------------------------
# Multiplication
# ---------------------------------------------------------------------------


def multiplication(rng: Random, level: int, country: Any) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []

    for _ in range(4):
        a, b = rng.randint(2, 9), rng.randint(2, 9)
        items.append(
            numeric(
                f"Combien font {a} x {b} ?",
                a * b,
                difficulty=1 if level <= 3 else 1,
                explanation=f"Table de {a} : {a} x {b} = {a * b}.",
                tags=["multiplication", "tables"],
                estimated_seconds=20,
            )
        )

    for _ in range(3):
        a = rng.randint(11, 99)
        b = rng.randint(2, 9) if level <= 3 else rng.randint(11, 49)
        items.append(
            expression(
                f"Calcule : {a} x {b}",
                a * b,
                difficulty=_diff(level, 3 if level <= 3 else 4),
                explanation=f"{a} x {b} = {a * b}.",
                tags=["multiplication", "calcul_pose"],
                input_spec=WIDGET_COLUMN_OP,
            )
        )

    for _ in range(2):
        a = rng.randint(12, 999)
        factor = rng.choice([10, 100, 1000])
        items.append(
            numeric(
                f"Calcule : {a} x {factor}",
                a * factor,
                difficulty=_diff(level, 2),
                explanation=(
                    f"Multiplier par {factor} revient à ajouter "
                    f"{len(str(factor)) - 1} zero(s) : {fmt_int(a * factor)}."
                ),
                tags=["multiplication", "puissances_de_10"],
            )
        )

    n = rng.randint(3, 12)
    multiples = [n * k for k in range(1, 5)]
    intrus = n * 3 + 1
    options = [fmt_int(v) for v in multiples[:3]] + [fmt_int(intrus)]
    items.append(
        mcq(
            f"Lequel de ces nombres n'est PAS un multiple de {n} ?",
            options,
            3,
            difficulty=_diff(level, 3),
            explanation=f"{intrus} n'est pas dans la table de {n}.",
            tags=["multiplication", "multiples"],
            shuffle=rng,
        )
    )

    a, b = rng.randint(3, 9), rng.randint(3, 9)
    items.append(
        true_false(
            f"{a} x {b} donne le même résultat que {b} x {a}.",
            True,
            difficulty=1,
            explanation="La multiplication est commutative : l'ordre des facteurs ne change rien.",
            tags=["multiplication", "propriete"],
        )
    )
    return items


# ---------------------------------------------------------------------------
# Division
# ---------------------------------------------------------------------------


def division(rng: Random, level: int, country: Any) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []

    for _ in range(3):
        divisor = rng.randint(2, 9)
        quotient = rng.randint(11, 99 if level <= 4 else 999)
        dividend = divisor * quotient
        items.append(
            expression(
                f"Calcule : {fmt_int(dividend)} : {divisor}",
                quotient,
                difficulty=_diff(level, 3),
                explanation=f"{fmt_int(dividend)} = {divisor} x {fmt_int(quotient)}, donc le quotient est {fmt_int(quotient)}.",
                tags=["division", "division_exacte"],
                input_spec=WIDGET_LONG_DIVISION,
                instructions="Utilisé la potence : glisse les barres pour poser ta division.",
            )
        )

    for _ in range(3):
        divisor = rng.randint(3, 9)
        quotient = rng.randint(12, 99 if level <= 4 else 499)
        remainder = rng.randint(1, divisor - 1)
        dividend = divisor * quotient + remainder
        items.append(
            numeric(
                f"Dans la division de {fmt_int(dividend)} par {divisor}, quel est le reste ?",
                remainder,
                difficulty=_diff(level, 4),
                explanation=(
                    f"{fmt_int(dividend)} = {divisor} x {fmt_int(quotient)} + {remainder}. "
                    f"Le reste est toujours plus petit que le diviseur."
                ),
                tags=["division", "euclidienne", "reste"],
            )
        )
        items.append(
            numeric(
                f"Dans la division de {fmt_int(dividend)} par {divisor}, quel est le quotient entier ?",
                quotient,
                difficulty=_diff(level, 4),
                explanation=f"{fmt_int(dividend)} = {divisor} x {fmt_int(quotient)} + {remainder}.",
                tags=["division", "euclidienne", "quotient"],
                input_spec=WIDGET_LONG_DIVISION,
            )
        )

    divisor = rng.randint(2, 9)
    quotient = rng.randint(21, 99)
    remainder = rng.randint(1, divisor - 1)
    dividend = divisor * quotient + remainder
    items.append(
        true_false(
            f"Dans la division de {fmt_int(dividend)} par {divisor}, le reste peut valoir {divisor}.",
            False,
            difficulty=_diff(level, 3),
            explanation="Non : le reste est toujours strictement inférieur au diviseur.",
            tags=["division", "propriete"],
        )
    )

    if level >= 5:
        divisor = rng.randint(11, 25)
        quotient = rng.randint(12, 99)
        dividend = divisor * quotient
        items.append(
            handwritten(
                f"Pose et effectue la division : {fmt_int(dividend)} : {divisor}",
                quotient,
                difficulty=_diff(level, 4),
                explanation=f"Le quotient est {fmt_int(quotient)} et le reste est 0.",
                tags=["division", "ardoise"],
            )
        )
    return items


# ---------------------------------------------------------------------------
# Fractions
# ---------------------------------------------------------------------------


def fractions(rng: Random, level: int, country: Any) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []

    for _ in range(3):
        den = rng.choice([2, 3, 4, 5, 6, 8, 10])
        num = rng.randint(1, den - 1)
        total = den * rng.randint(2, 12)
        part = total * num // den
        items.append(
            numeric(
                f"Calcule les {num}/{den} de {fmt_int(total)}.",
                part,
                difficulty=_diff(level, 3),
                explanation=(
                    f"On divise par {den} : {fmt_int(total)} : {den} = {fmt_int(total // den)}, "
                    f"puis on multiplie par {num} : {fmt_int(part)}."
                ),
                tags=["fractions", "fraction_dune_quantite"],
                input_spec=KEYPAD_NUMERIC,
            )
        )

    for _ in range(3):
        factor = rng.randint(2, 6)
        den = rng.choice([2, 3, 4, 5])
        num = rng.randint(1, den - 1)
        items.append(
            expression(
                f"Simplifie la fraction {num * factor}/{den * factor}.",
                Fraction(num, den),
                difficulty=_diff(level, 4),
                explanation=(
                    f"On divise le numérateur et le dénominateur par {factor} : "
                    f"{num * factor}/{den * factor} = {num}/{den}."
                ),
                tags=["fractions", "simplification"],
                input_spec=WIDGET_FRACTION,
                require_form="fraction_irreductible",
                display=f"{num}/{den}",
            )
        )

    for _ in range(2):
        den = rng.choice([4, 5, 6, 8, 10])
        a, b = rng.sample(range(1, den), 2)
        bigger = max(a, b)
        items.append(
            mcq(
                f"Quelle est la plus grande fraction : {a}/{den} ou {b}/{den} ?",
                [f"{a}/{den}", f"{b}/{den}", "Elles sont égales"],
                0 if a == bigger else 1,
                difficulty=_diff(level, 2),
                explanation=(
                    "A dénominateur égal, la plus grande fraction est celle qui a le "
                    "plus grand numérateur."
                ),
                tags=["fractions", "comparaison"],
                shuffle=rng,
            )
        )

    for _ in range(2):
        den = rng.choice([4, 5, 6, 8])
        a = rng.randint(1, den - 2)
        b = rng.randint(1, den - a - 1) if den - a - 1 >= 1 else 1
        result = Fraction(a + b, den)
        items.append(
            expression(
                f"Calcule : {a}/{den} + {b}/{den}",
                result,
                difficulty=_diff(level, 3),
                explanation=(
                    f"Les dénominateurs sont identiques : on additionne les numérateurs. "
                    f"{a}/{den} + {b}/{den} = {a + b}/{den}"
                    + (
                        f" = {result.numerator}/{result.denominator}."
                        if result.denominator != den
                        else "."
                    )
                ),
                tags=["fractions", "addition"],
                input_spec=WIDGET_FRACTION,
                accept=[f"{a + b}/{den}"],
                display=f"{result.numerator}/{result.denominator}",
            )
        )

    den = rng.choice([2, 4, 5, 10])
    num = rng.randint(1, den - 1)
    items.append(
        numeric(
            f"Écris {num}/{den} sous forme décimale.",
            Fraction(num, den),
            difficulty=_diff(level, 4),
            explanation=f"{num}/{den} = {num} : {den} = {fmt_decimal(num / den, 2 if den != 10 else 1)}.",
            tags=["fractions", "decimaux"],
            input_spec=KEYPAD_DECIMAL,
            display=fmt_decimal(num / den, 2),
        )
    )

    items.append(
        true_false(
            "Une fraction dont le numérateur est plus grand que le dénominateur est plus grande que 1.",
            True,
            difficulty=_diff(level, 3),
            explanation="Oui : par exemple 7/4 = 1,75, ce qui est bien supérieur à 1.",
            tags=["fractions", "propriete"],
        )
    )
    return items


# ---------------------------------------------------------------------------
# Nombres decimaux
# ---------------------------------------------------------------------------


def decimaux(rng: Random, level: int, country: Any) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    ranks = ["dixièmes", "centièmes", "millièmes"]

    for _ in range(3):
        whole = rng.randint(1, 99)
        decimals = rng.randint(1, 999)
        value = round(whole + decimals / 1000, 3)
        index = rng.randrange(3)
        digit = int(f"{decimals:03d}"[index])
        items.append(
            numeric(
                f"Dans le nombre {fmt_decimal(value, 3)}, quel est le chiffre des {ranks[index]} ?",
                digit,
                difficulty=_diff(level, 3),
                explanation=(
                    "Après la virgule on trouve, dans l'ordre : les dixièmes, "
                    f"les centièmes puis les milliemes. Ici c'est {digit}."
                ),
                tags=["decimaux", "valeur_position"],
            )
        )

    for _ in range(3):
        a = round(rng.randint(1, 200) + rng.randrange(1, 100) / 100, 2)
        b = round(rng.randint(1, 200) + rng.randrange(1, 100) / 100, 2)
        items.append(
            expression(
                f"Calcule : {fmt_decimal(a)} + {fmt_decimal(b)}",
                round(a + b, 2),
                difficulty=_diff(level, 3),
                explanation=(
                    "On aligne les virgules avant d'additionner. Résultat : "
                    f"{fmt_decimal(round(a + b, 2))}."
                ),
                tags=["decimaux", "addition"],
                input_spec=WIDGET_COLUMN_OP,
                display=fmt_decimal(round(a + b, 2)),
            )
        )

    for _ in range(2):
        a = round(rng.randint(1, 50) + rng.randrange(1, 100) / 100, 2)
        factor = rng.choice([10, 100])
        items.append(
            numeric(
                f"Calcule : {fmt_decimal(a)} x {factor}",
                round(a * factor, 2),
                difficulty=_diff(level, 3),
                explanation=(
                    f"Multiplier par {factor} deplace la virgule de "
                    f"{len(str(factor)) - 1} rang(s) vers la droite."
                ),
                tags=["decimaux", "puissances_de_10"],
                input_spec=KEYPAD_DECIMAL,
                display=fmt_decimal(round(a * factor, 2)),
            )
        )

    a = round(rng.randint(1, 9) + rng.randrange(10, 99) / 100, 2)
    b = round(a + rng.randrange(1, 9) / 100, 2)
    items.append(
        mcq(
            f"Quel est le plus grand : {fmt_decimal(a)} ou {fmt_decimal(b)} ?",
            [fmt_decimal(a), fmt_decimal(b), "Ils sont égaux"],
            1,
            difficulty=_diff(level, 3),
            explanation=(
                "On compare d'abord la partie entière, puis les chiffres après la "
                "virgule, rang par rang."
            ),
            tags=["decimaux", "comparaison"],
            shuffle=rng,
        )
    )

    items.append(
        true_false(
            "Le nombre 2,5 est plus petit que 2,45.",
            False,
            difficulty=_diff(level, 3),
            explanation=(
                "Piege classique : 2,5 = 2,50 et 2,50 > 2,45. Un nombre decimal ne se "
                "compare pas comme un nombre entier."
            ),
            tags=["decimaux", "piege_classique"],
        )
    )
    return items


# ---------------------------------------------------------------------------
# Grandeurs et mesures
# ---------------------------------------------------------------------------

_LENGTH = [("km", 1000), ("m", 1), ("cm", 0.01), ("mm", 0.001)]
_MASS = [("kg", 1000), ("g", 1), ("mg", 0.001)]


def mesures(rng: Random, level: int, country: Any) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []

    for _ in range(3):
        value = rng.choice([2, 3, 5, 7, 12, 25])
        items.append(
            numeric(
                f"Convertis : {value} m = ... cm",
                value * 100,
                difficulty=_diff(level, 2),
                explanation=f"1 m = 100 cm, donc {value} m = {value * 100} cm.",
                tags=["mesures", "longueurs"],
                unit="cm",
            )
        )

    for _ in range(2):
        value = rng.choice([1500, 2400, 3200, 7500])
        items.append(
            numeric(
                f"Convertis : {fmt_int(value)} m = ... km",
                round(value / 1000, 3),
                difficulty=_diff(level, 3),
                explanation=f"1 km = 1000 m, donc {fmt_int(value)} m = {fmt_decimal(value / 1000, 3)} km.",
                tags=["mesures", "longueurs"],
                input_spec=KEYPAD_DECIMAL,
                display=fmt_decimal(value / 1000, 3),
            )
        )

    for _ in range(2):
        kilos = rng.randint(2, 15)
        items.append(
            numeric(
                f"Convertis : {kilos} kg = ... g",
                kilos * 1000,
                difficulty=_diff(level, 2),
                explanation=f"1 kg = 1000 g, donc {kilos} kg = {fmt_int(kilos * 1000)} g.",
                tags=["mesures", "masses"],
                unit="g",
            )
        )

    for _ in range(3):
        hours = rng.randint(1, 4)
        minutes = rng.choice([15, 20, 30, 45])
        items.append(
            numeric(
                f"Convertis en minutes : {hours} h {minutes} min",
                hours * 60 + minutes,
                difficulty=_diff(level, 3),
                explanation=f"1 h = 60 min, donc {hours} h {minutes} min = {hours * 60 + minutes} min.",
                tags=["mesures", "durees"],
                unit="min",
            )
        )

    start_h, start_m = rng.randint(7, 15), rng.choice([0, 15, 30, 45])
    dur = rng.choice([45, 75, 90, 105])
    end = (start_h * 60 + start_m + dur) % (24 * 60)
    items.append(
        short_text(
            f"Un cours commence à {start_h}h{start_m:02d} et dure {dur} minutes. "
            "À quelle heure se terminé-t-il ? (écris comme 14h30)",
            [f"{end // 60}h{end % 60:02d}", f"{end // 60}h{end % 60}"],
            difficulty=_diff(level, 4),
            explanation=(f"{start_h}h{start_m:02d} + {dur} min = {end // 60}h{end % 60:02d}."),
            tags=["mesures", "durees", "probleme"],
            max_distance=0,
        )
    )

    items.append(
        mcq(
            "Quelle unité convient le mieux pour mesurer la longueur d'une salle de classe ?",
            ["le millimètre", "le mètre", "le kilomètre", "le gramme"],
            1,
            difficulty=1,
            explanation="Une salle de classe mesure quelques mètres : le mètre est adapte.",
            tags=["mesures", "unites"],
            shuffle=rng,
        )
    )
    return items


# ---------------------------------------------------------------------------
# Geometrie
# ---------------------------------------------------------------------------


def geometrie(rng: Random, level: int, country: Any) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []

    for _ in range(3):
        length, width = rng.randint(3, 25), rng.randint(2, 20)
        items.append(
            numeric(
                f"Un rectangle mesure {length} cm de long et {width} cm de large. "
                "Quel est son périmètre ?",
                2 * (length + width),
                difficulty=_diff(level, 3),
                explanation=(
                    f"Périmètre = 2 x (Longueur + largeur) = 2 x ({length} + {width}) = "
                    f"{2 * (length + width)} cm."
                ),
                tags=["geometrie", "perimetre"],
                unit="cm",
            )
        )

    for _ in range(3):
        length, width = rng.randint(3, 20), rng.randint(2, 15)
        items.append(
            numeric(
                f"Un rectangle mesure {length} cm sur {width} cm. Quelle est son aire ?",
                length * width,
                difficulty=_diff(level, 4),
                explanation=(
                    f"Aire = Longueur x largeur = {length} x {width} = {length * width} cm2. "
                    "Attention à ne pas confondre avec le périmètre."
                ),
                tags=["geometrie", "aire", "piege_classique"],
                unit="cm2",
            )
        )

    side = rng.randint(3, 18)
    items.append(
        numeric(
            f"Quel est le périmètre d'un carré de cote {side} cm ?",
            4 * side,
            difficulty=_diff(level, 2),
            explanation=f"Périmètre du carré = 4 x cote = 4 x {side} = {4 * side} cm.",
            tags=["geometrie", "perimetre", "carre"],
            unit="cm",
        )
    )

    items.append(
        mcq(
            "Combien de côtés possede un quadrilatère ?",
            ["3", "4", "5", "6"],
            1,
            difficulty=1,
            explanation="Le préfixe quadri- signifie quatre.",
            tags=["geometrie", "figures"],
            shuffle=rng,
        )
    )
    items.append(
        mcq(
            "Un angle droit mesure :",
            ["45 degrés", "90 degrés", "180 degrés", "360 degrés"],
            1,
            difficulty=_diff(level, 2),
            explanation="Un angle droit mesure 90 degrés : c'est le coin d'une feuille.",
            tags=["geometrie", "angles"],
            shuffle=rng,
        )
    )
    items.append(
        true_false(
            "Tous les carres sont des rectangles.",
            True,
            difficulty=_diff(level, 4),
            explanation=(
                "Vrai : un rectangle à quatre angles droits, et le carré aussi. "
                "En revanche tous les rectangles ne sont pas des carres."
            ),
            tags=["geometrie", "logique"],
        )
    )

    if level >= 5:
        radius = rng.randint(2, 12)
        items.append(
            numeric(
                f"Un cercle à un rayon de {radius} cm. Quel est son diamètre ?",
                2 * radius,
                difficulty=_diff(level, 2),
                explanation=f"Le diamètre vaut deux fois le rayon : 2 x {radius} = {2 * radius} cm.",
                tags=["geometrie", "cercle"],
                unit="cm",
            )
        )
    return items


# ---------------------------------------------------------------------------
# Problemes
# ---------------------------------------------------------------------------


def problemes(rng: Random, level: int, country: Any) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    names = country.given_names
    place = rng.choice(country.places)

    for _ in range(3):
        name = rng.choice(names)
        unit_price = rng.choice([1.5, 2.0, 2.5, 3.0, 4.5])
        quantity = rng.randint(3, 12)
        total = round(unit_price * quantity, 2)
        items.append(
            numeric(
                f"{name} achète {quantity} cahiers à {money(unit_price, country)} l'unité. "
                "Quel est le montant total à payer ?",
                money_value(total, country),
                difficulty=_diff(level, 3),
                explanation=(
                    f"On multiplie le prix unitaire par la quantité : "
                    f"{money(unit_price, country)} x {quantity} = {money(total, country)}."
                ),
                tags=["probleme", "monnaie", "multiplication"],
                input_spec=KEYPAD_DECIMAL if country.money_scale == 1 else KEYPAD_NUMERIC,
                display=money(total, country),
            )
        )

    for _ in range(2):
        name = rng.choice(names)
        given = rng.choice([10.0, 20.0, 50.0])
        spent = round(rng.choice([3.5, 7.5, 12.5, 18.0]), 2)
        if spent >= given:
            spent = round(given / 2, 2)
        change = round(given - spent, 2)
        items.append(
            numeric(
                f"{name} paie avec {money(given, country)} un article à "
                f"{money(spent, country)}. Combien lui rend-on ?",
                money_value(change, country),
                difficulty=_diff(level, 3),
                explanation=(
                    f"{money(given, country)} - {money(spent, country)} = {money(change, country)}."
                ),
                tags=["probleme", "monnaie", "soustraction"],
                input_spec=KEYPAD_DECIMAL if country.money_scale == 1 else KEYPAD_NUMERIC,
                display=money(change, country),
            )
        )

    for _ in range(2):
        name = rng.choice(names)
        total_items = rng.randint(4, 9) * rng.randint(6, 12)
        per_box = rng.choice([6, 8, 12])
        boxes = total_items // per_box
        rest = total_items % per_box
        items.append(
            numeric(
                f"À l'école de {place}, on range {total_items} livres dans des cartons "
                f"de {per_box} livres. Combien de cartons sont completement remplis ?",
                boxes,
                difficulty=_diff(level, 4),
                explanation=(
                    f"{total_items} : {per_box} = {boxes} reste {rest}. "
                    f"Il y a donc {boxes} cartons pleins"
                    + (f" et {rest} livres en trop." if rest else ".")
                ),
                tags=["probleme", "division", "euclidienne"],
            )
        )

    name = rng.choice(names)
    distance = rng.randint(3, 15)
    days = rng.randint(4, 6)
    items.append(
        numeric(
            f"{name} parcourt {distance} km chaque jour pour aller à l'école et en revenir. "
            f"Quelle distance cela représente-t-il en {days} jours ?",
            distance * days,
            difficulty=_diff(level, 3),
            explanation=f"{distance} km x {days} = {distance * days} km.",
            tags=["probleme", "multiplication", "mesures"],
            unit="km",
        )
    )

    if level >= 5:
        name = rng.choice(names)
        total = rng.randint(30, 90)
        part_a = rng.randint(10, total - 15)
        part_b = rng.randint(5, total - part_a - 1)
        rest = total - part_a - part_b
        items.append(
            numeric(
                f"Un sac contient {total} billes : {part_a} rouges, {part_b} bleues, "
                "le reste est vert. Combien y a-t-il de billes vertes ?",
                rest,
                difficulty=_diff(level, 4),
                explanation=f"{total} - {part_a} - {part_b} = {rest} billes vertes.",
                tags=["probleme", "plusieurs_etapes"],
            )
        )
    return items


# ---------------------------------------------------------------------------
# Proportionnalite et pourcentages
# ---------------------------------------------------------------------------


def proportionnalite(rng: Random, level: int, country: Any) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []

    for _ in range(3):
        pct = rng.choice([10, 20, 25, 50, 75])
        total = rng.choice([40, 60, 80, 120, 200, 400])
        items.append(
            numeric(
                f"Calcule {pct} % de {fmt_int(total)}.",
                total * pct // 100,
                difficulty=_diff(level, 3),
                explanation=(
                    f"{pct} % signifie {pct} pour 100 : {fmt_int(total)} x {pct} : 100 = "
                    f"{fmt_int(total * pct // 100)}."
                ),
                tags=["proportionnalite", "pourcentage"],
            )
        )

    for _ in range(2):
        unit = rng.choice([3, 4, 6, 8])
        qty1 = rng.randint(2, 5)
        qty2 = qty1 + rng.randint(2, 6)
        items.append(
            numeric(
                f"{qty1} stylos identiques coutent {money(unit * qty1, country)}. "
                f"Combien coutent {qty2} stylos ?",
                money_value(unit * qty2, country),
                difficulty=_diff(level, 4),
                explanation=(
                    f"Un stylo coute {money(unit, country)} "
                    f"({money(unit * qty1, country)} : {qty1}). "
                    f"Donc {qty2} stylos coutent {money(unit * qty2, country)}."
                ),
                tags=["proportionnalite", "regle_de_trois"],
                input_spec=KEYPAD_DECIMAL if country.money_scale == 1 else KEYPAD_NUMERIC,
                display=money(unit * qty2, country),
            )
        )

    speed = rng.choice([40, 60, 80, 90])
    hours = rng.choice([2, 3, 4])
    items.append(
        numeric(
            f"Une voiture roule à {speed} km/h pendant {hours} h. Quelle distance parcourt-elle ?",
            speed * hours,
            difficulty=_diff(level, 4),
            explanation=f"Distance = vitesse x temps = {speed} x {hours} = {speed * hours} km.",
            tags=["proportionnalite", "vitesse"],
            unit="km",
        )
    )

    items.append(
        true_false(
            "Si je double la quantité achetée, le prix double aussi dans une situation "
            "de proportionnalité.",
            True,
            difficulty=_diff(level, 3),
            explanation="C'est la definition même de la proportionnalité.",
            tags=["proportionnalite", "propriete"],
        )
    )

    discount = rng.choice([10, 20, 25])
    price = rng.choice([40, 60, 80, 200])
    final = price - price * discount // 100
    items.append(
        numeric(
            f"Un article coute {money(price, country)}. Il est solde de {discount} %. "
            "Quel est son nouveau prix ?",
            money_value(final, country),
            difficulty=_diff(level, 5),
            explanation=(
                f"La remise vaut {money(price * discount / 100, country)}. "
                f"Nouveau prix : {money(price, country)} - "
                f"{money(price * discount / 100, country)} = {money(final, country)}."
            ),
            tags=["proportionnalite", "pourcentage", "probleme"],
            input_spec=KEYPAD_DECIMAL if country.money_scale == 1 else KEYPAD_NUMERIC,
            display=money(final, country),
        )
    )
    return items
