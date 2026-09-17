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

### Tester sur un téléphone (Expo Go)

Le téléphone doit être sur le **même Wi-Fi** que l'ordinateur. Aucune adresse
d'API à configurer : en développement, l'application joint l'API **à travers
le serveur Expo**, qui relaie `/api/*` vers `make api` (voir
`mobile/metro.config.js`). Le téléphone n'a donc qu'un seul port à joindre,
celui qui lui sert déjà l'application.

```bash
make api            # terminal 1
make mobile         # terminal 2 — scannez le QR avec l'appareil photo de l'iPhone
make mobile-check   # diagnostic réseau, sans rien lancer
```

Puis, sur le tableau de bord : **Appareils → Appairer pour…**, et saisissez le
code sur le téléphone.

#### Sous WSL : ouvrir un pont vers Windows

En mode NAT (le défaut), Linux a une adresse interne `172.x` invisible du
réseau local. `make mobile` la détecte, affiche la commande exacte à passer, et
demande à Expo d'annoncer l'adresse Wi-Fi de Windows à la place.

Une seule commande, dans **PowerShell en administrateur** — `make mobile`
l'affiche déjà remplie avec l'adresse WSL du moment :

```powershell
netsh interface portproxy add v4tov4 listenport=8081 listenaddress=0.0.0.0 connectport=8081 connectaddress=<adresse-WSL>

# Et, la première fois seulement, autoriser le port dans le pare-feu :
New-NetFirewallRule -DisplayName "KODA Expo (8081)" -Direction Inbound `
  -Protocol TCP -LocalPort 8081 -Action Allow -Profile Private
```

L'adresse de WSL change à chaque redémarrage : relancez `make mobile` pour
obtenir la commande à jour. **Rien n'est modifié dans WSL.**

Pour tout annuler :

```powershell
netsh interface portproxy delete v4tov4 listenport=8081 listenaddress=0.0.0.0
Remove-NetFirewallRule -DisplayName "KODA Expo (8081)"
```

> **N'activez pas le mode réseau miroir de WSL** (`networkingMode=mirrored`
> dans `.wslconfig`) pour ce projet. Il paraît plus élégant, mais il rend WSL
> inutilisable sur certaines configurations — au point de ne plus pouvoir
> démarrer la distribution. Le pont ci-dessus obtient le même résultat sans
> toucher à WSL. Si vous l'aviez activé et que WSL ne démarre plus : supprimez
> `%UserProfile%\.wslconfig`, puis `wsl --shutdown`.

#### Si le téléphone tourne encore en boucle

| Vérification | Où |
|---|---|
| Expo Go a le droit d'accéder au **réseau local** (iOS le demande au premier lancement ; un refus fait tourner en boucle) | iPhone : Réglages → Confidentialité et sécurité → Réseau local → Expo Go |
| Le Wi-Fi Windows est en **réseau privé** (la règle de pare-feu ne s'applique pas aux réseaux publics) | Paramètres → Réseau et Internet → Wi-Fi → Type de profil réseau |
| Téléphone et ordinateur sur le **même** Wi-Fi, sans « isolation des clients » (fréquente sur les réseaux invités) | Box / point d'accès |
| Un seul serveur Expo tourne (un ancien sur le port 8081 bloque le nouveau) | `Ctrl+C` dans l'ancien terminal |
| Les versions natives correspondent au SDK d'Expo Go | `cd mobile && npx expo-doctor` |

Sans téléphone sous la main, `cd mobile && npx expo start --web` ouvre
l'application enfant dans le navigateur : l'examen et l'ardoise y sont
utilisables.

---|---|
| Le Wi-Fi Windows est en **réseau privé** (la règle 3 ne s'applique pas aux réseaux publics) | Paramètres → Réseau et Internet → Wi-Fi → Type de profil réseau |
| Expo Go a le droit d'accéder au **réseau local** (iOS le demande au premier lancement ; un refus fait tourner en boucle) | iPhone : Réglages → Confidentialité et sécurité → Réseau local → Expo Go |
| Téléphone et ordinateur sur le **même** Wi-Fi, sans « isolation des clients » (fréquente sur les réseaux invités) | Box / point d'accès |
| Un seul serveur Expo tourne (un ancien sur le port 8081 bloque le nouveau) | `Ctrl+C` dans l'ancien terminal |

---|---|
| Émulateur Android | `http://10.0.2.2:8000/api/v1` |
| Simulateur iOS | `http://localhost:8000/api/v1` |
| Tablette réelle | `http://<adresse de votre machine>:8000/api/v1` |

`make ip` affiche l'adresse à utiliser. `make api` écoute sur toutes les
interfaces, donc l'appareil peut l'atteindre.

> **Sous WSL**, l'adresse affichée est celle de la machine virtuelle Linux :
> elle n'est pas joignable depuis le réseau local sans redirection de ports
> côté Windows. Le plus simple est alors `cd mobile && npx expo start --tunnel`,
> qui fonctionne quelle que soit la topologie réseau.

Une fois l'application lancée : générez un code d'appairage depuis le tableau
de bord (**Appareils → Appairer pour…**), saisissez-le sur la tablette, et vous
êtes dans le parcours enfant.

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
