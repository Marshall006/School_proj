# Feuille de route

## Livré

- Double mécanisme de déverrouillage : code parental direct, ou évaluation réussie.
- Protocole de code vérifiable **hors ligne**, non rejouable, résistant à la
  manipulation d'horloge, avec verrouillage progressif de la saisie.
- Minuteur sur horloge monotone, pause écran éteint, butoir absolu,
  réconciliation hors ligne, détection d'anomalies.
- Temps de carence après échec, avec correction détaillée, diagnostic de
  l'erreur et notions à réviser ; escalade paramétrable ; levée possible par le
  parent.
- Moteur adaptatif : estimation de maîtrise, répartition 40 / 40 / 20,
  répétition espacée, calibrage des items en retour.
- Points d'expérience à rendement décroissant, convertibles en minutes, plafonnés.
- Onze types de questions ; saisie assistée (pavé, fractions, potence de
  division, opération posée) **et** ardoise manuscrite avec validation parentale.
- Banque de 3 232 questions, 4 pays, 6 matières, localisée (monnaie, prénoms,
  repères historiques et géographiques).
- Tableau de bord parental : état temps réel, réussite par matière, lacunes
  classées, temps consommé, signaux de contournement, copies à valider,
  réglages par période, calendrier scolaire.
- Journal d'audit chaîné, vérifiable par le parent.
- Authentification locale et Firebase (optionnelle), rotation stricte des jetons.

---

## V2 — les deux évolutions annoncées au cahier des charges

### Génération d'exercices adaptatifs équilibrés

**Déjà en place pour l'essentiel.** Le moteur cible les lacunes tout en révisant
les acquis, et vise ~75 % de réussite attendue plutôt que la difficulté
maximale. Ce qui reste :

- générer des **variantes** d'un même item plutôt que piocher dans une banque
  finie (pour les mathématiques, le squelette existe déjà dans les générateurs) ;
- suivre la lassitude : varier les formats quand une notion revient souvent ;
- exposer au parent une explication en clair de la composition de chaque épreuve.

### Évaluations vocales (lecture, langues vivantes)

L'infrastructure est posée : le type `VOICE` existe, il part en validation
humaine par défaut. Restent :

- capture et transmission de l'audio depuis l'application enfant ;
- reconnaissance et notation (fluidité, exactitude) via un service tiers, avec
  repli sur l'écoute par le parent ;
- **protection des données** : l'audio d'un enfant est une donnée sensible, à
  chiffrer au repos et à purger automatiquement.

---

## Durcissement technique

- **Mode kiosque réel** (Android Device Owner, iOS Screen Time API) : c'est la
  brique manquante la plus importante. Aujourd'hui le contournement est
  *détecté et signalé*, pas *empêché*.
- Attestation d'intégrité de l'appareil, pour refuser un appareil rooté.
- Notifications poussées vers le parent : évaluation réussie, copie à valider,
  anomalie détectée.
- Limitation de débit par compte, en plus de la limitation par adresse IP.
- Chiffrement au repos des tracés manuscrits.
- Rotation du secret d'appareil.
- Tâches de fond planifiées plutôt que `python -m app.cli housekeeping` manuel.

## Produit

- Reconnaissance d'écriture sur l'appareil, pour réduire les validations
  parentales sans jamais pénaliser l'enfant.
- Export PDF du bilan de période, pour le montrer à un enseignant.
- Plusieurs parents par foyer avec rôles distincts (le modèle le prévoit déjà :
  propriétaire, tuteur, lecteur).
- Import du calendrier scolaire officiel par pays et par zone.
- Accessibilité : dyslexie (police, interlignage), synthèse vocale des énoncés,
  temps majoré paramétrable.

## Pédagogie

- **Relecture des 3 232 items par des enseignants** de chaque pays. Le contenu
  livré est généré : il est cohérent et vérifié mécaniquement, mais il n'a pas
  été validé par des professionnels de terrain.
- Affiner la table d'équivalence entre systèmes scolaires
  (`app/content/catalog.py`), aujourd'hui une approximation assumée.
- Étendre au collège (5e → 3e) et à d'autres pays francophones.
- Mesurer l'effet réel : est-ce que le niveau progresse, ou seulement le temps
  passé sur l'application ? C'est la seule question qui compte vraiment.
