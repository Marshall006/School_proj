# Sécurité et anti-triche

Ce document décrit ce contre quoi KODA se protège, comment, et — tout aussi
important — ce contre quoi il ne se protège pas.

---

## 1. Le modèle de menace

L'adversaire est **un enfant motivé, sur un appareil qu'il possède
physiquement**. Ce n'est pas un attaquant distant : il a le temps, l'appareil
en main, et une bonne raison d'essayer. Les tentatives réalistes, par ordre de
probabilité :

| # | Tentative | Réponse |
|---|---|---|
| 1 | Couper le wifi pour que l'app « ne sache plus » | Le verrou est local : couper le réseau ne l'ouvre pas (§ 2) |
| 2 | Changer l'heure de la tablette pour rallonger le temps | Décompte sur horloge monotone (§ 3) |
| 3 | Réutiliser un code noté sur un papier | Compteur anti-rejeu de type HOTP (§ 2.3) |
| 4 | Deviner un code | 10^7 étiquettes + verrouillage progressif (§ 2.5) |
| 5 | Forcer l'arrêt de l'application | Réconciliation à la reconnexion + butoir absolu (§ 3.3) |
| 6 | Redémarrer pour remettre le minuteur à zéro | Détection de changement de `boot_id` (§ 3.2) |
| 7 | Se faire passer pour un autre enfant | Jeton d'appareil lié à un seul enfant (§ 4) |
| 8 | Effacer une trace gênante en base | Journal chaîné par hachage (§ 5) |

**Hors périmètre, assumé.** Un appareil rooté ou jailbreaké, sur lequel
l'enfant peut désinstaller l'application ou lire le magasin sécurisé, sort du
modèle. Aucun contrôle parental logiciel ne résout ce cas ; le produit vise à
rendre le contournement *coûteux et visible*, pas impossible. Toute anomalie
détectée remonte au parent : c'est la vraie ligne de défense.

---

## 2. Le protocole KODA-UNLOCK

### 2.1 Le problème

La tablette est souvent hors ligne. Le code saisi doit donc être validable
**sans réseau**, tout en restant infalsifiable et non rejouable. Un simple code
« secret partagé » ne suffit pas : il serait réutilisable indéfiniment.

### 2.2 Le format

Un code fait **10 chiffres**, affichés en trois groupes (`123 456 7890`) :

```
    d0 d1   durée accordée, en tranches de 5 minutes (00..99 → 0..495 min)
    d2      nature du code (parental, récompense, XP, bonus, secours)
    d3..d9  troncature décimale sur 7 chiffres de HMAC-SHA256
```

La signature porte sur :

```
KODA1 | <identifiant appareil> | <compteur> | <unités de durée> | <nature> | <tranche horaire>
```

La clé est le **secret d'appareil** : 32 octets aléatoires, remis une seule
fois lors de l'appairage, stockés dans le Keychain / Keystore du système.

Conséquence directe : les deux premiers chiffres sont lisibles avant
vérification (« ce code ouvre 3 h »), mais **les modifier invalide la
signature** — on ne rallonge pas un code de 30 minutes en tapant `99`.

### 2.3 Anti-rejeu : le compteur

Le serveur incrémente un compteur à chaque émission. L'appareil essaie les
compteurs `[dernier_accepté + 1 .. dernier_accepté + 16]` (fenêtre de type
HOTP). Dès qu'un code est accepté, le compteur local **saute à cette valeur** :
tous les codes antérieurs meurent instantanément.

Un code noté sur un papier ne resservira donc jamais, et générer un nouveau
code annule de fait les précédents non consommés.

### 2.4 Péremption hors ligne : la tranche horaire

Une tranche de 30 minutes (12 h pour les codes de secours) entre dans la
signature, avec une tolérance de ± 1 tranche. Même sans réseau, un code cesse
donc de fonctionner au bout d'une heure environ.

Reculer l'horloge de la tablette ne sert à rien : cela ne fait qu'invalider les
codes récents, et le compteur bloque de toute façon le rejeu. Avancer l'horloge
ne permet pas de deviner un code futur, qui reste signé par un secret inconnu.

### 2.5 Résistance à la force brute

| Grandeur | Valeur |
|---|---|
| Espace des étiquettes | 10^7 |
| Combinaisons acceptables simultanément | 16 compteurs × 3 tranches = 48 |
| Probabilité par essai | 4,8 × 10⁻⁶ |

Couplé au **verrouillage progressif de la saisie** — 5 essais → 5 min, 10 → 30
min, 15 → 24 h et alerte parentale — l'attaque n'est pas praticable. Le test
`test_brute_force_resistance` vérifie que 20 000 essais aléatoires n'aboutissent
jamais.

Le compteur d'échecs est **validé en base avant que l'erreur ne soit levée** :
sans cela, l'annulation de transaction rendrait la force brute gratuite. C'est
une subtilité que le test `test_saisie_bloquee_apres_des_codes_errones` couvre.

### 2.6 Deux implémentations, une seule vérité

Le protocole existe en Python (`backend/app/core/unlock_protocol.py`) et en
TypeScript (`shared/src/unlock-protocol.ts`, y compris SHA-256 et HMAC écrits à
la main pour fonctionner sur Hermes sans dépendance native).

`shared/test/run.mjs` rejoue des **vecteurs générés par l'implémentation Python
de référence** : émission, empreintes, acceptations, refus, tolérance
temporelle. Le SHA-256 maison est lui-même comparé à `node:crypto`. Si les deux
portages divergent, le build échoue.

### 2.7 Révocation

Le serveur ne stocke jamais un code en clair, seulement une empreinte
SHA-256. Un parent peut révoquer un code non consommé ; la liste des empreintes
révoquées est poussée à l'appareil à chaque synchronisation, pour le cas hors
ligne. Un code révoqué mais consommé hors ligne est signalé au parent et la
session correspondante peut être écourtée.

---

## 3. Le minuteur

### 3.1 Horloge monotone, pas horloge murale

Le décompte s'appuie sur le temps écoulé depuis le démarrage de l'application
(`performance.now()`), insensible aux réglages système. C'est cette valeur qui
est transmise au serveur, pas l'heure locale.

### 3.2 Garde-fous serveur

- `delta_monotone ≤ delta_serveur × 1,05 + 2 s` — impossible de consommer plus
  de temps qu'il n'en est réellement passé.
- Un recul de l'horloge monotone (`monotonic_rollback`) est traité comme une
  anomalie : on impute le temps serveur écoulé et on baisse l'indice
  d'intégrité de la session.
- Un changement de `boot_id` signale un redémarrage : la base monotone est
  réinitialisée, et le temps écoulé pendant l'absence est imputé si l'écran
  était annoncé allumé.
- L'écart entre l'horloge annoncée par l'appareil et l'horloge serveur est
  mesuré à chaque battement ; au-delà de deux minutes, l'anomalie remonte au
  tableau de bord.

### 3.3 Butoir absolu

Une session dispose d'une fenêtre murale de `durée × 3`. Enchaîner les pauses
pour étaler une heure sur trois jours ne fonctionne pas. Toute lecture de
l'état (tableau de bord, synchronisation d'appareil) ferme au passage une
session dont le butoir est dépassé : une tablette qui ne donne plus signe de
vie ne reste jamais « ouverte » à l'écran du parent.

### 3.4 Hors ligne

L'appareil déclare le temps consommé pendant la coupure. Le serveur le retient,
**borné par le temps réellement écoulé côté serveur** : impossible d'en gagner
en sur-déclarant, impossible d'en rendre en sous-déclarant plus que la réalité.
Une sur-déclaration est comptabilisée comme anomalie.

---

## 4. Identités et cloisonnement

Deux identités distinctes, deux types de jetons :

| | Parent | Appareil enfant |
|---|---|---|
| Authentification | mot de passe (PBKDF2-HMAC-SHA256, 240 000 itérations) ou Firebase | code d'appairage à usage unique |
| Jeton | accès 1 h + rafraîchissement 30 j, **rotation stricte** | jeton long, révocable |
| Portée | son foyer uniquement | son seul enfant |

Un jeton d'appareil ne peut pas piloter le tableau de bord, et un jeton parent
ne peut pas passer une évaluation : les deux cas sont testés. Chaque accès à un
enfant vérifie l'appartenance au foyer — un parent d'un autre foyer reçoit un
403, jamais des données.

Le jeton de rafraîchissement est à usage unique : le réutiliser après rotation
est refusé, ce qui limite la fenêtre d'exploitation d'un jeton volé.

---

## 5. Journal d'audit chaîné

Chaque action sensible (code émis, code consommé, évaluation corrigée, règle
modifiée, carence levée, appareil révoqué) produit un événement contenant
l'empreinte du précédent :

```
hash(n) = SHA-256( n | foyer | acteur | action | cible | charge utile | hash(n-1) )
```

Modifier une ligne casse le contenu ; en supprimer une casse le chaînage. Les
deux cas sont détectés par `verify_chain`, exposé au parent via
`GET /family/audit?verify=true` et affiché sur la page d'accueil du tableau de
bord.

---

## 6. Ce qui reste à durcir

Ces points sont identifiés, non traités, et documentés comme tels :

- **Mode kiosque réel.** L'application ne verrouille pas encore le système
  (Android Device Owner / iOS Screen Time API). Sans cela, l'enfant peut sortir
  de l'application ; le minuteur le détecte et le signale, mais ne l'empêche pas.
- **Attestation d'intégrité de l'appareil** (Play Integrity, DeviceCheck) pour
  refuser un appareil rooté.
- **Limitation de débit par compte**, en plus de la limitation par adresse IP
  déjà en place.
- **Chiffrement au repos** des tracés manuscrits, qui sont des données
  personnelles d'enfants.
- **Rotation du secret d'appareil**, aujourd'hui fixé à l'appairage.
