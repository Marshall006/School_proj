# Architecture

## Vue d'ensemble

```
┌────────────────────┐        ┌────────────────────┐
│  Tableau de bord   │        │  Application       │
│  parental (Next.js)│        │  enfant (Expo)     │
│                    │        │                    │
│  · règles          │        │  · verrou local    │
│  · codes           │        │  · examen          │
│  · métriques       │        │  · ardoise         │
│  · copies à valider│        │  · minuteur        │
└─────────┬──────────┘        └─────────┬──────────┘
          │  HTTPS (jeton parent)       │  HTTPS (jeton appareil)
          │                             │  … ou rien du tout : le verrou
          │                             │     fonctionne hors ligne
          └──────────────┬──────────────┘
                         │
              ┌──────────▼───────────┐        ┌──────────────────┐
              │   API FastAPI        │◄──────►│  PostgreSQL      │
              │                      │        │  (21 tables)     │
              │  · règles par période│        └──────────────────┘
              │  · moteur adaptatif  │
              │  · correction        │        ┌──────────────────┐
              │  · émission de codes │◄──────►│  shared/         │
              │  · comptabilité temps│        │  protocole       │
              │  · journal chaîné    │        │  (Python ↔ TS)   │
              └──────────────────────┘        └──────────────────┘
```

Le module `shared/` n'est pas une commodité : c'est **la garantie que les trois
programmes calculent le même code**. Le protocole y est écrit deux fois et
vérifié l'une contre l'autre à chaque build.

---

## Backend

### Découpage

```
app/
  core/          config, sécurité, horloge injectable, erreurs métier,
                 protocole de déverrouillage (pur, sans I/O)
  db/            socle SQLAlchemy, types portables PostgreSQL ↔ SQLite
  models/        21 tables
  schemas/       contrats d'API (Pydantic)
  services/      la logique métier — c'est ici que vit le produit
  api/v1/        routeurs HTTP, fins et sans logique
  content/       catalogue, générateurs, remplissage, démonstration
```

**Les routeurs ne décident de rien.** Ils authentifient, valident la forme des
données, appellent un service et sérialisent. Toute la logique — quand un code
peut être émis, comment une épreuve se compose, ce que vaut une réponse — vit
dans `services/`, ce qui la rend testable sans HTTP.

### Les services

| Service | Responsabilité |
|---|---|
| `policy` | Résout les règles applicables : période du calendrier → profil enfant → profil foyer → défauts |
| `assessment` | Compose, corrige, décide : code délivré ou temps de carence |
| `adaptive` | Estimation de maîtrise, composition équilibrée, répétition espacée |
| `grading` | Correction tolérante à la saisie et diagnostic pédagogique |
| `unlock` | Émission et consommation des codes, plafonds, couvre-feu |
| `screen_time` | Comptabilité du temps, anomalies, réconciliation hors ligne |
| `xp` | Gains, rendement décroissant, conversion en minutes |
| `lockouts` | Temps de carence et escalade |
| `audit` | Journal chaîné par hachage |
| `analytics` | Métriques du tableau de bord |

`grading`, `adaptive` et `xp` sont **purs** : aucune I/O, aucune dépendance à
la base. Ce sont eux qui portent la valeur pédagogique du produit, et ils sont
testables exhaustivement — c'est ce qui permet de vérifier les 3 232 questions
générées une par une.

### Modèle de données

```
Family ─┬─ Parent (rôle : propriétaire / tuteur / lecteur)
        ├─ Child ─┬─ Device ─── UnlockCode ─── ScreenSession ─── ScreenEvent
        │         ├─ Assessment ─── AssessmentItem
        │         ├─ Mastery (par notion)
        │         ├─ XPLedgerEntry
        │         └─ Lockout
        ├─ PolicyProfile (par période, éventuellement par enfant)
        ├─ CalendarPeriod
        └─ AuditEvent (chaîné)

Subject ─── Topic ─── Question        (pays × classe × matière)
GradeLevel                            (intitulés propres à chaque pays)
```

Trois décisions structurantes :

**Les points d'expérience sont un grand livre, pas un compteur.** Chaque
mouvement est tracé avec son solde résultant. On peut expliquer à un enfant
d'où viennent ses points, et à un parent pourquoi le solde a bougé.

**L'énoncé est figé dans l'épreuve.** `AssessmentItem.snapshot` contient une
copie de la question au moment où elle a été posée. Corriger une faute de frappe
dans la banque ne réécrit pas l'historique.

**Les règles aussi sont figées.** `Assessment.policy_snapshot` archive les
exigences en vigueur au démarrage : durcir le seuil en cours d'épreuve ne
change pas le verdict de l'épreuve en cours.

### Choix techniques, et pourquoi

| Choix | Raison |
|---|---|
| **FastAPI + SQLAlchemy 2 asynchrone** | Beaucoup d'appels courts et concurrents (battements de cœur toutes les 30 s par appareil). |
| **Types portables PostgreSQL ↔ SQLite** | PostgreSQL en production ; SQLite en mémoire pour des tests rapides et une démonstration sans installation. Le même code, les mêmes migrations. |
| **`UTCDateTime` sur mesure** | SQLite perd le fuseau. Le type force l'aller-retour en UTC : plus de comparaisons de dates naïves. |
| **Énumérations en `VARCHAR` + `CHECK`** | Ajouter une valeur ne demande pas de migration de type PostgreSQL. |
| **PBKDF2 de la bibliothèque standard** | Pas de `bcrypt` ni d'`argon2` à compiler : le build ne casse ni sur ARM ni sur Alpine. 240 000 itérations. |
| **Horloge applicative injectable** | Les tests voyagent dans le temps (expiration, carence, couvre-feu) sans `sleep`. |
| **Firebase optionnel** | Configuré → authentification par téléphone. Non configuré → authentification locale, le produit reste entier. |

---

## Tableau de bord parental (Next.js)

App Router, composants clients, appels directs à l'API avec rotation
automatique du jeton. Pas de framework CSS : un système de variables CSS avec
un mode sombre réellement conçu (couleurs re-choisies, pas inversées).

Les graphiques sont du SVG écrit à la main, sur une palette validée pour le
daltonisme et le contraste :

- **Temps d'écran** — colonnes, deux nuances d'une même teinte (accordé /
  consommé), infobulle au survol.
- **Réussite par matière** — barres classées, teinte unique, ligne de seuil en
  pointillés ; les matières sous le seuil portent une étiquette explicite, pas
  seulement une couleur. Une vue tableau est disponible en un clic.
- **Maîtrise par notion** — barre empilée sur une rampe ordonnée (fragile →
  expert), légende portant les effectifs.

---

## Application enfant (React Native / Expo)

Navigation volontairement minimale : quatre états (appairage, verrouillé,
examen, déverrouillé). Une pile de navigation complète serait une surface
d'évasion supplémentaire sur un appareil dont on veut contraindre l'usage.

- **Verrou local** (`lib/lockGuard.ts`) — vérification du code sans réseau,
  compteur anti-rejeu persistant, verrouillage progressif de la saisie.
- **Minuteur** (`lib/timer.ts`) — horloge monotone, pause automatique quand
  l'application passe en arrière-plan, recalage sur le serveur sans jamais
  rendre du temps déjà consommé.
- **Saisie assistée** (`components/`) — pavé adapté à la question, constructeur
  de fractions, potence de division, opération posée en colonnes, remise en
  ordre, associations.
- **Ardoise** (`components/Slate.tsx`) — tracé vectoriel (listes de points), pas
  une image : léger à transmettre, redimensionnable, et le parent revoit
  exactement ce que l'enfant a écrit.
- **File d'attente hors ligne** (`api/client.ts`) — les battements et
  consommations produits sans réseau sont rejoués à la reconnexion.

---

## Flux critiques

### Déverrouillage parental (période scolaire)

```
Parent ──► POST /unlock/parent-code
             ├─ règles : le déverrouillage direct est-il autorisé ?
             ├─ compteur de l'appareil +1
             ├─ code = HMAC(secret, appareil|compteur|durée|nature|tranche)
             └─ empreinte enregistrée, code jamais stocké en clair
       ◄── 10 chiffres, dictés à l'enfant

Enfant ──► saisie sur la tablette
             ├─ vérification LOCALE (fonctionne hors ligne)
             ├─ compteur local avancé → les codes antérieurs meurent
             └─ session ouverte immédiatement
           POST /unlock/redeem  (dès que le réseau revient)
             ├─ code révoqué ? déjà consommé ? expiré ?
             ├─ plafond quotidien → durée éventuellement rognée
             ├─ carence / couvre-feu selon la nature du code
             └─ session serveur ouverte, réconciliation du temps hors ligne
```

### Déverrouillage par évaluation (vacances)

```
POST /assessments
  ├─ éligibilité : carence ? quota du jour ? règle du foyer ?
  ├─ notions du programme (pays × classe) ayant des questions
  ├─ état de maîtrise → plan 40 / 40 / 20
  ├─ pour chaque créneau, la question la plus proche de la difficulté visée
  │  (en évitant celles vues récemment)
  └─ épreuve figée : énoncés sans corrigé, règles archivées

POST /assessments/{id}/submit
  ├─ correction item par item (crédit partiel, diagnostic)
  ├─ mise à jour de la maîtrise + calibrage de la difficulté des items
  ├─ XP avec rendement décroissant
  └─ verdict :
       réussi        → code émis, minutes créditées
       en attente    → une réponse manuscrite doit être tranchée par un parent
       échoué        → carence + correction détaillée + notions à revoir
```

---

## Déploiement

`docker compose up --build` lève PostgreSQL, l'API (migrations Alembic
appliquées au démarrage) et le tableau de bord. Les images sont
multi-étapes, tournent en utilisateur non privilégié et exposent une sonde de
santé.

L'application enfant se distribue par EAS Build / les magasins ; en
développement, `make mobile` suffit.

Tâches de fond à planifier en production (`python -m app.cli housekeeping`) :
expiration des codes, des sessions et des épreuves abandonnées.
