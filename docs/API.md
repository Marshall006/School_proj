# API

Base : `/api/v1` · Documentation interactive : `/docs` · Schéma : `/openapi.json`

Toutes les réponses sont en JSON. Les messages d'erreur sont **rédigés en
français côté serveur** : un client peut les afficher tels quels.

---

## Authentification

Deux identités, deux jetons, deux portées.

| | Parent | Appareil enfant |
|---|---|---|
| En-tête | `Authorization: Bearer <jeton d'accès>` | `Authorization: Bearer <jeton d'appareil>` (ou `X-Device-Token`) |
| Obtention | `POST /auth/login` ou `/auth/firebase` | `POST /devices/claim` avec un code d'appairage |
| Durée | 1 h, rafraîchissable 30 j | longue, révocable par le parent |
| Portée | son foyer | son seul enfant |

Le jeton de rafraîchissement est **à usage unique** : `POST /auth/refresh` en
émet un nouveau et invalide l'ancien. Le réutiliser renvoie `401
refresh_expired`.

Un jeton d'appareil sur une route parent — ou l'inverse — est refusé.

---

## Format des erreurs

```json
{
  "error": {
    "code": "cooldown_active",
    "message": "Tu dois attendre la fin du temps de carence pour retenter.",
    "details": {
      "until": "2026-03-15T18:30:00Z",
      "remaining_minutes": 87,
      "review_topics": [{ "topic_id": "…", "subject_code": "math", "missed": 3 }]
    }
  }
}
```

Le `code` est stable et destiné aux clients ; `details` transporte ce dont
l'interface a besoin pour afficher le bon écran.

| Code | HTTP | Signification |
|---|---|---|
| `unauthenticated`, `token_expired`, `refresh_expired` | 401 | Session à renouveler |
| `permission_denied`, `device_revoked` | 403 | Ressource hors du foyer, ou appareil révoqué |
| `policy_forbids` | 403 | La règle de la période interdit cette action |
| `not_found` | 404 | Ressource inexistante |
| `conflict`, `email_taken`, `too_many_attempts` | 409 | État incompatible |
| `cooldown_active`, `curfew`, `daily_cap_reached`, `device_locked` | 423 | Verrou métier, avec l'instant de reprise dans `details` |
| `invalid_unlock_code` | 400 | Code faux, déjà utilisé, expiré ou annulé |
| `no_content_available` | 409 | Aucune question pour ce niveau et ces matières |
| `rate_limited` | 429 | Trop de requêtes |
| `validation_error` | 422 | Données mal formées (`details.fields`) |

Chaque réponse porte `X-Request-ID` et `X-Response-Time-Ms`.

---

## Comptes et foyer

| Méthode | Chemin | Rôle |
|---|---|---|
| `POST` | `/auth/register` | Crée un foyer et son premier parent |
| `POST` | `/auth/login` | Connexion par mot de passe |
| `POST` | `/auth/firebase` | Échange un jeton Firebase (téléphone / e-mail) contre une session KODA |
| `POST` | `/auth/refresh` | Rotation du jeton |
| `POST` | `/auth/logout` | Révoque le jeton de rafraîchissement |
| `GET` | `/auth/me` | Parent et foyer courants |
| `GET` | `/family/overview` | Chiffres du foyer, tous enfants confondus |
| `GET` | `/family/audit?verify=true` | Journal chaîné, avec revalidation de la chaîne |

## Enfants

| Méthode | Chemin | Rôle |
|---|---|---|
| `POST` `GET` | `/children` | Créer, lister |
| `GET` `PATCH` `DELETE` | `/children/{id}` | Consulter, modifier, désactiver |
| `GET` | `/children/{id}/status` | État instantané : verrouillé, temps restant, carence |
| `GET` | `/children/{id}/dashboard` | Toutes les métriques en un appel |
| `GET` | `/children/{id}/policy` | Règles réellement appliquées maintenant |
| `GET` | `/children/{id}/lockout` | Temps de carence en cours |
| `POST` | `/children/{id}/lockout/release` | Le parent lève la carence |

## Règles et calendrier

| Méthode | Chemin | Rôle |
|---|---|---|
| `GET` `PUT` | `/policies` | Lister ; créer ou mettre à jour un profil (période, éventuellement enfant) |
| `DELETE` | `/policies/{id}` | Supprimer un profil |
| `GET` `POST` | `/calendar` | Périodes déclarées (vacances, week-end prolongé) |
| `DELETE` | `/calendar/{id}` | Retirer une période |

La résolution suit l'ordre : **profil de l'enfant pour la période courante →
profil du foyer → valeurs par défaut**. La période vient du calendrier ; à
défaut, samedi et dimanche sont des week-ends et le reste est scolaire.

## Appareils

| Méthode | Chemin | Rôle | Identité |
|---|---|---|---|
| `POST` | `/devices/pairing-code` | Génère un code d'appairage à usage unique | parent |
| `POST` | `/devices/claim` | L'appareil l'échange contre ses identifiants durables | aucune |
| `GET` | `/devices` | Liste, avec écart d'horloge et indice d'anomalie | parent |
| `POST` | `/devices/{id}/revoke` | Coupe l'accès et ferme la session en cours | parent |
| `POST` | `/devices/{id}/unlock-attempts/reset` | Débloque la saisie après des codes erronés | parent |
| `POST` | `/device/sync` | Règles, carence, session, révocations, dérive d'horloge | appareil |

`/devices/claim` est le **seul** moment où le `device_secret` transite.

## Déverrouillage

| Méthode | Chemin | Rôle | Identité |
|---|---|---|---|
| `POST` | `/unlock/parent-code` | Déverrouillage direct (période scolaire) | parent |
| `POST` | `/unlock/bonus-code` | Rallonge exceptionnelle, hors profil de période | parent |
| `GET` | `/unlock/codes?child_id=` | Historique des codes émis | parent |
| `POST` | `/unlock/codes/{id}/revoke` | Annule un code non consommé | parent |
| `POST` | `/unlock/redeem` | Consomme un code et ouvre la session | appareil |
| `POST` | `/unlock/xp/quote` | Simule une conversion XP → minutes | parent |
| `POST` | `/unlock/xp/redeem` | Convertit et ouvre la session | appareil |

`/unlock/redeem` accepte `consumed_offline_at` et `offline_active_ms` : c'est
ainsi qu'une tablette rapporte un déverrouillage effectué sans réseau.

## Temps d'écran

| Méthode | Chemin | Rôle | Identité |
|---|---|---|---|
| `GET` | `/screen/current` | Session en cours de l'appareil | appareil |
| `POST` | `/screen/sessions/{id}/heartbeat` | Battement du minuteur | appareil |
| `POST` | `/screen/sessions/{id}/pause` `/resume` `/end` | Contrôle local | appareil |
| `POST` | `/screen/sessions/{id}/extend` | Rallonge parentale | parent |
| `POST` | `/screen/sessions/{id}/stop` | Coupure immédiate à distance | parent |
| `GET` | `/screen/sessions/{id}/events` | Journal détaillé, utile pour comprendre une anomalie | parent |
| `GET` | `/children/{id}/screen-sessions` | Historique des sessions | parent |

Le battement porte `monotonic_ms` (temps monotone depuis le début de la
session), `device_wall_ms` (pour mesurer la dérive) et `screen_on`. Il renvoie
le temps restant, les anomalies détectées et un ordre `should_lock`.

## Évaluations

| Méthode | Chemin | Rôle | Identité |
|---|---|---|---|
| `GET` | `/assessments/eligibility` | Peut-on lancer une évaluation ? sinon pourquoi | appareil |
| `POST` | `/assessments` | Compose et ouvre une épreuve | appareil |
| `GET` | `/assessments/current` | Reprise après coupure, réponses comprises | appareil |
| `GET` | `/assessments/{id}` | Énoncés (jamais le corrigé) | appareil |
| `PATCH` | `/assessments/{id}/items/{item}` | Sauvegarde continue d'une réponse | appareil |
| `POST` | `/assessments/{id}/submit` | Correction et verdict | appareil |
| `GET` | `/assessments/{id}/review` | Correction détaillée, consultable après coup | appareil |
| `GET` | `/children/{id}/assessments` | Historique | parent |
| `GET` | `/parent/assessments/pending-review` | Copies en attente de validation manuscrite | parent |
| `GET` | `/parent/assessments/{id}` | Copie complète : réponses, corrections, tracé de l'ardoise | parent |
| `POST` | `/parent/assessments/{id}/items/{item}/grade` | Le parent tranche une réponse manuscrite | parent |
| `POST` | `/parent/children/{id}/assessments` | Le parent pousse une évaluation | parent |

`submit` accepte un envoi groupé (`answers`) : une épreuve peut être composée
entièrement hors ligne puis envoyée d'un bloc.

## Catalogue

| Méthode | Chemin | Rôle |
|---|---|---|
| `GET` | `/catalog/countries` | Pays et intitulés de classes |
| `GET` | `/catalog/subjects` `/catalog/grades` `/catalog/topics` | Référentiel |
| `GET` | `/catalog/coverage` | Volume de la banque, par pays et par classe |
| `GET` `POST` | `/catalog/questions` | Questions d'une notion ; ajout par le parent |
| `DELETE` | `/catalog/questions/{id}` | Retire une question personnalisée |

---

## Exemple : déverrouillage parental complet

```bash
# 1. Le parent se connecte
JETON=$(curl -s -X POST localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"demo@koda.app","password":"demo-koda-2026"}' \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["tokens"]["access_token"])')

# 2. Il génère un code de 2 h pour un enfant
curl -s -X POST localhost:8000/api/v1/unlock/parent-code \
  -H "Authorization: Bearer $JETON" -H 'Content-Type: application/json' \
  -d '{"child_id":"<uuid>","duration_minutes":120,"note":"Devoirs faits"}'
# → { "code": "2400123456", "formatted": "240 012 3456", "expires_at": "…" }

# 3. La tablette le consomme (jeton d'appareil)
curl -s -X POST localhost:8000/api/v1/unlock/redeem \
  -H "Authorization: Bearer $JETON_APPAREIL" -H 'Content-Type: application/json' \
  -d '{"code":"240 012 3456"}'
# → { "session_id": "…", "granted_minutes": 120, "remaining_ms": 7200000 }

# 4. Puis bat la mesure toutes les 30 s
curl -s -X POST localhost:8000/api/v1/screen/sessions/<session>/heartbeat \
  -H "Authorization: Bearer $JETON_APPAREIL" -H 'Content-Type: application/json' \
  -d '{"monotonic_ms":60000,"device_wall_ms":1789000000000,"screen_on":true}'
# → { "remaining_ms": 7140000, "should_lock": false, "anomalies": [] }
```
