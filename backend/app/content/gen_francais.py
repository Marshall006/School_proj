"""Generateurs de questions de francais : conjugaison, grammaire, orthographe,
vocabulaire et comprehension de texte.

La conjugaison est produite par regles (avec les irregularites usuelles
explicitement listees) plutot que par une table figee : on obtient des dizaines
d'items justes par classe, sans recopier un manuel.
"""

from __future__ import annotations

from random import Random
from typing import Any

from app.content.common import (
    fill_blank,
    matching,
    mcq,
    short_text,
    true_false,
)

PRONOUNS = ["je", "tu", "il", "nous", "vous", "ils"]
PRONOUN_LABEL = {
    "je": "je",
    "tu": "tu",
    "il": "il",
    "nous": "nous",
    "vous": "vous",
    "ils": "ils",
}

#: "au present" mais "a l'imparfait" : la preposition depend du temps.
TENSE_PHRASE = {
    "present": "au present",
    "imparfait": "a l'imparfait",
    "futur": "au futur simple",
}
TENSE_NAME = {"present": "present", "imparfait": "imparfait", "futur": "futur simple"}

# --- Conjugaison -----------------------------------------------------------

#: Terminaisons regulieres par groupe et par temps.
ENDINGS = {
    ("er", "present"): ["e", "es", "e", "ons", "ez", "ent"],
    ("ir", "present"): ["is", "is", "it", "issons", "issez", "issent"],
    ("er", "imparfait"): ["ais", "ais", "ait", "ions", "iez", "aient"],
    ("ir", "imparfait"): ["issais", "issais", "issait", "issions", "issiez", "issaient"],
    ("er", "futur"): ["erai", "eras", "era", "erons", "erez", "eront"],
    ("ir", "futur"): ["irai", "iras", "ira", "irons", "irez", "iront"],
}

REGULAR_ER = ["chanter", "danser", "marcher", "regarder", "jouer", "parler", "travailler", "aimer"]
REGULAR_IR = ["finir", "grandir", "choisir", "reussir", "obeir", "remplir"]

#: Verbes irreguliers frequents : formes ecrites explicitement.
IRREGULAR: dict[str, dict[str, list[str]]] = {
    "etre": {
        "present": ["suis", "es", "est", "sommes", "etes", "sont"],
        "imparfait": ["etais", "etais", "etait", "etions", "etiez", "etaient"],
        "futur": ["serai", "seras", "sera", "serons", "serez", "seront"],
    },
    "avoir": {
        "present": ["ai", "as", "a", "avons", "avez", "ont"],
        "imparfait": ["avais", "avais", "avait", "avions", "aviez", "avaient"],
        "futur": ["aurai", "auras", "aura", "aurons", "aurez", "auront"],
    },
    "aller": {
        "present": ["vais", "vas", "va", "allons", "allez", "vont"],
        "imparfait": ["allais", "allais", "allait", "allions", "alliez", "allaient"],
        "futur": ["irai", "iras", "ira", "irons", "irez", "iront"],
    },
    "faire": {
        "present": ["fais", "fais", "fait", "faisons", "faites", "font"],
        "imparfait": ["faisais", "faisais", "faisait", "faisions", "faisiez", "faisaient"],
        "futur": ["ferai", "feras", "fera", "ferons", "ferez", "feront"],
    },
    "pouvoir": {
        "present": ["peux", "peux", "peut", "pouvons", "pouvez", "peuvent"],
        "imparfait": ["pouvais", "pouvais", "pouvait", "pouvions", "pouviez", "pouvaient"],
        "futur": ["pourrai", "pourras", "pourra", "pourrons", "pourrez", "pourront"],
    },
    "venir": {
        "present": ["viens", "viens", "vient", "venons", "venez", "viennent"],
        "imparfait": ["venais", "venais", "venait", "venions", "veniez", "venaient"],
        "futur": ["viendrai", "viendras", "viendra", "viendrons", "viendrez", "viendront"],
    },
    "prendre": {
        "present": ["prends", "prends", "prend", "prenons", "prenez", "prennent"],
        "imparfait": ["prenais", "prenais", "prenait", "prenions", "preniez", "prenaient"],
        "futur": ["prendrai", "prendras", "prendra", "prendrons", "prendrez", "prendront"],
    },
    "voir": {
        "present": ["vois", "vois", "voit", "voyons", "voyez", "voient"],
        "imparfait": ["voyais", "voyais", "voyait", "voyions", "voyiez", "voyaient"],
        "futur": ["verrai", "verras", "verra", "verrons", "verrez", "verront"],
    },
}


def conjugate(verb: str, tense: str, person: int) -> str | None:
    """Forme conjuguee, ou None si le verbe n'est pas gere."""
    if verb in IRREGULAR:
        return IRREGULAR[verb].get(tense, [None] * 6)[person]
    if verb.endswith("er"):
        stem = verb[:-2] if tense != "futur" else verb[:-2]
        return stem + ENDINGS[("er", tense)][person]
    if verb.endswith("ir"):
        stem = verb[:-2]
        return stem + ENDINGS[("ir", tense)][person]
    return None


def _wrong_forms(verb: str, tense: str, person: int, rng: Random) -> list[str]:
    """Distracteurs credibles : autre personne, autre temps, terminaison voisine."""
    wrong: list[str] = []
    for other in range(6):
        if other != person:
            form = conjugate(verb, tense, other)
            if form:
                wrong.append(form)
    for other_tense in ("present", "imparfait", "futur"):
        if other_tense != tense:
            form = conjugate(verb, other_tense, person)
            if form:
                wrong.append(form)
    correct = conjugate(verb, tense, person)
    unique = [w for w in dict.fromkeys(wrong) if w != correct]
    rng.shuffle(unique)
    return unique[:3]


def conjugaison(rng: Random, level: int, country: Any) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    tenses = ["present"] if level <= 2 else ["present", "imparfait", "futur"]
    verbs = REGULAR_ER + (REGULAR_IR if level >= 3 else []) + list(IRREGULAR)

    for _ in range(6):
        verb = rng.choice(verbs)
        tense = rng.choice(tenses)
        person = rng.randrange(6)
        correct = conjugate(verb, tense, person)
        if not correct:
            continue
        distractors = _wrong_forms(verb, tense, person, rng)
        if len(distractors) < 3:
            continue
        options = [correct, *distractors]
        items.append(
            mcq(
                f'Conjugue le verbe "{verb}" {TENSE_PHRASE[tense]} : '
                f"{PRONOUN_LABEL[PRONOUNS[person]]} ...",
                options,
                0,
                difficulty=2 if verb not in IRREGULAR else 3,
                explanation=(
                    f"{TENSE_PHRASE[tense].capitalize()}, {PRONOUN_LABEL[PRONOUNS[person]]} {correct}."
                    + (
                        " C'est un verbe irregulier a connaitre par coeur."
                        if verb in IRREGULAR
                        else ""
                    )
                ),
                tags=["conjugaison", tense, "irregulier" if verb in IRREGULAR else "regulier"],
                shuffle=rng,
            )
        )

    for _ in range(4):
        verb = rng.choice(verbs)
        tense = rng.choice(tenses)
        person = rng.randrange(6)
        correct = conjugate(verb, tense, person)
        if not correct:
            continue
        items.append(
            short_text(
                f'Ecris le verbe "{verb}" conjugue {TENSE_PHRASE[tense]} avec '
                f'"{PRONOUN_LABEL[PRONOUNS[person]]}".',
                [correct],
                difficulty=3 if verb in IRREGULAR else 2,
                explanation=f"{PRONOUN_LABEL[PRONOUNS[person]]} {correct}.",
                tags=["conjugaison", tense, "production"],
                max_distance=0,
            )
        )

    verb = rng.choice(list(IRREGULAR))
    tense = rng.choice(["present", "imparfait", "futur"])
    items.append(
        matching(
            f'Relie chaque pronom a la forme correcte du verbe "{verb}" {TENSE_PHRASE[tense]}.',
            {PRONOUN_LABEL[PRONOUNS[i]]: IRREGULAR[verb][tense][i] for i in (0, 2, 3, 5)},
            difficulty=4,
            explanation=f'Conjugaison de "{verb}" {TENSE_PHRASE[tense]}.',
            tags=["conjugaison", tense, "association"],
            shuffle=rng,
        )
    )
    return items


# --- Grammaire -------------------------------------------------------------

NATURES = [
    ("chat", "nom"),
    ("courir", "verbe"),
    ("rapide", "adjectif"),
    ("le", "determinant"),
    ("elle", "pronom"),
    ("doucement", "adverbe"),
    ("maison", "nom"),
    ("bleu", "adjectif"),
    ("nous", "pronom"),
    ("manger", "verbe"),
    ("une", "determinant"),
    ("tres", "adverbe"),
]


def grammaire(rng: Random, level: int, country: Any) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    natures = ["nom", "verbe", "adjectif", "determinant", "pronom", "adverbe"]

    sample = rng.sample(NATURES, min(5, len(NATURES)))
    for word, nature in sample:
        options = [nature] + rng.sample([n for n in natures if n != nature], 3)
        items.append(
            mcq(
                f'Quelle est la nature du mot "{word}" ?',
                options,
                0,
                difficulty=2 if level <= 3 else 3,
                explanation=f'"{word}" est un {nature}.',
                tags=["grammaire", "nature_des_mots"],
                shuffle=rng,
            )
        )

    subjects = [
        ("Les enfants", "jouent", "jouent", "joue"),
        ("Le chien", "aboie", "aboie", "aboient"),
        ("Mes soeurs", "chantent", "chantent", "chante"),
        ("Ma cousine", "arrive", "arrive", "arrivent"),
        ("Les eleves", "ecoutent", "ecoutent", "ecoute"),
    ]
    for subject, _, correct, wrong in rng.sample(subjects, 3):
        items.append(
            mcq(
                f'Choisis la forme correcte : "{subject} ... dans la cour."',
                [correct, wrong],
                0,
                difficulty=3,
                explanation=(
                    f'Le verbe s\'accorde avec son sujet "{subject}" : on ecrit "{correct}".'
                ),
                tags=["grammaire", "accord_sujet_verbe"],
                shuffle=rng,
            )
        )

    items.append(
        mcq(
            'Dans la phrase "Le petit chat noir dort sur le tapis", quel est le sujet ?',
            ["Le petit chat noir", "dort", "sur le tapis", "le tapis"],
            0,
            difficulty=3,
            explanation='On pose la question "Qui est-ce qui dort ?" : le petit chat noir.',
            tags=["grammaire", "fonction", "sujet"],
            shuffle=rng,
        )
    )
    items.append(
        true_false(
            "Dans une phrase, le verbe s'accorde toujours avec le complement.",
            False,
            difficulty=3,
            explanation="Le verbe s'accorde avec le SUJET, pas avec le complement.",
            tags=["grammaire", "accord"],
        )
    )

    if level >= 4:
        items.append(
            mcq(
                'Dans "Nous avons visite un musee magnifique", quelle est la fonction '
                'de "un musee magnifique" ?',
                ["complement d'objet direct", "sujet", "complement circonstanciel", "attribut"],
                0,
                difficulty=4,
                explanation="On visite quoi ? Un musee magnifique : c'est le COD.",
                tags=["grammaire", "fonction", "cod"],
                shuffle=rng,
            )
        )
    return items


# --- Orthographe -----------------------------------------------------------

HOMOPHONES = [
    ("a", "a", "Il ... mange une pomme.", "a", 'Le verbe avoir : on peut dire "il avait".'),
    ("a", "a", "Nous allons ... la plage.", "a", 'Preposition : on ne peut pas dire "avait".'),
    (
        "et",
        "est",
        "Papa ... maman sont partis.",
        "et",
        '"et" relie deux mots : on peut dire "et puis".',
    ),
    ("et", "est", "Le ciel ... bleu.", "est", 'Verbe etre : on peut dire "etait".'),
    (
        "son",
        "sont",
        "Les enfants ... contents.",
        "sont",
        'Verbe etre au pluriel : on peut dire "etaient".',
    ),
    (
        "son",
        "sont",
        "Il a perdu ... cahier.",
        "son",
        'Determinant possessif : on peut dire "le sien".',
    ),
    (
        "ou",
        "ou",
        "Tu prefres le the ... le cafe ?",
        "ou",
        '"ou" de choix : on peut dire "ou bien".',
    ),
    ("ou", "ou", "Je ne sais pas ... il est parti.", "ou", '"ou" de lieu.'),
    (
        "ces",
        "ses",
        "Range ... affaires, elles sont a toi.",
        "ses",
        "Possessif : ce sont les siennes.",
    ),
    ("ces", "ses", "Regarde ... nuages !", "ces", 'Demonstratif : on peut dire "ces ...-la".'),
]


def orthographe(rng: Random, level: int, country: Any) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []

    for option_a, option_b, sentence, correct, why in rng.sample(
        HOMOPHONES, min(6, len(HOMOPHONES))
    ):
        options = [option_a, option_b]
        items.append(
            mcq(
                f'Complete correctement : "{sentence}"',
                options,
                options.index(correct),
                difficulty=3,
                explanation=why,
                tags=["orthographe", "homophones"],
                shuffle=rng,
            )
        )

    plurals = [
        ("cheval", "chevaux"),
        ("journal", "journaux"),
        ("bijou", "bijoux"),
        ("hibou", "hiboux"),
        ("travail", "travaux"),
        ("gateau", "gateaux"),
    ]
    for singular, plural in rng.sample(plurals, 3):
        items.append(
            short_text(
                f'Ecris le pluriel du mot "{singular}".',
                [plural],
                difficulty=3,
                explanation=f'Le pluriel de "{singular}" est "{plural}".',
                tags=["orthographe", "pluriel"],
                max_distance=0,
            )
        )

    items.append(
        fill_blank(
            'Complete : "Les fleurs que j\'... achetees ... tres belles." '
            "(1er trou : ai/est, 2e trou : sont/son)",
            [["ai"], ["sont"]],
            difficulty=4,
            explanation='"j\'ai" (verbe avoir) et "sont" (verbe etre au pluriel).',
            tags=["orthographe", "homophones", "texte_a_trous"],
        )
    )
    return items


# --- Vocabulaire -----------------------------------------------------------

SYNONYMS = [
    ("content", "joyeux", ["triste", "fatigue", "lent"]),
    ("rapide", "vite", ["lourd", "sombre", "doux"]),
    ("maison", "habitation", ["voiture", "jardin", "route"]),
    ("commencer", "debuter", ["finir", "arreter", "perdre"]),
    ("difficile", "ardu", ["facile", "simple", "clair"]),
]
ANTONYMS = [
    ("grand", "petit", ["enorme", "haut", "large"]),
    ("chaud", "froid", ["tiede", "brulant", "doux"]),
    ("jour", "nuit", ["matin", "midi", "heure"]),
    ("monter", "descendre", ["grimper", "sauter", "avancer"]),
    ("riche", "pauvre", ["cher", "genereux", "grand"]),
]


def vocabulaire(rng: Random, level: int, country: Any) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []

    for word, synonym, wrong in rng.sample(SYNONYMS, min(4, len(SYNONYMS))):
        items.append(
            mcq(
                f'Quel mot est un synonyme de "{word}" ?',
                [synonym, *wrong],
                0,
                difficulty=2,
                explanation=f'"{synonym}" a le meme sens que "{word}".',
                tags=["vocabulaire", "synonymes"],
                shuffle=rng,
            )
        )

    for word, antonym, wrong in rng.sample(ANTONYMS, min(4, len(ANTONYMS))):
        items.append(
            mcq(
                f'Quel est le contraire de "{word}" ?',
                [antonym, *wrong],
                0,
                difficulty=2,
                explanation=f'Le contraire de "{word}" est "{antonym}".',
                tags=["vocabulaire", "contraires"],
                shuffle=rng,
            )
        )

    families = [
        ("dent", ["dentiste", "dentaire", "dentition"], "dentelle"),
        ("terre", ["terrain", "terrasse", "atterrir"], "terrible"),
        ("chant", ["chanteur", "chanson", "chantonner"], "chantier"),
    ]
    root, family, intrus = rng.choice(families)
    items.append(
        mcq(
            f'Quel mot n\'appartient PAS a la famille du mot "{root}" ?',
            [*family, intrus],
            3,
            difficulty=4,
            explanation=f"\"{intrus}\" ressemble mais n'a pas le meme sens d'origine.",
            tags=["vocabulaire", "familles_de_mots"],
            shuffle=rng,
        )
    )

    items.append(
        mcq(
            'Dans la phrase "Il a le coeur lourd", l\'expression est employee :',
            ["au sens figure", "au sens propre"],
            0,
            difficulty=4,
            explanation="Le coeur n'est pas vraiment lourd : c'est une image, un sens figure.",
            tags=["vocabulaire", "sens_propre_figure"],
            shuffle=rng,
        )
    )
    return items


# --- Comprehension de texte ------------------------------------------------


def comprehension(rng: Random, level: int, country: Any) -> list[dict[str, Any]]:
    name = rng.choice(country.given_names)
    place = rng.choice(country.places)
    text = (
        f"Ce matin, {name} s'est leve tot. La pluie tombait depuis la veille sur "
        f"{place}, et la cour de l'ecole etait pleine de flaques. {name} a pris "
        "son parapluie bleu, puis il a retrouve son amie Sara devant le portail. "
        "Ensemble, ils ont saute par-dessus les flaques en riant, si bien qu'ils "
        "sont arrives en classe avec les chaussures trempees. La maitresse a souri "
        "et leur a demande de se secher les pieds avant de s'asseoir."
    )
    instructions = f"Lis le texte, puis reponds.\n\n{text}"

    return [
        mcq(
            "Quel temps fait-il dans le texte ?",
            ["Il pleut", "Il neige", "Il fait tres chaud", "Il y a du vent"],
            0,
            difficulty=2,
            explanation='Le texte dit : "La pluie tombait depuis la veille".',
            tags=["comprehension", "information_explicite"],
            shuffle=rng,
            instructions=instructions,
        ),
        mcq(
            "Pourquoi leurs chaussures sont-elles trempees ?",
            [
                "Parce qu'ils ont saute dans les flaques",
                "Parce qu'ils ont oublie leur parapluie",
                "Parce qu'ils sont tombes dans une riviere",
                "Parce qu'il a neige",
            ],
            0,
            difficulty=3,
            explanation="C'est une deduction : ils ont saute par-dessus les flaques.",
            tags=["comprehension", "inference"],
            shuffle=rng,
            instructions=instructions,
        ),
        short_text(
            "Comment s'appelle l'amie rencontree devant le portail ?",
            ["Sara"],
            difficulty=2,
            explanation='Le texte precise : "il a retrouve son amie Sara".',
            tags=["comprehension", "prelevement"],
            max_distance=1,
            instructions=instructions,
        ),
        true_false(
            "La maitresse s'est mise en colere.",
            False,
            difficulty=3,
            explanation="Non : le texte dit qu'elle a souri.",
            tags=["comprehension", "interpretation"],
        ),
        mcq(
            "Quel titre conviendrait le mieux a ce texte ?",
            [
                "Une matinee sous la pluie",
                "Les vacances a la mer",
                "La recette du gateau",
                "Le match de football",
            ],
            0,
            difficulty=4,
            explanation="Le texte raconte une matinee pluvieuse sur le chemin de l'ecole.",
            tags=["comprehension", "titre"],
            shuffle=rng,
        ),
    ]
