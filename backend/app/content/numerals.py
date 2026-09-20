"""Écriture des nombres en toutes lettres (français).

Utilisé par les generateurs de numération ("Écris en chiffres : ...") et par
les corrections. Règles couvertes : et-un, soixante-dix, quatre-vingts,
accord de cent et de vingt, mille invariable.
"""

from __future__ import annotations

UNITS = [
    "zero",
    "un",
    "deux",
    "trois",
    "quatre",
    "cinq",
    "six",
    "sept",
    "huit",
    "neuf",
    "dix",
    "onze",
    "douze",
    "treize",
    "quatorze",
    "quinze",
    "seize",
    "dix-sept",
    "dix-huit",
    "dix-neuf",
]
TENS = {
    20: "vingt",
    30: "trente",
    40: "quarante",
    50: "cinquante",
    60: "soixante",
    80: "quatre-vingt",
}


def _below_hundred(n: int) -> str:
    if n < 20:
        return UNITS[n]
    if n < 70:
        ten, unit = divmod(n, 10)
        base = TENS[ten * 10]
        if unit == 0:
            return base
        if unit == 1:
            return f"{base} et un"
        return f"{base}-{UNITS[unit]}"
    if n < 80:  # 70..79 : soixante-dix, soixante et onze...
        rest = n - 60
        if rest == 11:
            return "soixante et onze"
        return f"soixante-{UNITS[rest]}"
    # 80..99
    rest = n - 80
    if rest == 0:
        return "quatre-vingts"
    return f"quatre-vingt-{UNITS[rest]}" if rest < 20 else f"quatre-vingt-{_below_hundred(rest)}"


def _below_thousand(n: int, *, standalone: bool = True) -> str:
    """`standalone=False` quand le groupe est suivi de "mille" ou "millions".

    Règle d'accord : vingt et cent prennent un s seulement s'ils terminent le
    nombre. On écrit donc "deux cents" mais "deux cent mille", "quatre-vingts"
    mais "quatre-vingt mille".
    """
    hundreds, rest = divmod(n, 100)
    if hundreds == 0:
        word = _below_hundred(rest)
        return word if standalone else word.replace("quatre-vingts", "quatre-vingt")
    head = "cent" if hundreds == 1 else f"{UNITS[hundreds]} cent"
    if rest == 0:
        return head if (hundreds == 1 or not standalone) else head + "s"
    return f"{head} {_below_thousand(rest, standalone=standalone)}"


def en_lettres(n: int) -> str:
    """Écrit un entier (0 <= n < 1 000 000 000) en toutes lettres."""
    if n < 0:
        return f"moins {en_lettres(-n)}"
    if n < 1000:
        return _below_thousand(n)
    if n < 1_000_000:
        thousands, rest = divmod(n, 1000)
        head = (
            "mille" if thousands == 1 else f"{_below_thousand(thousands, standalone=False)} mille"
        )
        return head if rest == 0 else f"{head} {_below_thousand(rest)}"
    millions, rest = divmod(n, 1_000_000)
    # "million" est un nom : cent et vingt s'accordent devant lui
    # (trois cents millions), contrairement a "mille" qui reste un adjectif.
    head = "un million" if millions == 1 else f"{_below_thousand(millions)} millions"
    return head if rest == 0 else f"{head} {en_lettres(rest)}"
