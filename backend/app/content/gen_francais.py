"""Generateurs de questions de français : conjugaison, grammaire, orthographe,
vocabulaire et compréhension de texte.

La conjugaison est produite par règles (avec les irregularites usuelles
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

#: "au présent" mais "à l'imparfait" : la preposition depend du temps.
TENSE_PHRASE = {
    "present": "au présent",
    "imparfait": "à l'imparfait",
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
REGULAR_IR = ["finir", "grandir", "choisir", "réussir", "obéir", "remplir"]

#: Verbes irreguliers frequents : formes ecrites explicitement.
IRREGULAR: dict[str, dict[str, list[str]]] = {
    "être": {
        "present": ["suis", "es", "est", "sommes", "êtes", "sont"],
        "imparfait": ["étais", "étais", "était", "étions", "étiez", "étaient"],
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


def with_pronoun(pronoun: str, form: str) -> str:
    """« je » s'elide devant une voyelle : on ecrit « j'aimais », pas « je aimais »."""
    if pronoun == "je" and form and form[0].lower() in "aeiouyéèêh":
        return f"j'{form}"
    return f"{pronoun} {form}"


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
                    f"{TENSE_PHRASE[tense].capitalize()}, {with_pronoun(PRONOUN_LABEL[PRONOUNS[person]], correct)}."
                    + (
                        " C'est un verbe irrégulier à connaître par cœur."
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
                f'Écris le verbe "{verb}" conjugue {TENSE_PHRASE[tense]} avec '
                f'"{PRONOUN_LABEL[PRONOUNS[person]]}".',
                [correct],
                difficulty=3 if verb in IRREGULAR else 2,
                explanation=f"{with_pronoun(PRONOUN_LABEL[PRONOUNS[person]], correct)}.",
                tags=["conjugaison", tense, "production"],
                max_distance=0,
            )
        )

    verb = rng.choice(list(IRREGULAR))
    tense = rng.choice(["present", "imparfait", "futur"])
    items.append(
        matching(
            f'Relie chaque pronom à la forme correcte du verbe "{verb}" {TENSE_PHRASE[tense]}.',
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
    ("le", "déterminant"),
    ("elle", "pronom"),
    ("doucement", "adverbe"),
    ("maison", "nom"),
    ("bleu", "adjectif"),
    ("nous", "pronom"),
    ("manger", "verbe"),
    ("une", "déterminant"),
    ("très", "adverbe"),
]


def grammaire(rng: Random, level: int, country: Any) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    natures = ["nom", "verbe", "adjectif", "déterminant", "pronom", "adverbe"]

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
        ("Mes sœurs", "chantent", "chantent", "chante"),
        ("Ma cousine", "arrive", "arrive", "arrivent"),
        ("Les élèves", "ecoutent", "ecoutent", "ecoute"),
    ]
    for subject, _, correct, wrong in rng.sample(subjects, 3):
        items.append(
            mcq(
                f'Choisis la forme correcte : "{subject} ... dans la cour."',
                [correct, wrong],
                0,
                difficulty=3,
                explanation=(
                    f'Le verbe s\'accordé avec son sujet "{subject}" : on écrit "{correct}".'
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
            "Dans une phrase, le verbe s'accordé toujours avec le complément.",
            False,
            difficulty=3,
            explanation="Le verbe s'accordé avec le Sujet, pas avec le complément.",
            tags=["grammaire", "accord"],
        )
    )

    if level >= 4:
        items.append(
            mcq(
                'Dans "Nous avons visite un musee magnifique", quelle est la fonction '
                'de "un musee magnifique" ?',
                ["complément d'objet direct", "sujet", "complément circonstanciel", "attribut"],
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
    ("et", "est", "Le ciel ... bleu.", "est", 'Verbe être : on peut dire "était".'),
    (
        "son",
        "sont",
        "Les enfants ... contents.",
        "sont",
        'Verbe être au pluriel : on peut dire "étaient".',
    ),
    (
        "son",
        "sont",
        "Il a perdu ... cahier.",
        "son",
        'Déterminant possessif : on peut dire "le sien".',
    ),
    (
        "ou",
        "ou",
        "Tu préfères le the ... le cafe ?",
        "ou",
        '"ou" de choix : on peut dire "ou bien".',
    ),
    ("ou", "ou", "Je ne sais pas ... il est parti.", "ou", '"ou" de lieu.'),
    (
        "ces",
        "ses",
        "Range ... affaires, elles sont à toi.",
        "ses",
        "Possessif : ce sont les siennes.",
    ),
    ("ces", "ses", "Regarde ... nuages !", "ces", 'Démonstratif : on peut dire "ces ...-la".'),
]


def orthographe(rng: Random, level: int, country: Any) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []

    for option_a, option_b, sentence, correct, why in rng.sample(
        HOMOPHONES, min(6, len(HOMOPHONES))
    ):
        options = [option_a, option_b]
        items.append(
            mcq(
                f'Complète correctement : "{sentence}"',
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
        ("gâteau", "gâteaux"),
    ]
    for singular, plural in rng.sample(plurals, 3):
        items.append(
            short_text(
                f'Écris le pluriel du mot "{singular}".',
                [plural],
                difficulty=3,
                explanation=f'Le pluriel de "{singular}" est "{plural}".',
                tags=["orthographe", "pluriel"],
                max_distance=0,
            )
        )

    items.append(
        fill_blank(
            'Complète : "Les fleurs que j\'... achetées ... très belles." '
            "(1er trou : ai/est, 2e trou : sont/son)",
            [["ai"], ["sont"]],
            difficulty=4,
            explanation='"j\'ai" (verbe avoir) et "sont" (verbe être au pluriel).',
            tags=["orthographe", "homophones", "texte_a_trous"],
        )
    )
    return items


# --- Vocabulaire -----------------------------------------------------------

SYNONYMS = [
    ("content", "joyeux", ["triste", "fatigué", "lent"]),
    ("rapide", "vite", ["lourd", "sombre", "doux"]),
    ("maison", "habitation", ["voiture", "jardin", "route"]),
    ("commencer", "débuter", ["finir", "arrêter", "perdre"]),
    ("difficile", "ardu", ["facile", "simple", "clair"]),
]
ANTONYMS = [
    ("grand", "petit", ["énorme", "haut", "large"]),
    ("chaud", "froid", ["tiède", "brûlant", "doux"]),
    ("jour", "nuit", ["matin", "midi", "heure"]),
    ("monter", "descendre", ["grimper", "sauter", "avancer"]),
    ("riche", "pauvre", ["cher", "généreux", "grand"]),
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
                explanation=f'"{synonym}" a le même sens que "{word}".',
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
            f'Quel mot n\'appartient PAS à la famille du mot "{root}" ?',
            [*family, intrus],
            3,
            difficulty=4,
            explanation=f"\"{intrus}\" ressemble mais n'a pas le même sens d'origine.",
            tags=["vocabulaire", "familles_de_mots"],
            shuffle=rng,
        )
    )

    items.append(
        mcq(
            'Dans la phrase "Il a le cœur lourd", l\'expression est employee :',
            ["au sens figure", "au sens propre"],
            0,
            difficulty=4,
            explanation="Le cœur n'est pas vraiment lourd : c'est une image, un sens figure.",
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
        f"Ce matin, {name} s'est levé tôt. La pluie tombait depuis la veille sur "
        f"{place}, et la cour de l'école était pleine de flaques. {name} a pris "
        "son parapluie bleu, puis il a retrouvé son amie Sara devant le portail. "
        "Ensemble, ils ont saute par-dessus les flaques en riant, si bien qu'ils "
        "sont arrives en classe avec les chaussures trempées. La maîtresse a souri "
        "et leur a demandé de se secher les pieds avant de s'asseoir."
    )
    instructions = f"Lis le texte, puis réponds.\n\n{text}"

    return [
        mcq(
            "Quel temps fait-il dans le texte ?",
            ["Il pleut", "Il neige", "Il fait très chaud", "Il y a du vent"],
            0,
            difficulty=2,
            explanation='Le texte dit : "La pluie tombait depuis la veille".',
            tags=["comprehension", "information_explicite"],
            shuffle=rng,
            instructions=instructions,
        ),
        mcq(
            "Pourquoi leurs chaussures sont-elles trempées ?",
            [
                "Parce qu'ils ont saute dans les flaques",
                "Parce qu'ils ont oublie leur parapluie",
                "Parce qu'ils sont tombes dans une riviere",
                "Parce qu'il a neigé",
            ],
            0,
            difficulty=3,
            explanation="C'est une déduction : ils ont saute par-dessus les flaques.",
            tags=["comprehension", "inference"],
            shuffle=rng,
            instructions=instructions,
        ),
        short_text(
            "Comment s'appelle l'amie rencontree devant le portail ?",
            ["Sara"],
            difficulty=2,
            explanation='Le texte précise : "il a retrouvé son amie Sara".',
            tags=["comprehension", "prelevement"],
            max_distance=1,
            instructions=instructions,
        ),
        true_false(
            "La maîtresse s'est mise en colere.",
            False,
            difficulty=3,
            explanation="Non : le texte dit qu'elle a souri.",
            tags=["comprehension", "interpretation"],
        ),
        mcq(
            "Quel titre conviendrait le mieux à ce texte ?",
            [
                "Une matinee sous la pluie",
                "Les vacances à la mer",
                "La recette du gateau",
                "Le match de football",
            ],
            0,
            difficulty=4,
            explanation="Le texte raconte une matinee pluvieuse sur le chemin de l'école.",
            tags=["comprehension", "titre"],
            shuffle=rng,
        ),
    ]
