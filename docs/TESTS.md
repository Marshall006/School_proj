# Stratégie de test

```bash
make test          # API + protocole partagé
make coverage      # avec rapport de couverture
make lint          # ruff + vérification de types TypeScript
make integration   # boucle serveur ↔ tablette hors ligne (API démarrée)
make e2e           # parcours navigateur du tableau de bord (API + web démarrés)
```

| Suite | Volume |
|---|---|
| `backend/tests` | 207 tests, 92 % de couverture |
| `shared/test/run.mjs` | 71 vérifications d'équivalence Python ↔ TypeScript |
| `shared/test/appareil-hors-ligne.mjs` | 17 vérifications d'intégration serveur ↔ tablette |
| `web/e2e/parcours.mjs` | 19 vérifications navigateur |

---

## Ce qui est vérifié, et pourquoi

### 1. Le protocole de déverrouillage — `test_unlock_protocol.py` (19 tests)

C'est la pièce dont dépend tout le produit : si un code peut être rejoué ou
forgé, le reste ne vaut rien.

- format, aller-retour, lecture de la durée avant vérification ;
- tolérance aux séparateurs de saisie (`240 012 3456`, `240-012-3456`) ;
- **rejeu refusé**, et un code plus récent tue les précédents ;
- fenêtre de compteur bornée ;
- refus avec un autre secret, un autre appareil, un chiffre altéré ;
- **durée falsifiée refusée** (passer `30 min` à `495 min` casse la signature) ;
- péremption hors ligne, et tolérance de part et d'autre d'une tranche ;
- codes de secours à durée de vie longue ;
- verrouillage progressif après échecs ;
- **20 000 essais aléatoires, zéro succès** (secret et graine figés pour la
  reproductibilité).

### 2. La correction — `test_grading.py` (48 tests)

- lecture des nombres : `3,14` `3/4` `1 1/2` `50 %` `1 000` `12 cm` `,5`, y
  compris avec espaces insécables ;
- rejet de ce qui n'est pas un nombre (`3/0`, `True`, `""`) ;
- crédit partiel : QCM multiple, textes à trous, remise en ordre, associations ;
- exigence de forme (`fraction irréductible`) et d'unité ;
- **diagnostics** : facteur 10, signe inversé, retenue, accents, orthographe ;
- réponse manuscrite illisible → validation parentale, jamais « faux ».

### 3. Le moteur adaptatif — `test_adaptive.py` (25 tests)

- monotonie et inversion exacte du modèle logistique ;
- convergence du niveau à la hausse comme à la baisse ;
- **pas d'ajustement décroissant** avec l'expérience ;
- répétition espacée : 1 j → 3 j → intervalle croissant, remise à zéro sur échec ;
- calibrage en retour de la difficulté des items ;
- **répartition 40 / 40 / 20 exacte**, et redistribution quand un bloc est vide ;
- somme toujours égale au nombre demandé, pour 1 à 30 questions ;
- reproductibilité à graine égale ;
- choix de l'item le plus proche de la difficulté visée, exclusion des doublons,
  évitement des questions vues récemment.

### 4. Expérience et règles — `test_xp_and_policy.py` (40 tests)

- gain proportionnel à la difficulté et au crédit partiel ;
- **rendement décroissant** : la dixième évaluation de la journée rapporte
  moins du tiers de la première ;
- bonus de réussite, de sans-faute, de lacune comblée, de série (plafonné) ;
- un échec rapporte quand même les bonnes réponses ;
- conversion arrondie au pas de 5 minutes, plafonnée, refusée si solde
  insuffisant ou conversion désactivée ;
- résolution de la période depuis le calendrier ;
- **les vacances coupent le déverrouillage direct par défaut** ;
- couvre-feu traversant minuit, sur la journée, désactivable ;
- escalade du temps de carence ;
- écriture des nombres en toutes lettres (accords de *vingt*, *cent*, *mille*).

### 5. Le minuteur — `test_screen_time.py` (20 tests)

- consommation écran allumé, **gel écran éteint** ;
- expiration quand le temps est épuisé ;
- impossible de consommer plus de temps qu'il n'en est passé ;
- recul de l'horloge monotone signalé, temps serveur imputé ;
- horloge murale décalée détectée **sans fausser le décompte** ;
- redémarrage détecté ;
- **butoir absolu** contre les pauses à répétition ;
- réconciliation hors ligne, sur-déclaration bornée ;
- une session périmée n'est jamais présentée comme active ;
- quotas du jour, purge des sessions périmées.

### 6. Parcours complets — `test_journey.py` (6 tests)

Le scénario du cahier des charges, du début à la fin :

> période scolaire → code parental → session → **bascule en vacances** → le
> déverrouillage direct est refusé → évaluation échouée → pas de code, mais
> correction détaillée et carence → nouvelle tentative bloquée → le parent lève
> la carence → évaluation réussie → code délivré → session ouverte → conversion
> d'XP → le tableau de bord reflète le tout → la chaîne d'audit est intacte.

Plus : plafond quotidien qui rogne une durée, limite de tentatives,
l'entraînement libre qui rapporte des XP sans ouvrir l'écran, appareil révoqué,
saisie bloquée après cinq codes erronés.

### 7. Hors ligne et validation parentale — `test_offline_and_review.py` (9 tests)

- **la tablette vérifie un code seule**, avec le secret reçu à l'appairage,
  puis synchronise 40 minutes plus tard : le temps consommé hors ligne est
  décompté ;
- un code révoqué est refusé et la liste de révocation est poussée à l'appareil ;
- horloge manipulée détectée à la synchronisation ;
- réponse manuscrite indécise → attente d'un parent → verdict → code délivré ;
- **score déjà suffisant → code immédiat**, sans faire patienter ;
- correction consultable après coup, sans jamais réafficher un code ;
- sauvegarde continue et reprise après coupure.

### 8. Sécurité et audit — `test_security_and_audit.py` (16 tests)

- inscription, doublon d'adresse refusé, mot de passe trop court ;
- **rotation stricte** du jeton de rafraîchissement ;
- jeton d'appareil refusé sur les routes parent, et réciproquement ;
- **cloisonnement des foyers** : un parent ne voit ni ne pilote l'enfant d'un
  autre foyer ;
- un appareil ne touche pas à l'évaluation d'un autre enfant ;
- chaîne d'audit valide ; **modification détectée** ; **suppression détectée** ;
- chaînes indépendantes par foyer ;
- lecture des listes en variable d'environnement (régression réelle, § plus bas).

### 9. Banque de contenu — `test_catalog_and_content.py` (18 tests)

- remplissage idempotent, couverture multi-pays ;
- **localisation vérifiée** : euros en France, francs CFA au Bénin ; Abomey et
  le Dahomey dans l'histoire béninoise ;
- tous les générateurs déclarés produisent au moins quatre items par notion ;
- items bien formés : barème présent, propositions distinctes, bonne réponse
  parmi les choix ;
- **plus de 1 000 items corrigés en boucle fermée** : la réponse attendue est
  reconstruite depuis le barème et doit être comptée juste, une réponse
  manifestement fausse doit être comptée fausse ;
- moins de 2 % d'items sans explication ;
- gabarits de saisie cohérents (une division posée propose la potence).

### 10. Démonstration et administration — `test_demo_and_cli.py` (6 tests)

`make demo` est le premier geste de quiconque découvre le projet : s'il casse,
rien ne démarre. Ces tests vérifient que le foyer se crée, que l'historique
simulé est cohérent (évaluations corrigées, sessions **fermées**, XP, niveau
estimé), que le tableau de bord se construit dessus, que la chaîne d'audit reste
valide, que relancer la commande ne duplique rien, et que les tâches de
maintenance ne cassent pas sur une base vide.

---

## Équivalence Python ↔ TypeScript — `shared/test/run.mjs`

**71 vérifications.** Les vecteurs sont produits par l'implémentation Python de
référence, puis rejoués par le portage TypeScript :

- SHA-256 et HMAC maison comparés à `node:crypto` (y compris accents et emoji) ;
- codes émis identiques au chiffre près ;
- empreintes identiques ;
- mêmes acceptations, **mêmes refus**, même tolérance temporelle ;
- performance : une vérification exhaustive reste sous 60 ms, condition pour
  que le déverrouillage soit instantané sur une tablette d'entrée de gamme.

C'est ce test qui permet à la tablette de valider un code hors ligne en étant
certaine d'accepter exactement ce que le serveur émet.

---

## Intégration serveur ↔ tablette — `shared/test/appareil-hors-ligne.mjs`

**17 vérifications**, sans navigateur ni émulateur : le script joue le rôle de
la tablette avec l'implémentation TypeScript réellement embarquée dans
l'application.

1. le parent appaire un appareil neuf et reçoit un secret de 32 octets ;
2. il génère un code — et si la période est aux vacances, le déverrouillage
   direct est refusé et la rallonge prend le relais, comme dans l'interface ;
3. **la tablette valide le code sans rappeler le serveur** ;
4. elle refuse ensuite de le rejouer, et refuse une durée falsifiée ;
5. le serveur accepte la consommation, puis refuse lui aussi le rejeu ;
6. le minuteur bat la mesure, et **se met en pause écran éteint** ;
7. la révocation de l'appareil coupe tout accès.

---

## Clients

| Client | Vérification |
|---|---|
| `web` | `next build` avec vérification de types complète — 9 routes |
| `mobile` | `tsc --noEmit` puis bundle Metro (721 modules, 1,8 Mo de bytecode Hermes) |

Le bundle Metro n'est pas décoratif : il prouve que le module partagé est
réellement résolvable depuis React Native, ce que la seule vérification de types
ne garantit pas.

### Parcours navigateur du tableau de bord

Un scénario Playwright exerce l'interface contre l'API réelle et le jeu de
démonstration — **21 vérifications** : connexion, liste des enfants, banque
pédagogique, intégrité du journal, génération d'un code à 10 chiffres avec
compte à rebours, les trois graphiques, la vue tableau de substitution, la page
de règles, appareils, copies, calendrier, bascule du thème, et **aucune erreur
de console**.

---

## Deux bugs réels trouvés par ces tests

Ils sont mentionnés parce qu'ils illustrent ce que chaque niveau attrape.

**`KODA_CORS_ORIGINS=http://a,http://b` faisait échouer le démarrage.**
pydantic-settings tentait un décodage JSON avant la validation. Trouvé en
lançant le navigateur contre l'API — invisible pour les tests unitaires, qui
n'utilisaient que les valeurs par défaut. Corrigé avec `NoDecode` et couvert par
`test_origines_cors_depuis_lenvironnement`.

**Une session ouverte la veille restait affichée comme active.** Sans battement
de cœur, rien ne la fermait. Corrigé par une expiration paresseuse appliquée sur
tous les chemins de lecture, et couvert par
`test_session_perimee_nest_jamais_presentee_comme_active`.

---

## Couverture

92 % sur `backend/app`. Les zones non couvertes sont l'adaptateur Firebase (il
demande un vrai projet Google) et le câblage de démarrage d'uvicorn.

> La couverture est mesurée avec `concurrency = ["greenlet", "thread"]` :
> SQLAlchemy asyncio exécute du code dans des greenlets, et sans cette option la
> couverture des services est massivement sous-estimée (44 % au lieu de 91 %
> pour `services/assessment.py`).
