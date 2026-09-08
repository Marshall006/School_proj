"""Sciences, histoire-geographie, anglais et education civique.

Ces matieres sont fortement dependantes du pays : les reperes historiques et
geographiques d'un eleve de Cotonou ne sont pas ceux d'un eleve de Lyon. Le
contenu commun (sciences, anglais) est mutualise ; le reste est declare par
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
            ["le coeur", "le poumon", "l'estomac", "le foie"],
            0,
            difficulty=2,
            explanation="Le coeur est un muscle qui pompe le sang dans tout le corps.",
            tags=["sciences", "corps_humain"],
            shuffle=rng,
        ),
        mcq(
            "Ou commence la digestion des aliments ?",
            ["dans la bouche", "dans l'estomac", "dans l'intestin", "dans le coeur"],
            0,
            difficulty=3,
            explanation="La digestion commence dans la bouche : les dents machent et la salive agit deja.",
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
                "C'est la photosynthese : grace a la lumiere, la plante transforme l'eau "
                "et le dioxyde de carbone en matiere organique."
            ),
            tags=["sciences", "vegetaux", "photosynthese"],
            shuffle=rng,
        ),
        true_false(
            "Les os du squelette servent uniquement a nous faire tenir debout.",
            False,
            difficulty=3,
            explanation="Ils protegent aussi des organes fragiles : le crane protege le cerveau.",
            tags=["sciences", "squelette"],
        ),
        ordering(
            "Remets dans l'ordre les etapes du trajet des aliments.",
            ["la bouche", "l'oesophage", "l'estomac", "l'intestin grele"],
            difficulty=4,
            explanation="Bouche, puis oesophage, puis estomac, puis intestin grele.",
            tags=["sciences", "digestion"],
            shuffle=rng,
        ),
        mcq(
            "Dans une chaine alimentaire, qui vient en premier ?",
            ["un vegetal", "un carnivore", "un decomposeur", "un herbivore"],
            0,
            difficulty=4,
            explanation="Une chaine alimentaire demarre toujours par un producteur : un vegetal.",
            tags=["sciences", "chaine_alimentaire"],
            shuffle=rng,
        ),
        matching(
            "Relie chaque animal a son regime alimentaire.",
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
                "Quel gaz les etres humains rejettent-ils en respirant ?",
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
            "A quelle temperature l'eau pure gele-t-elle (sous pression normale) ?",
            ["0 degre Celsius", "10 degres Celsius", "100 degres Celsius", "-100 degres Celsius"],
            0,
            difficulty=2,
            explanation="L'eau pure gele a 0 degre C et bout a 100 degres C.",
            tags=["sciences", "etats_matiere"],
            shuffle=rng,
        ),
        mcq(
            "Comment s'appelle le passage de l'etat liquide a l'etat gazeux ?",
            ["la vaporisation", "la fusion", "la solidification", "la condensation"],
            0,
            difficulty=4,
            explanation="Liquide vers gaz : vaporisation. Gaz vers liquide : condensation.",
            tags=["sciences", "changements_etat"],
            shuffle=rng,
        ),
        ordering(
            "Remets le cycle de l'eau dans l'ordre.",
            ["evaporation", "condensation", "precipitations", "ruissellement"],
            difficulty=4,
            explanation="L'eau s'evapore, forme des nuages, retombe en pluie, puis ruisselle.",
            tags=["sciences", "cycle_eau"],
            shuffle=rng,
        ),
        true_false(
            "Le soleil est une source d'energie renouvelable.",
            True,
            difficulty=2,
            explanation="Oui : l'energie solaire se renouvelle en permanence.",
            tags=["sciences", "energie"],
        ),
        mcq(
            "Lequel de ces materiaux conduit le mieux l'electricite ?",
            ["le cuivre", "le bois", "le plastique", "le verre"],
            0,
            difficulty=3,
            explanation="Les metaux, comme le cuivre, sont de bons conducteurs.",
            tags=["sciences", "electricite"],
            shuffle=rng,
        ),
        mcq(
            "Que devient l'eau d'une flaque apres une journee de soleil ?",
            [
                "elle s'evapore dans l'air",
                "elle disparait definitivement",
                "elle se transforme en sable",
                "elle gele",
            ],
            0,
            difficulty=2,
            explanation="La chaleur fait passer l'eau a l'etat de vapeur : c'est l'evaporation.",
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
            "q": "Quelle chaine de montagnes separe la France de l'Espagne ?",
            "a": "les Pyrenees",
            "d": ["les Alpes", "le Jura", "les Vosges"],
            "e": "Les Pyrenees forment la frontiere avec l'Espagne.",
        },
        {
            "q": "Quel ocean borde la France a l'ouest ?",
            "a": "l'ocean Atlantique",
            "d": ["l'ocean Pacifique", "l'ocean Indien", "la mer Rouge"],
            "e": "La facade ouest de la France donne sur l'Atlantique.",
        },
        {
            "q": "Combien la France metropolitaine compte-t-elle de regions ?",
            "a": "13",
            "d": ["8", "22", "36"],
            "e": "Depuis 2016, la France metropolitaine compte 13 regions.",
        },
    ],
    "BJ": [
        {
            "q": "Quelle est la capitale politique du Benin ?",
            "a": "Porto-Novo",
            "d": ["Cotonou", "Parakou", "Abomey"],
            "e": "Porto-Novo est la capitale ; Cotonou est la plus grande ville.",
        },
        {
            "q": "Quelle ville du Benin est le principal port et la capitale economique ?",
            "a": "Cotonou",
            "d": ["Porto-Novo", "Natitingou", "Bohicon"],
            "e": "Cotonou concentre le port et l'activite economique.",
        },
        {
            "q": "Quel pays ne borde PAS le Benin ?",
            "a": "le Ghana",
            "d": ["le Togo", "le Nigeria", "le Niger"],
            "e": "Le Benin est entoure du Togo, du Nigeria, du Niger et du Burkina Faso.",
        },
        {
            "q": "Quel massif se trouve au nord-ouest du Benin ?",
            "a": "l'Atacora",
            "d": ["le Fouta-Djalon", "l'Adamaoua", "le Hoggar"],
            "e": "La chaine de l'Atacora traverse le nord-ouest du pays.",
        },
        {
            "q": "Quel fleuve marque la frontiere nord du Benin ?",
            "a": "le Niger",
            "d": ["l'Oueme", "le Mono", "le Senegal"],
            "e": "Le fleuve Niger borde le Benin au nord.",
        },
    ],
    "CI": [
        {
            "q": "Quelle est la capitale politique de la Cote d'Ivoire ?",
            "a": "Yamoussoukro",
            "d": ["Abidjan", "Bouake", "San-Pedro"],
            "e": "Yamoussoukro est la capitale depuis 1983 ; Abidjan reste la capitale economique.",
        },
        {
            "q": "Quelle est la plus grande ville de Cote d'Ivoire ?",
            "a": "Abidjan",
            "d": ["Yamoussoukro", "Korhogo", "Daloa"],
            "e": "Abidjan est la metropole economique du pays.",
        },
        {
            "q": "Quel produit agricole a fait la richesse de la Cote d'Ivoire ?",
            "a": "le cacao",
            "d": ["le the", "le ble", "la vigne"],
            "e": "La Cote d'Ivoire est le premier producteur mondial de cacao.",
        },
        {
            "q": "Quel pays ne borde PAS la Cote d'Ivoire ?",
            "a": "le Benin",
            "d": ["le Ghana", "le Liberia", "le Mali"],
            "e": "Ses voisins sont le Ghana, le Liberia, la Guinee, le Mali et le Burkina Faso.",
        },
        {
            "q": "Quel ocean borde la Cote d'Ivoire ?",
            "a": "l'ocean Atlantique",
            "d": ["l'ocean Indien", "l'ocean Pacifique", "la mer Mediterranee"],
            "e": "Le golfe de Guinee ouvre sur l'ocean Atlantique.",
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
            "q": "Quelle ile au large de Dakar est un lieu de memoire de la traite ?",
            "a": "l'ile de Goree",
            "d": ["l'ile de Ngor", "l'ile de Fadiouth", "l'ile de Carabane"],
            "e": "Goree est inscrite au patrimoine mondial de l'UNESCO.",
        },
        {
            "q": "Quel fleuve marque la frontiere nord du Senegal ?",
            "a": "le fleuve Senegal",
            "d": ["la Casamance", "le Saloum", "le Niger"],
            "e": "Le fleuve Senegal separe le pays de la Mauritanie.",
        },
        {
            "q": "Quel ocean borde le Senegal a l'ouest ?",
            "a": "l'ocean Atlantique",
            "d": ["l'ocean Indien", "la mer Rouge", "l'ocean Arctique"],
            "e": "Le Senegal est le pays continental le plus a l'ouest de l'Afrique.",
        },
    ],
}

COUNTRY_HISTORY: dict[str, list[dict[str, Any]]] = {
    "FR": [
        {
            "q": "En quelle annee a eu lieu la prise de la Bastille ?",
            "a": "1789",
            "d": ["1515", "1848", "1914"],
            "e": "Le 14 juillet 1789 marque le debut de la Revolution francaise.",
        },
        {
            "q": "Quelle guerre s'est deroulee de 1914 a 1918 ?",
            "a": "la Premiere Guerre mondiale",
            "d": ["la Seconde Guerre mondiale", "la guerre de Cent Ans", "la guerre de 1870"],
            "e": "On l'appelle aussi la Grande Guerre.",
        },
        {
            "q": "Qui a fait voter les lois rendant l'ecole primaire gratuite et obligatoire ?",
            "a": "Jules Ferry",
            "d": ["Napoleon", "Louis XIV", "Charles de Gaulle"],
            "e": "Les lois Ferry datent de 1881 et 1882.",
        },
        {
            "q": "Quelle est la devise de la Republique francaise ?",
            "a": "Liberte, Egalite, Fraternite",
            "d": ["Un pour tous, tous pour un", "Travail, Famille, Patrie", "Unite et Progres"],
            "e": "Elle figure sur les batiments publics.",
        },
    ],
    "BJ": [
        {
            "q": "Quand le Benin a-t-il accede a l'independance ?",
            "a": "le 1er aout 1960",
            "d": ["le 7 aout 1960", "le 4 avril 1960", "le 14 juillet 1789"],
            "e": "Le Benin (alors Dahomey) devient independant le 1er aout 1960.",
        },
        {
            "q": "Quel puissant royaume avait sa capitale a Abomey ?",
            "a": "le royaume du Dahomey",
            "d": ["l'empire du Mali", "le royaume du Benin (Nigeria)", "l'empire songhai"],
            "e": "Le royaume du Dahomey a rayonne du 17e au 19e siecle.",
        },
        {
            "q": "Quel roi d'Abomey a resiste a la colonisation francaise ?",
            "a": "Behanzin",
            "d": ["Samory Toure", "Lat Dior", "Chaka"],
            "e": "Behanzin a combattu les troupes francaises entre 1890 et 1894.",
        },
        {
            "q": "Quelle ville cotiere est un haut lieu de memoire de la traite negriere ?",
            "a": "Ouidah",
            "d": ["Parakou", "Natitingou", "Djougou"],
            "e": "La Route des esclaves de Ouidah rappelle cette histoire.",
        },
        {
            "q": "Comment s'appelait le Benin avant 1975 ?",
            "a": "le Dahomey",
            "d": ["le Soudan francais", "la Haute-Volta", "l'Oubangui-Chari"],
            "e": "Le pays a pris le nom de Benin en 1975.",
        },
    ],
    "CI": [
        {
            "q": "Quand la Cote d'Ivoire a-t-elle accede a l'independance ?",
            "a": "le 7 aout 1960",
            "d": ["le 1er aout 1960", "le 4 avril 1960", "le 1er janvier 1960"],
            "e": "L'independance est proclamee le 7 aout 1960.",
        },
        {
            "q": "Qui a ete le premier president de la Cote d'Ivoire ?",
            "a": "Felix Houphouet-Boigny",
            "d": ["Leopold Sedar Senghor", "Kwame Nkrumah", "Modibo Keita"],
            "e": "Il a dirige le pays de 1960 a 1993.",
        },
        {
            "q": "En quelle annee Yamoussoukro devient-elle capitale politique ?",
            "a": "1983",
            "d": ["1960", "1975", "2000"],
            "e": "La capitale est transferee a Yamoussoukro en 1983.",
        },
        {
            "q": "Quel empire medieval a rayonne sur l'Afrique de l'Ouest ?",
            "a": "l'empire du Mali",
            "d": ["l'empire romain", "l'empire aztheque", "l'empire ottoman"],
            "e": "L'empire du Mali, avec Tombouctou, a rayonne du 13e au 15e siecle.",
        },
    ],
    "SN": [
        {
            "q": "Quand le Senegal a-t-il accede a l'independance ?",
            "a": "le 4 avril 1960",
            "d": ["le 1er aout 1960", "le 7 aout 1960", "le 14 juillet 1960"],
            "e": "Le 4 avril est la fete nationale senegalaise.",
        },
        {
            "q": "Qui a ete le premier president du Senegal, aussi poete ?",
            "a": "Leopold Sedar Senghor",
            "d": ["Felix Houphouet-Boigny", "Lat Dior", "Cheikh Anta Diop"],
            "e": "Senghor, poete et homme d'Etat, a dirige le pays de 1960 a 1980.",
        },
        {
            "q": "Quel damel du Cayor a resiste a la colonisation francaise ?",
            "a": "Lat Dior",
            "d": ["Behanzin", "Samory Toure", "Soundiata Keita"],
            "e": "Lat Dior Ngone Latyr Diop s'est oppose a la construction du chemin de fer.",
        },
        {
            "q": "Quel empire medieval avait Soundiata Keita pour fondateur ?",
            "a": "l'empire du Mali",
            "d": ["l'empire du Ghana", "l'empire songhai", "le royaume du Dahomey"],
            "e": "Soundiata Keita fonde l'empire du Mali au 13e siecle.",
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
                explanation=f"Oui, {voisins[0]} partage une frontiere avec {country.name}.",
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
                f"En quelle annee {country.name} est-il devenu independant ?",
                [country.independence.split()[-1]],
                difficulty=3,
                explanation=f"L'independance a ete proclamee le {country.independence}.",
                tags=["histoire", "independance"],
                max_distance=0,
            )
        )
    items.append(
        ordering(
            "Range ces periodes historiques de la plus ancienne a la plus recente.",
            ["la Prehistoire", "l'Antiquite", "le Moyen Age", "l'epoque contemporaine"],
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
    ("ecole", "school", ["house", "street", "garden"]),
    ("frere", "brother", ["sister", "mother", "uncle"]),
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
            'Complete : "She ... a student."',
            ["is", "are", "am", "be"],
            0,
            difficulty=3,
            explanation='Avec she/he/it, on utilise "is".',
            tags=["anglais", "grammaire", "verbe_etre"],
            shuffle=rng,
        )
    )
    items.append(
        matching(
            "Relie chaque mot anglais a sa traduction.",
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
                "regarder a gauche, a droite, puis encore a gauche",
                "courir le plus vite possible",
                "traverser en regardant son telephone",
                "fermer les yeux",
            ],
            0,
            difficulty=1,
            explanation="On regarde des deux cotes et on traverse sur le passage pieton.",
            tags=["civique", "securite"],
            shuffle=rng,
        ),
        true_false(
            "Chaque enfant a le droit d'aller a l'ecole.",
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
            "Que faire si on assiste a une moquerie repetee envers un camarade ?",
            [
                "en parler a un adulte de confiance",
                "faire comme si de rien n'etait",
                "rire avec les autres",
                "se moquer aussi",
            ],
            0,
            difficulty=2,
            explanation="Parler a un adulte permet d'arreter le harcelement.",
            tags=["civique", "vivre_ensemble"],
            shuffle=rng,
        ),
        true_false(
            "Le vote permet aux citoyens de choisir leurs representants.",
            True,
            difficulty=2,
            explanation="C'est le principe de la democratie representative.",
            tags=["civique", "democratie"],
        ),
    ]
