"""Sciences, histoire-géographie, anglais et éducation civique.

Ces matières sont fortement dependantes du pays : les repères historiques et
geographiques d'un élève de Cotonou ne sont pas ceux d'un élève de Lyon. Le
contenu commun (sciences, anglais) est mutualise ; le reste est déclaré par
pays dans `COUNTRY_HISTORY` et `COUNTRY_GEOGRAPHY`.
"""

from __future__ import annotations

from random import Random
from typing import Any

from app.content.common import matching, mcq, ordering, short_text, true_false

# ---------------------------------------------------------------------------
# Sciences (commun)
# ---------------------------------------------------------------------------


def sciences_vivant(rng: Random, level: int, country: Any) -> list[dict[str, Any]]:
    items = [
        mcq(
            "Quel organe permet de faire circuler le sang dans le corps ?",
            ["le cœur", "le poumon", "l'estomac", "le foie"],
            0,
            difficulty=2,
            explanation="Le cœur est un muscle qui pompe le sang dans tout le corps.",
            tags=["sciences", "corps_humain"],
            shuffle=rng,
        ),
        mcq(
            "Ou commence la digestion des aliments ?",
            ["dans la bouche", "dans l'estomac", "dans l'intestin", "dans le cœur"],
            0,
            difficulty=3,
            explanation="La digestion commence dans la bouche : les dents machent et la salive agit déjà.",
            tags=["sciences", "digestion"],
            shuffle=rng,
        ),
        mcq(
            "De quoi une plante verte a-t-elle besoin pour fabriquer sa nourriture ?",
            [
                "de lumiere, d'eau et de dioxyde de carbone",
                "de viande et d'eau",
                "de sable et de vent",
                "uniquement d'engrais",
            ],
            0,
            difficulty=4,
            explanation=(
                "C'est la photosynthèse : grace à la lumiere, la plante transforme l'eau "
                "et le dioxyde de carbone en matière organique."
            ),
            tags=["sciences", "vegetaux", "photosynthese"],
            shuffle=rng,
        ),
        true_false(
            "Les os du squelette servent uniquement à nous faire tenir debout.",
            False,
            difficulty=3,
            explanation="Ils protègent aussi des organes fragiles : le crane protège le cerveau.",
            tags=["sciences", "squelette"],
        ),
        ordering(
            "Remets dans l'ordre les etapes du trajet des aliments.",
            ["la bouche", "l'œsophage", "l'estomac", "l'intestin grêle"],
            difficulty=4,
            explanation="Bouche, puis œsophage, puis estomac, puis intestin grele.",
            tags=["sciences", "digestion"],
            shuffle=rng,
        ),
        mcq(
            "Dans une chaîne alimentaire, qui vient en premier ?",
            ["un végétal", "un carnivore", "un décomposeur", "un herbivore"],
            0,
            difficulty=4,
            explanation="Une chaîne alimentaire demarre toujours par un producteur : un végétal.",
            tags=["sciences", "chaine_alimentaire"],
            shuffle=rng,
        ),
        matching(
            "Relie chaque animal à son régime alimentaire.",
            {"la vache": "herbivore", "le lion": "carnivore", "le poulet": "omnivore"},
            difficulty=3,
            explanation="La vache mange de l'herbe, le lion de la viande, le poulet un peu de tout.",
            tags=["sciences", "regimes"],
            shuffle=rng,
        ),
    ]
    if level >= 5:
        items.append(
            mcq(
                "Quel gaz les êtres humains rejettent-ils en respirant ?",
                ["le dioxyde de carbone", "l'oxygene", "l'azote", "l'hydrogene"],
                0,
                difficulty=3,
                explanation="Nous inspirons de l'oxygene et rejetons du dioxyde de carbone.",
                tags=["sciences", "respiration"],
                shuffle=rng,
            )
        )
    return items


def sciences_matiere(rng: Random, level: int, country: Any) -> list[dict[str, Any]]:
    items = [
        mcq(
            "À quelle température l'eau pure gèle-t-elle (sous pression normale) ?",
            ["0 degré Celsius", "10 degrés Celsius", "100 degrés Celsius", "-100 degrés Celsius"],
            0,
            difficulty=2,
            explanation="L'eau pure gèle à 0 degré C et bout à 100 degrés C.",
            tags=["sciences", "etats_matiere"],
            shuffle=rng,
        ),
        mcq(
            "Comment s'appelle le passage de l'état liquide à l'état gazeux ?",
            ["la vaporisation", "la fusion", "la solidification", "la condensation"],
            0,
            difficulty=4,
            explanation="Liquide vers gaz : vaporisation. Gaz vers liquide : condensation.",
            tags=["sciences", "changements_etat"],
            shuffle=rng,
        ),
        ordering(
            "Remets le cycle de l'eau dans l'ordre.",
            ["évaporation", "condensation", "précipitations", "ruissellement"],
            difficulty=4,
            explanation="L'eau s'evapore, forme des nuages, retombe en pluie, puis ruisselle.",
            tags=["sciences", "cycle_eau"],
            shuffle=rng,
        ),
        true_false(
            "Le soleil est une source d'énergie renouvelable.",
            True,
            difficulty=2,
            explanation="Oui : l'énergie solaire se renouvelle en permanence.",
            tags=["sciences", "energie"],
        ),
        mcq(
            "Lequel de ces matériaux conduit le mieux l'électricité ?",
            ["le cuivre", "le bois", "le plastique", "le verre"],
            0,
            difficulty=3,
            explanation="Les metaux, comme le cuivre, sont de bons conducteurs.",
            tags=["sciences", "electricite"],
            shuffle=rng,
        ),
        mcq(
            "Que devient l'eau d'une flaque après une journee de soleil ?",
            [
                "elle s'evapore dans l'air",
                "elle disparait definitivement",
                "elle se transforme en sable",
                "elle gèle",
            ],
            0,
            difficulty=2,
            explanation="La chaleur fait passer l'eau à l'état de vapeur : c'est l'évaporation.",
            tags=["sciences", "evaporation"],
            shuffle=rng,
        ),
    ]
    return items


# ---------------------------------------------------------------------------
# Geographie et histoire : declarees par pays
# ---------------------------------------------------------------------------

COUNTRY_GEOGRAPHY: dict[str, list[dict[str, Any]]] = {
    "FR": [
        {
            "q": "Quelle est la capitale de la France ?",
            "a": "Paris",
            "d": ["Lyon", "Marseille", "Bordeaux"],
            "e": "Paris est la capitale de la France.",
        },
        {
            "q": "Quel est le plus long fleuve de France ?",
            "a": "la Loire",
            "d": ["la Seine", "le Rhone", "la Garonne"],
            "e": "La Loire mesure environ 1 000 km.",
        },
        {
            "q": "Quelle chaîne de montagnes separe la France de l'Espagne ?",
            "a": "les Pyrenees",
            "d": ["les Alpes", "le Jura", "les Vosges"],
            "e": "Les Pyrenees forment la frontière avec l'Espagne.",
        },
        {
            "q": "Quel océan borde la France à l'ouest ?",
            "a": "l'océan Atlantique",
            "d": ["l'océan Pacifique", "l'océan Indien", "la mer Rouge"],
            "e": "La facade ouest de la France donne sur l'Atlantique.",
        },
        {
            "q": "Combien la France metropolitaine compte-t-elle de régions ?",
            "a": "13",
            "d": ["8", "22", "36"],
            "e": "Depuis 2016, la France metropolitaine compte 13 régions.",
        },
    ],
    "BJ": [
        {
            "q": "Quelle est la capitale politique du Bénin ?",
            "a": "Porto-Novo",
            "d": ["Cotonou", "Parakou", "Abomey"],
            "e": "Porto-Novo est la capitale ; Cotonou est la plus grande ville.",
        },
        {
            "q": "Quelle ville du Bénin est le principal port et la capitale économique ?",
            "a": "Cotonou",
            "d": ["Porto-Novo", "Natitingou", "Bohicon"],
            "e": "Cotonou concentre le port et l'activité économique.",
        },
        {
            "q": "Quel pays ne borde PAS le Bénin ?",
            "a": "le Ghana",
            "d": ["le Togo", "le Nigeria", "le Niger"],
            "e": "Le Bénin est entoure du Togo, du Nigeria, du Niger et du Burkina Faso.",
        },
        {
            "q": "Quel massif se trouve au nord-ouest du Bénin ?",
            "a": "l'Atacora",
            "d": ["le Fouta-Djalon", "l'Adamaoua", "le Hoggar"],
            "e": "La chaîne de l'Atacora traverse le nord-ouest du pays.",
        },
        {
            "q": "Quel fleuve marque la frontière nord du Bénin ?",
            "a": "le Niger",
            "d": ["l'Oueme", "le Mono", "le Senegal"],
            "e": "Le fleuve Niger borde le Bénin au nord.",
        },
    ],
    "CI": [
        {
            "q": "Quelle est la capitale politique de la Cote d'Ivoire ?",
            "a": "Yamoussoukro",
            "d": ["Abidjan", "Bouake", "San-Pedro"],
            "e": "Yamoussoukro est la capitale depuis 1983 ; Abidjan reste la capitale économique.",
        },
        {
            "q": "Quelle est la plus grande ville de Cote d'Ivoire ?",
            "a": "Abidjan",
            "d": ["Yamoussoukro", "Korhogo", "Daloa"],
            "e": "Abidjan est la metropole économique du pays.",
        },
        {
            "q": "Quel produit agricole a fait la richesse de la Cote d'Ivoire ?",
            "a": "le cacao",
            "d": ["le the", "le ble", "la vigne"],
            "e": "La Cote d'Ivoire est le premier producteur mondial de cacao.",
        },
        {
            "q": "Quel pays ne borde PAS la Cote d'Ivoire ?",
            "a": "le Bénin",
            "d": ["le Ghana", "le Liberia", "le Mali"],
            "e": "Ses voisins sont le Ghana, le Liberia, la Guinee, le Mali et le Burkina Faso.",
        },
        {
            "q": "Quel océan borde la Cote d'Ivoire ?",
            "a": "l'océan Atlantique",
            "d": ["l'océan Indien", "l'océan Pacifique", "la mer Mediterranee"],
            "e": "Le golfe de Guinee ouvre sur l'océan Atlantique.",
        },
    ],
    "SN": [
        {
            "q": "Quelle est la capitale du Senegal ?",
            "a": "Dakar",
            "d": ["Thies", "Saint-Louis", "Kaolack"],
            "e": "Dakar est la capitale, situee sur la presqu'ile du Cap-Vert.",
        },
        {
            "q": "Quel pays est entierement entoure par le Senegal ?",
            "a": "la Gambie",
            "d": ["la Mauritanie", "le Mali", "la Guinee"],
            "e": "La Gambie forme une enclave le long de son fleuve.",
        },
        {
            "q": "Quelle ile au large de Dakar est un lieu de mémoire de la traite ?",
            "a": "l'ile de Goree",
            "d": ["l'ile de Ngor", "l'ile de Fadiouth", "l'ile de Carabane"],
            "e": "Goree est inscrite au patrimoine mondial de l'UNESCO.",
        },
        {
            "q": "Quel fleuve marque la frontière nord du Senegal ?",
            "a": "le fleuve Senegal",
            "d": ["la Casamance", "le Saloum", "le Niger"],
            "e": "Le fleuve Senegal separe le pays de la Mauritanie.",
        },
        {
            "q": "Quel océan borde le Senegal à l'ouest ?",
            "a": "l'océan Atlantique",
            "d": ["l'océan Indien", "la mer Rouge", "l'océan Arctique"],
            "e": "Le Senegal est le pays continental le plus à l'ouest de l'Afrique.",
        },
    ],
}

COUNTRY_HISTORY: dict[str, list[dict[str, Any]]] = {
    "FR": [
        {
            "q": "En quelle année a eu lieu la prise de la Bastille ?",
            "a": "1789",
            "d": ["1515", "1848", "1914"],
            "e": "Le 14 juillet 1789 marque le début de la Révolution française.",
        },
        {
            "q": "Quelle guerre s'est déroulée de 1914 à 1918 ?",
            "a": "la Première Guerre mondiale",
            "d": ["la Seconde Guerre mondiale", "la guerre de Cent Ans", "la guerre de 1870"],
            "e": "On l'appelle aussi la Grande Guerre.",
        },
        {
            "q": "Qui a fait voter les lois rendant l'école primaire gratuite et obligatoire ?",
            "a": "Jules Ferry",
            "d": ["Napoleon", "Louis XIV", "Charles de Gaulle"],
            "e": "Les lois Ferry datent de 1881 et 1882.",
        },
        {
            "q": "Quelle est la devise de la République française ?",
            "a": "Liberté, Égalité, Fraternité",
            "d": ["Un pour tous, tous pour un", "Travail, Famille, Patrie", "Unité et Progres"],
            "e": "Elle figure sur les batiments publics.",
        },
    ],
    "BJ": [
        {
            "q": "Quand le Bénin a-t-il accédé à l'indépendance ?",
            "a": "le 1er août 1960",
            "d": ["le 7 août 1960", "le 4 avril 1960", "le 14 juillet 1789"],
            "e": "Le Bénin (alors Dahomey) devient indépendant le 1er août 1960.",
        },
        {
            "q": "Quel puissant royaume avait sa capitale à Abomey ?",
            "a": "le royaume du Dahomey",
            "d": ["l'empire du Mali", "le royaume du Bénin (Nigeria)", "l'empire songhai"],
            "e": "Le royaume du Dahomey a rayonné du 17e au 19e siècle.",
        },
        {
            "q": "Quel roi d'Abomey a resiste à la colonisation française ?",
            "a": "Behanzin",
            "d": ["Samory Toure", "Lat Dior", "Chaka"],
            "e": "Behanzin a combattu les troupes françaises entre 1890 et 1894.",
        },
        {
            "q": "Quelle ville cotiere est un haut lieu de mémoire de la traite négrière ?",
            "a": "Ouidah",
            "d": ["Parakou", "Natitingou", "Djougou"],
            "e": "La Route des esclaves de Ouidah rappelle cette histoire.",
        },
        {
            "q": "Comment s'appelait le Bénin avant 1975 ?",
            "a": "le Dahomey",
            "d": ["le Soudan français", "la Haute-Volta", "l'Oubangui-Chari"],
            "e": "Le pays a pris le nom de Bénin en 1975.",
        },
    ],
    "CI": [
        {
            "q": "Quand la Cote d'Ivoire a-t-elle accédé à l'indépendance ?",
            "a": "le 7 août 1960",
            "d": ["le 1er août 1960", "le 4 avril 1960", "le 1er janvier 1960"],
            "e": "L'indépendance est proclamée le 7 août 1960.",
        },
        {
            "q": "Qui a été le premier président de la Cote d'Ivoire ?",
            "a": "Felix Houphouet-Boigny",
            "d": ["Leopold Sedar Senghor", "Kwame Nkrumah", "Modibo Keita"],
            "e": "Il a dirigé le pays de 1960 à 1993.",
        },
        {
            "q": "En quelle année Yamoussoukro devient-elle capitale politique ?",
            "a": "1983",
            "d": ["1960", "1975", "2000"],
            "e": "La capitale est transferee à Yamoussoukro en 1983.",
        },
        {
            "q": "Quel empire médiéval a rayonné sur l'Afrique de l'Ouest ?",
            "a": "l'empire du Mali",
            "d": ["l'empire romain", "l'empire aztheque", "l'empire ottoman"],
            "e": "L'empire du Mali, avec Tombouctou, a rayonné du 13e au 15e siècle.",
        },
    ],
    "SN": [
        {
            "q": "Quand le Senegal a-t-il accédé à l'indépendance ?",
            "a": "le 4 avril 1960",
            "d": ["le 1er août 1960", "le 7 août 1960", "le 14 juillet 1960"],
            "e": "Le 4 avril est la fete nationale senegalaise.",
        },
        {
            "q": "Qui a été le premier président du Senegal, aussi poete ?",
            "a": "Leopold Sedar Senghor",
            "d": ["Felix Houphouet-Boigny", "Lat Dior", "Cheikh Anta Diop"],
            "e": "Senghor, poete et homme d'État, a dirigé le pays de 1960 à 1980.",
        },
        {
            "q": "Quel damel du Cayor a résisté à la colonisation française ?",
            "a": "Lat Dior",
            "d": ["Behanzin", "Samory Toure", "Soundiata Keita"],
            "e": "Lat Dior Ngone Latyr Diop s'est opposé à la construction du chemin de fer.",
        },
        {
            "q": "Quel empire médiéval avait Soundiata Keita pour fondateur ?",
            "a": "l'empire du Mali",
            "d": ["l'empire du Ghana", "l'empire songhai", "le royaume du Dahomey"],
            "e": "Soundiata Keita fondé l'empire du Mali au 13e siècle.",
        },
    ],
}


def geographie(rng: Random, level: int, country: Any) -> list[dict[str, Any]]:
    entries = COUNTRY_GEOGRAPHY.get(country.code, [])
    items = [
        mcq(
            entry["q"],
            [entry["a"], *entry["d"]],
            0,
            difficulty=2 if index < 2 else 3,
            explanation=entry["e"],
            tags=["geographie", country.code.lower()],
            shuffle=rng,
        )
        for index, entry in enumerate(entries)
    ]
    items.append(
        short_text(
            f"Quelle est la capitale de {country.name} ?",
            [country.capital],
            difficulty=2,
            explanation=f"La capitale de {country.name} est {country.capital}.",
            tags=["geographie", "capitale"],
            max_distance=1,
        )
    )
    voisins = country.facts.get("voisins", [])
    if voisins:
        items.append(
            true_false(
                f"{voisins[0].capitalize()} est un pays voisin de {country.name}.",
                True,
                difficulty=2,
                explanation=f"Oui, {voisins[0]} partage une frontière avec {country.name}.",
                tags=["geographie", "frontieres"],
            )
        )
    return items


def histoire(rng: Random, level: int, country: Any) -> list[dict[str, Any]]:
    entries = COUNTRY_HISTORY.get(country.code, [])
    items = [
        mcq(
            entry["q"],
            [entry["a"], *entry["d"]],
            0,
            difficulty=3,
            explanation=entry["e"],
            tags=["histoire", country.code.lower()],
            shuffle=rng,
        )
        for entry in entries
    ]
    if country.independence:
        items.append(
            short_text(
                f"En quelle année {country.name} est-il devenu indépendant ?",
                [country.independence.split()[-1]],
                difficulty=3,
                explanation=f"L'indépendance a été proclamée le {country.independence}.",
                tags=["histoire", "indépendance"],
                max_distance=0,
            )
        )
    items.append(
        ordering(
            "Range ces périodes historiques de la plus ancienne à la plus recente.",
            ["la Préhistoire", "l'Antiquité", "le Moyen Âge", "l'époque contemporaine"],
            difficulty=3,
            explanation="Prehistoire, Antiquite, Moyen Age, puis epoque moderne et contemporaine.",
            tags=["histoire", "chronologie"],
            shuffle=rng,
        )
    )
    return items


# ---------------------------------------------------------------------------
# Anglais
# ---------------------------------------------------------------------------

EN_VOCAB = [
    ("rouge", "red", ["blue", "green", "yellow"]),
    ("bleu", "blue", ["red", "black", "white"]),
    ("chien", "dog", ["cat", "bird", "horse"]),
    ("livre", "book", ["pen", "table", "door"]),
    ("école", "school", ["house", "street", "garden"]),
    ("frère", "brother", ["sister", "mother", "uncle"]),
    ("lundi", "Monday", ["Sunday", "Friday", "Tuesday"]),
    ("sept", "seven", ["six", "eight", "nine"]),
]


def anglais_vocabulaire(rng: Random, level: int, country: Any) -> list[dict[str, Any]]:
    items = [
        mcq(
            f'Comment dit-on "{fr}" en anglais ?',
            [en, *wrong],
            0,
            difficulty=2,
            explanation=f'"{fr}" se dit "{en}".',
            tags=["anglais", "vocabulaire"],
            shuffle=rng,
        )
        for fr, en, wrong in rng.sample(EN_VOCAB, min(6, len(EN_VOCAB)))
    ]
    items.append(
        mcq(
            'Complète : "She ... a student."',
            ["is", "are", "am", "be"],
            0,
            difficulty=3,
            explanation='Avec she/he/it, on utilisé "is".',
            tags=["anglais", "grammaire", "verbe_etre"],
            shuffle=rng,
        )
    )
    items.append(
        matching(
            "Relie chaque mot anglais à sa traduction.",
            {"water": "eau", "friend": "ami", "night": "nuit"},
            difficulty=3,
            explanation="water = eau, friend = ami, night = nuit.",
            tags=["anglais", "vocabulaire"],
            shuffle=rng,
        )
    )
    return items


# ---------------------------------------------------------------------------
# Education civique
# ---------------------------------------------------------------------------


def civique(rng: Random, level: int, country: Any) -> list[dict[str, Any]]:
    return [
        mcq(
            "Que doit-on faire avant de traverser la route ?",
            [
                "regarder à gauche, à droite, puis encore à gauche",
                "courir le plus vite possible",
                "traverser en regardant son téléphone",
                "fermer les yeux",
            ],
            0,
            difficulty=1,
            explanation="On regarde des deux côtés et on traverse sur le passage piéton.",
            tags=["civique", "securite"],
            shuffle=rng,
        ),
        true_false(
            "Chaque enfant a le droit d'aller à l'école.",
            True,
            difficulty=1,
            explanation="C'est un droit reconnu par la Convention internationale des droits de l'enfant.",
            tags=["civique", "droits"],
        ),
        mcq(
            f"Quelle est la capitale de {country.name}, siege des institutions ?",
            [country.capital, *rng.sample(country.places, 3)],
            0,
            difficulty=2,
            explanation=f"{country.capital} est la capitale de {country.name}.",
            tags=["civique", "institutions"],
            shuffle=rng,
        ),
        mcq(
            "Que faire si on assiste à une moquerie répétée envers un camarade ?",
            [
                "en parler à un adulte de confiance",
                "faire comme si de rien n'était",
                "rire avec les autres",
                "se moquer aussi",
            ],
            0,
            difficulty=2,
            explanation="Parler à un adulte permet d'arreter le harcèlement.",
            tags=["civique", "vivre_ensemble"],
            shuffle=rng,
        ),
        true_false(
            "Le vote permet aux citoyens de choisir leurs représentants.",
            True,
            difficulty=2,
            explanation="C'est le principe de la démocratie representative.",
            tags=["civique", "democratie"],
        ),
    ]
