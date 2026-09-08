# KODA — contrôle parental éducatif

**L'écran se mérite.**

KODA remplace la restriction punitive du temps d'écran par un contrat clair :
le divertissement numérique s'obtient en montrant que le travail scolaire est
fait. Deux chemins, et un seul verrou.

| Période | Comment la tablette s'ouvre |
|---|---|
| **Scolaire** | Les devoirs sont faits : le parent génère un code depuis son tableau de bord et le dicte. |
| **Vacances / révisions** | Pas de devoirs à valider : l'enfant passe une évaluation et obtient son code s'il dépasse le seuil exigé. |

En cas d'échec, pas de code — mais la **correction détaillée**, et un **temps de
carence** pendant lequel réviser. L'échec devient une étape, pas une sanction
sèche.

---

## Ce que contient le dépôt

```
backend/    API FastAPI + PostgreSQL — règles, évaluations, codes, minuteur
web/        Tableau de bord parental (Next.js)
mobile/     Application enfant (React Native / Expo) — l'examen et le verrou
shared/     Protocole de déverrouillage et types, partagés par les trois
docs/       Architecture, sécurité, pédagogie, API, feuille de route
```

Les trois clients parlent le **même protocole de déverrouillage**, écrit une
fois en Python et une fois en TypeScript, et vérifié à chaque build contre des
vecteurs de test communs : les deux implémentations ne peuvent pas diverger.

---

## Démarrage rapide

### Avec Docker

```bash
cp .env.example .env
docker compose up --build
docker compose exec api python -m app.cli demo   # foyer de démonstration
```

- Tableau de bord parent : <http://localhost:3000> — `demo@koda.app` / `demo-koda-2026`
- API et documentation interactive : <http://localhost:8000/docs>

### Sans Docker

```bash
make install     # API, module partagé, tableau de bord, application enfant
make demo        # base SQLite locale + foyer de démonstration
make api         # http://localhost:8000
make web         # http://localhost:3000
make mobile      # Expo (tablette ou émulateur)
```

`make aide` liste toutes les cibles.

> Sans configuration, l'API utilise une base SQLite locale
> (`backend/koda.db`) : rien à installer, migrations comprises. Pour
> PostgreSQL, renseignez `KODA_DATABASE_URL` dans `.env` — c'est ce que fait
> `docker compose`.

---

## Le parcours, de bout en bout

1. **Le parent crée un foyer**, ajoute un enfant (pays + classe), et appaire sa
   tablette avec un code à usage unique. L'appareil reçoit alors un secret
   qu'il ne redemandera jamais.
2. **Il règle les exigences** par période : note minimale (14/20 par défaut),
   nombre de questions, temps accordé, plafond quotidien, temps de carence,
   couvre-feu, conversion des points d'expérience.
3. **Période scolaire** : les devoirs sont faits, le parent génère un code de
   10 chiffres et le dicte. La tablette le valide **même hors ligne**.
4. **Vacances** : le déverrouillage direct est coupé. L'enfant lance une
   évaluation composée par le moteur adaptatif, répond en mode assisté (pavé
   mathématique, potence de division, constructeur de fractions) ou sur
   l'**ardoise** manuscrite.
5. **Réussite** → code délivré automatiquement, minuteur lancé, XP crédités.
   **Échec** → correction détaillée avec diagnostic de l'erreur, liste des
   notions à revoir, et temps de carence.
6. **Le parent suit** le taux de réussite par matière, les lacunes classées par
   urgence, le temps réellement consommé, et les éventuels signaux de
   contournement.

---

## Ce qui distingue ce projet

**Un verrou qui fonctionne hors ligne.** Couper le wifi est le premier réflexe
de contournement. Les codes sont des jetons signés (HMAC-SHA256) que la
tablette valide seule, sans réseau, sans pouvoir être rejoués.
→ [`docs/SECURITE.md`](docs/SECURITE.md)

**Un minuteur qu'on ne triche pas.** Le décompte s'appuie sur une horloge
monotone, pas sur l'heure système : changer l'heure de la tablette ne donne
rien. Les incohérences remontent au parent au lieu d'être silencieusement
ignorées.

**Un moteur d'évaluation qui ne décourage pas.** Chaque épreuve mélange 40 % de
remédiation, 40 % de programme en cours et 20 % d'acquis, avec une difficulté
visée autour de 75 % de réussite attendue.
→ [`docs/PEDAGOGIE.md`](docs/PEDAGOGIE.md)

**Une banque réellement multi-pays.** 3 232 questions générées pour la France,
le Bénin, la Côte d'Ivoire et le Sénégal : intitulés de classes, monnaie,
repères historiques et géographiques adaptés à chaque pays.

**Un historique infalsifiable.** Le journal du foyer est chaîné par hachage :
supprimer ou modifier une ligne casse la chaîne, ce que le tableau de bord
détecte.

**L'enfant n'est jamais puni par la machine.** Si la reconnaissance d'écriture
échoue, la copie part en validation parentale plutôt que d'être comptée fausse.

---

## Tests

```bash
make test        # suite complète (API + protocole partagé)
make coverage    # avec rapport de couverture
make lint        # analyse statique Python + TypeScript
```

| Suite | Commande | Portée | Résultat |
|---|---|---|---|
| API | `make test-api` | protocole, correction, moteur adaptatif, XP, règles, minuteur, parcours complets | **207 tests**, 92 % de couverture |
| Protocole partagé | `make test` | équivalence Python ↔ TypeScript, SHA-256 vérifié contre `node:crypto` | **71 vérifications** |
| Serveur ↔ tablette | `make integration` | le code émis par l'API est validé **hors ligne** par l'implémentation TypeScript, puis consommé | **17 vérifications** |
| Tableau de bord | `make e2e` | parcours navigateur complet contre l'API réelle | **19 vérifications** |
| Application enfant | — | `tsc --noEmit` + bundle Metro (721 modules) | — |

Détail dans [`docs/TESTS.md`](docs/TESTS.md), y compris les deux bugs réels que
ces tests ont attrapés.

---

## Documentation

| Document | Contenu |
|---|---|
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Découpage, modèle de données, choix techniques et leurs raisons |
| [`docs/SECURITE.md`](docs/SECURITE.md) | Protocole KODA-UNLOCK, modèle de menace, anti-triche |
| [`docs/PEDAGOGIE.md`](docs/PEDAGOGIE.md) | Moteur adaptatif, banque de contenu, correction et diagnostic |
| [`docs/API.md`](docs/API.md) | Points d'entrée, authentification, erreurs |
| [`docs/TESTS.md`](docs/TESTS.md) | Stratégie de test et couverture |
| [`docs/ROADMAP.md`](docs/ROADMAP.md) | Ce qui reste à faire, y compris les évolutions V2 |

---

## Licence et usage

Projet scolaire. Le contenu pédagogique livré est généré et sert de base de
travail : une relecture par des enseignants est nécessaire avant tout usage
réel avec des enfants.
