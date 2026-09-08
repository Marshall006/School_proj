"""Catalogue pedagogique : pays, niveaux, matieres, notions.

Les systemes scolaires francophones ne se superposent pas exactement. En
France le primaire compte cinq annees (CP..CM2) ; au Benin, en Cote d'Ivoire ou
au Senegal il en compte six (CI, CP, CE1..CM2). On introduit donc un **indice
de niveau** commun : le programme est defini une fois par indice, puis
instancie pour chaque pays avec ses propres intitules de classe et son propre
contexte (monnaie, reperes historiques et geographiques, prenoms).

    indice   1    2    3    4    5    6     7    8    9    10
    FR       CP   CE1  CE2  CM1  CM2  6E    5E   4E   3E    -
    BJ/CI/SN CI   CP   CE1  CE2  CM1  CM2   6E   5E   4E   3E

Cette table d'equivalence est une approximation assumee : elle est isolee ici
pour qu'une equipe pedagogique puisse l'affiner sans toucher au code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Matieres
# ---------------------------------------------------------------------------

SUBJECTS: list[dict[str, Any]] = [
    {
        "code": "math",
        "name": "Mathematiques",
        "color": "#2563EB",
        "icon": "calculator",
        "position": 1,
    },
    {
        "code": "francais",
        "name": "Francais",
        "color": "#DC2626",
        "icon": "book-open",
        "position": 2,
    },
    {"code": "sciences", "name": "Sciences", "color": "#059669", "icon": "flask", "position": 3},
    {
        "code": "histoire_geo",
        "name": "Histoire-Geographie",
        "color": "#B45309",
        "icon": "globe",
        "position": 4,
    },
    {
        "code": "anglais",
        "name": "Anglais",
        "color": "#7C3AED",
        "icon": "message-circle",
        "position": 5,
    },
    {
        "code": "civique",
        "name": "Education civique",
        "color": "#0891B2",
        "icon": "users",
        "position": 6,
    },
]

# ---------------------------------------------------------------------------
# Pays et niveaux
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class GradeSpec:
    code: str
    name: str
    level: int  # indice commun
    cycle: str
    age: int


FR_GRADES = [
    GradeSpec("CP", "CP", 1, "primaire", 6),
    GradeSpec("CE1", "CE1", 2, "primaire", 7),
    GradeSpec("CE2", "CE2", 3, "primaire", 8),
    GradeSpec("CM1", "CM1", 4, "primaire", 9),
    GradeSpec("CM2", "CM2", 5, "primaire", 10),
    GradeSpec("6E", "6e", 6, "college", 11),
    GradeSpec("5E", "5e", 7, "college", 12),
    GradeSpec("4E", "4e", 8, "college", 13),
    GradeSpec("3E", "3e", 9, "college", 14),
]

AFRICA_GRADES = [
    GradeSpec("CI", "CI (Cours d'initiation)", 1, "primaire", 6),
    GradeSpec("CP", "CP (Cours preparatoire)", 2, "primaire", 7),
    GradeSpec("CE1", "CE1", 3, "primaire", 8),
    GradeSpec("CE2", "CE2", 4, "primaire", 9),
    GradeSpec("CM1", "CM1", 5, "primaire", 10),
    GradeSpec("CM2", "CM2", 6, "primaire", 11),
    GradeSpec("6E", "6e", 7, "college", 12),
    GradeSpec("5E", "5e", 8, "college", 13),
    GradeSpec("4E", "4e", 9, "college", 14),
    GradeSpec("3E", "3e", 10, "college", 15),
]


@dataclass(frozen=True, slots=True)
class CountrySpec:
    code: str
    name: str
    grades: list[GradeSpec]
    currency: str
    currency_name: str
    money_scale: int  # facteur applique aux prix des enonces
    capital: str
    given_names: list[str]
    places: list[str]
    independence: str | None = None
    facts: dict[str, Any] = field(default_factory=dict)


COUNTRIES: list[CountrySpec] = [
    CountrySpec(
        code="FR",
        name="France",
        grades=FR_GRADES,
        currency="EUR",
        currency_name="euro",
        money_scale=1,
        capital="Paris",
        given_names=["Lea", "Hugo", "Jade", "Louis", "Emma", "Nathan", "Chloe", "Adam"],
        places=["Lyon", "Marseille", "Lille", "Bordeaux", "Nantes", "Strasbourg"],
        facts={
            "fleuves": ["la Loire", "la Seine", "le Rhone", "la Garonne"],
            "montagnes": ["les Alpes", "les Pyrenees", "le Massif central"],
            "voisins": ["la Belgique", "l'Espagne", "l'Italie", "l'Allemagne", "la Suisse"],
        },
    ),
    CountrySpec(
        code="BJ",
        name="Benin",
        grades=AFRICA_GRADES,
        currency="XOF",
        currency_name="franc CFA",
        money_scale=100,
        capital="Porto-Novo",
        given_names=["Afiavi", "Kossi", "Adjoa", "Sena", "Mawuli", "Ayo", "Dossa", "Nadia"],
        places=["Cotonou", "Parakou", "Abomey", "Natitingou", "Ouidah", "Bohicon"],
        independence="1er aout 1960",
        facts={
            "fleuves": ["le Niger", "l'Oueme", "le Mono"],
            "regions": ["l'Atlantique", "le Borgou", "l'Atacora", "le Zou"],
            "voisins": ["le Niger", "le Nigeria", "le Togo", "le Burkina Faso"],
        },
    ),
    CountrySpec(
        code="CI",
        name="Cote d'Ivoire",
        grades=AFRICA_GRADES,
        currency="XOF",
        currency_name="franc CFA",
        money_scale=100,
        capital="Yamoussoukro",
        given_names=["Aya", "Konan", "Adjoua", "Yao", "Affoue", "Kouame", "Akissi", "Bakary"],
        places=["Abidjan", "Bouake", "Korhogo", "San-Pedro", "Man", "Daloa"],
        independence="7 aout 1960",
        facts={
            "fleuves": ["le Bandama", "la Comoe", "le Sassandra"],
            "voisins": ["le Ghana", "le Liberia", "la Guinee", "le Mali", "le Burkina Faso"],
        },
    ),
    CountrySpec(
        code="SN",
        name="Senegal",
        grades=AFRICA_GRADES,
        currency="XOF",
        currency_name="franc CFA",
        money_scale=100,
        capital="Dakar",
        given_names=["Awa", "Moussa", "Fatou", "Ibrahima", "Aminata", "Cheikh", "Ndeye", "Omar"],
        places=["Thies", "Saint-Louis", "Ziguinchor", "Kaolack", "Touba", "Rufisque"],
        independence="4 avril 1960",
        facts={
            "fleuves": ["le fleuve Senegal", "la Casamance", "le Saloum"],
            "voisins": ["la Mauritanie", "le Mali", "la Guinee", "la Gambie"],
        },
    ),
]

COUNTRY_BY_CODE = {c.code: c for c in COUNTRIES}


def grade_for(country_code: str, grade_code: str) -> GradeSpec | None:
    country = COUNTRY_BY_CODE.get(country_code)
    if not country:
        return None
    return next((g for g in country.grades if g.code == grade_code), None)


def grades_at_level(country_code: str, level: int) -> list[GradeSpec]:
    country = COUNTRY_BY_CODE.get(country_code)
    return [g for g in country.grades if g.level == level] if country else []


# ---------------------------------------------------------------------------
# Notions du programme, par indice de niveau
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class TopicSpec:
    code: str
    subject: str
    name: str
    description: str
    generator: str  # nom de la fabrique dans app.content.generators
    levels: tuple[int, ...]
    position: int = 0
    is_core: bool = True


#: Programme commun. `levels` dit a quels indices la notion est enseignee.
TOPICS: list[TopicSpec] = [
    # --- Mathematiques ----------------------------------------------------
    TopicSpec(
        "math.numeration",
        "math",
        "Numeration et nombres entiers",
        "Lire, ecrire, comparer et decomposer les nombres entiers.",
        "numeration",
        (1, 2, 3, 4, 5, 6),
        10,
    ),
    TopicSpec(
        "math.addition",
        "math",
        "Addition et soustraction",
        "Calcul pose et calcul mental, avec et sans retenue.",
        "addition_soustraction",
        (1, 2, 3, 4, 5),
        20,
    ),
    TopicSpec(
        "math.multiplication",
        "math",
        "Multiplication",
        "Tables, multiplication posee, multiples.",
        "multiplication",
        (2, 3, 4, 5, 6),
        30,
    ),
    TopicSpec(
        "math.division",
        "math",
        "Division",
        "Division euclidienne : quotient et reste, division posee.",
        "division",
        (3, 4, 5, 6),
        40,
    ),
    TopicSpec(
        "math.fractions",
        "math",
        "Fractions",
        "Lire, comparer, simplifier et additionner des fractions.",
        "fractions",
        (4, 5, 6, 7),
        50,
    ),
    TopicSpec(
        "math.decimaux",
        "math",
        "Nombres decimaux",
        "Ecriture decimale, comparaison, operations.",
        "decimaux",
        (4, 5, 6, 7),
        60,
    ),
    TopicSpec(
        "math.mesures",
        "math",
        "Grandeurs et mesures",
        "Longueurs, masses, contenances, durees et conversions.",
        "mesures",
        (2, 3, 4, 5, 6),
        70,
    ),
    TopicSpec(
        "math.geometrie",
        "math",
        "Geometrie",
        "Figures, perimetres, aires, angles.",
        "geometrie",
        (3, 4, 5, 6, 7),
        80,
    ),
    TopicSpec(
        "math.problemes",
        "math",
        "Resolution de problemes",
        "Problemes du quotidien a une ou plusieurs etapes.",
        "problemes",
        (2, 3, 4, 5, 6, 7),
        90,
    ),
    TopicSpec(
        "math.proportionnalite",
        "math",
        "Proportionnalite et pourcentages",
        "Situations proportionnelles, pourcentages, echelles.",
        "proportionnalite",
        (5, 6, 7, 8),
        100,
    ),
    # --- Francais ---------------------------------------------------------
    TopicSpec(
        "fr.conjugaison",
        "francais",
        "Conjugaison",
        "Present, imparfait, futur, passe compose.",
        "conjugaison",
        (2, 3, 4, 5, 6, 7),
        10,
    ),
    TopicSpec(
        "fr.grammaire",
        "francais",
        "Grammaire",
        "Nature et fonction des mots, accords.",
        "grammaire",
        (2, 3, 4, 5, 6, 7),
        20,
    ),
    TopicSpec(
        "fr.orthographe",
        "francais",
        "Orthographe",
        "Homophones grammaticaux et regles d'accord.",
        "orthographe",
        (2, 3, 4, 5, 6, 7),
        30,
    ),
    TopicSpec(
        "fr.vocabulaire",
        "francais",
        "Vocabulaire",
        "Synonymes, contraires, familles de mots, sens propre et figure.",
        "vocabulaire",
        (2, 3, 4, 5, 6, 7),
        40,
    ),
    TopicSpec(
        "fr.comprehension",
        "francais",
        "Comprehension de texte",
        "Lire un court texte et repondre a des questions.",
        "comprehension",
        (3, 4, 5, 6, 7),
        50,
    ),
    # --- Sciences ---------------------------------------------------------
    TopicSpec(
        "sc.vivant",
        "sciences",
        "Le vivant",
        "Corps humain, animaux, vegetaux, alimentation.",
        "sciences_vivant",
        (2, 3, 4, 5, 6, 7),
        10,
    ),
    TopicSpec(
        "sc.matiere",
        "sciences",
        "Matiere et energie",
        "Etats de la matiere, energie, environnement.",
        "sciences_matiere",
        (3, 4, 5, 6, 7),
        20,
    ),
    # --- Histoire-Geographie ---------------------------------------------
    TopicSpec(
        "hg.geographie",
        "histoire_geo",
        "Geographie",
        "Reperes du pays et du monde.",
        "geographie",
        (3, 4, 5, 6, 7),
        10,
    ),
    TopicSpec(
        "hg.histoire",
        "histoire_geo",
        "Histoire",
        "Grands reperes historiques.",
        "histoire",
        (4, 5, 6, 7),
        20,
    ),
    # --- Anglais ----------------------------------------------------------
    TopicSpec(
        "en.vocabulaire",
        "anglais",
        "Vocabulaire anglais",
        "Mots du quotidien, couleurs, nombres, famille.",
        "anglais_vocabulaire",
        (4, 5, 6, 7),
        10,
        is_core=False,
    ),
    # --- Education civique ------------------------------------------------
    TopicSpec(
        "civ.regles",
        "civique",
        "Vivre ensemble",
        "Regles de vie, citoyennete, securite.",
        "civique",
        (3, 4, 5, 6),
        10,
        is_core=False,
    ),
]

TOPICS_BY_CODE = {t.code: t for t in TOPICS}


def topics_for_level(level: int) -> list[TopicSpec]:
    return sorted((t for t in TOPICS if level in t.levels), key=lambda t: (t.subject, t.position))


#: Niveaux effectivement peuples par le jeu de donnees livre.
DEFAULT_SEED_LEVELS = (2, 3, 4, 5, 6)
DEFAULT_SEED_COUNTRIES = ("FR", "BJ", "CI", "SN")
