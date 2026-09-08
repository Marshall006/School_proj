# Pédagogie

Le produit repose sur une idée simple : **si l'écran se mérite, alors
l'évaluation doit être juste**. Une épreuve trop dure décourage, une épreuve
trop facile ne prouve rien, et une correction qui dit seulement « faux » ne fait
pas progresser. Ce document explique les trois mécanismes qui répondent à ces
trois risques.

---

## 1. Estimer le niveau plutôt que compter les points

Un pourcentage de réussite ignore que les questions n'ont pas la même
difficulté. KODA maintient donc, pour chaque couple (enfant, notion) :

| Grandeur | Rôle |
|---|---|
| `ability` | Aptitude sur une échelle logistique, façon Elo |
| `ewma` | Moyenne mobile exponentielle des réussites récentes |
| `band` | Palier lisible : fragile / en cours / acquis / expert |
| `ease`, `interval_days`, `next_review_at` | Répétition espacée (SM-2 allégé) |

La probabilité de réussite prédite est

```
p = 1 / (1 + exp(-(aptitude - difficulté) / 0,9))
```

et l'aptitude s'ajuste après chaque réponse d'un pas `K · (score - p)`, avec un
`K` **décroissant** : le modèle apprend vite au début, puis se stabilise. Un
enfant n'est donc pas étiqueté pour de bon sur trois mauvaises réponses.

La difficulté des items se calibre en retour : un item réussi plus souvent que
prévu voit sa difficulté empirique baisser. La banque s'auto-corrige à l'usage.

---

## 2. Composer une épreuve qui fait progresser sans décourager

Une épreuve composée uniquement de lacunes est une punition déguisée. Chaque
évaluation mélange donc trois intentions :

| Bloc | Part | Contenu | Réussite visée |
|---|---|---|---|
| Remédiation | 40 % | notions fragiles ou en retard de révision | 80 % |
| Apprentissage | 40 % | programme en cours d'acquisition | 70 % |
| Consolidation | 20 % | notions acquises, pour entretenir la confiance | 88 % |

La difficulté visée n'est jamais le maximum : on cherche la zone où l'effort est
réel mais la réussite plausible. Pour chaque créneau, le moteur choisit l'item
dont la difficulté colle le mieux à la cible, en **évitant les questions vues
récemment**.

Si un bloc est vide — aucune lacune connue, tant mieux — sa part est
redistribuée au prorata sur les autres. Le total demandé est toujours atteint.

Le tirage est **reproductible** : à graine égale, épreuve égale. Indispensable
pour les tests, et pour rejouer une épreuve contestée.

Le parent peut infléchir l'ensemble d'un curseur « exigence », qui déplace la
réussite visée sans toucher à la structure.

---

## 3. Corriger utilement

### Tolérance de saisie

Un enfant qui écrit `0,75`, `3/4`, `75 %` ou `.75` a la même réponse juste. Le
correcteur normalise :

- virgule française et point décimal ;
- fractions et nombres mixtes (`1 1/2`) ;
- pourcentages ;
- espaces de milliers, y compris insécables ;
- unités en suffixe (`12 cm`, `2,5 kg`) ;
- accents, casse et ponctuation pour le texte, avec distance d'édition
  paramétrable par item.

Une virgule mal placée par le clavier ne doit jamais coûter un point.

### Crédit partiel

QCM à choix multiples (bonnes cases moins mauvaises), textes à trous, remise en
ordre (paires consécutives correctes), associations : le score est continu, pas
binaire.

### Diagnostic

Quand c'est possible, le correcteur ne dit pas seulement « faux » mais
*pourquoi* :

| Écart observé | Message rendu à l'enfant |
|---|---|
| Résultat 10 fois trop grand | « Ta réponse est 10 fois trop grande : vérifie la virgule ou les zéros. » |
| Signe inversé | « Le résultat est bon mais le signe est inversé. » |
| Fraction inversée | « Tu as inversé le numérateur et le dénominateur. » |
| Écart d'une unité | « Il ne manque qu'une unité : vérifie ta retenue. » |
| Seuls les accents diffèrent | « C'est le bon mot : il ne manque que les accents. » |
| Une lettre de différence | « Relis l'orthographe. » |
| Mots dans le désordre | « Tous les mots y sont, mais l'ordre n'est pas le bon. » |

C'est ce qui rend le temps de carence formateur plutôt que punitif.

### La machine ne pénalise jamais une écriture

Pour une réponse posée sur l'ardoise :

1. si la transcription est lisible et juste → validée automatiquement ;
2. si elle est douteuse → la copie part en **validation parentale** ;
3. **mais** si le score déjà acquis suffit à passer le seuil, le code est
   délivré immédiatement — l'enfant n'attend pas ;
4. et si même le meilleur des cas ne suffit pas, l'échec est prononcé tout de
   suite, sans faire patienter inutilement.

Seul le cas réellement indécis attend l'arbitrage d'un adulte.

---

## 4. Les points d'expérience

Ils récompensent l'effort **volontaire** : les évaluations facultatives, celles
qui ne déverrouillent rien.

| Source | Gain |
|---|---|
| Bonne réponse | 10 XP × coefficient de difficulté (0,6 à 1,6), proportionnel au crédit partiel |
| Évaluation réussie | +50 |
| Sans faute | +50 |
| Lacune comblée (changement de palier) | +30 par notion |
| Série de jours consécutifs | +10/jour, plafonné à 50 |

**Rendement décroissant** : au-delà de 300 XP dans la journée le coefficient
tombe à 0,5, au-delà de 600 à 0,25. Enchaîner vingt QCM faciles ne rapporte pas
des heures d'écran ; le test `test_le_farming_ne_paie_pas` verrouille cette
propriété.

La conversion en minutes est fixée par le parent (15 min pour 100 XP par
défaut), plafonnée par jour, et arrondie au pas de 5 minutes imposé par le
protocole de code.

---

## 5. La banque de contenu

**3 232 questions, 348 notions, 6 matières, 4 pays.**

| Pays | Classes couvertes | Questions |
|---|---|---|
| France | CE1 → 6e | ~810 |
| Bénin | CP → CM2 | ~810 |
| Côte d'Ivoire | CP → CM2 | ~805 |
| Sénégal | CP → CM2 | ~805 |

### Les systèmes scolaires ne se superposent pas

Le primaire compte cinq années en France (CP→CM2) et six au Bénin, en Côte
d'Ivoire ou au Sénégal (CI, CP, CE1→CM2). Un **indice de niveau commun** relie
les deux :

```
indice     1     2     3     4     5     6      7    8    9   10
FR         CP    CE1   CE2   CM1   CM2   6e     5e   4e   3e   —
BJ/CI/SN   CI    CP    CE1   CE2   CM1   CM2    6e   5e   4e   3e
```

Le programme est défini une fois par indice, puis instancié par pays. Cette
table d'équivalence est une approximation assumée, isolée dans
`app/content/catalog.py` pour qu'une équipe pédagogique puisse l'affiner sans
toucher au code.

### Localisation réelle, pas cosmétique

- **Monnaie** : un problème d'achat parle d'euros en France et de francs CFA
  ailleurs, avec des ordres de grandeur crédibles (1,50 € → 150 FCFA).
- **Prénoms et lieux** propres à chaque pays.
- **Histoire et géographie** : le royaume d'Abomey et Béhanzin au Bénin,
  Houphouët-Boigny et le cacao en Côte d'Ivoire, Gorée et Lat Dior au Sénégal,
  1789 et Jules Ferry en France.

### Génération, pas recopie

Les mathématiques et la conjugaison sont produites par règles (avec les
irrégularités explicitement listées), ce qui donne des dizaines d'items justes
par classe sans recopier un manuel. Les sciences, l'histoire-géographie,
l'anglais et l'éducation civique sont rédigés à la main.

Chaque question porte une référence stable et le tirage est ensemencé par cette
référence : **relancer le remplissage ne crée aucun doublon et produit
exactement la même banque**.

### Onze types de questions

QCM simple et multiple, vrai/faux, numérique, texte court, texte à trous,
remise en ordre, associations, expression assistée (fractions, opérations
posées), manuscrit, et vocal (prévu en V2).

Chaque item déclare l'interface de saisie à présenter : pavé numérique ou
mathématique, palette de symboles, constructeur de fractions, potence de
division, opération en colonnes, autorisation de l'ardoise. **Le serveur décrit,
le client affiche** — ajouter un gabarit ne demande pas de toucher à
l'application.

### Vérification systématique

Le test `test_la_correction_valide_les_reponses_attendues` prend **chaque item
généré des quatre pays et des cinq niveaux**, construit la réponse attendue à
partir du barème, et vérifie qu'elle est comptée juste — puis qu'une réponse
manifestement fausse est comptée fausse. Plus de 1 000 items sont ainsi validés
à chaque exécution de la suite.

D'autres tests vérifient que les propositions de QCM sont distinctes, que la
bonne réponse figure bien parmi elles, que moins de 2 % des items sont dépourvus
d'explication, et que les gabarits de saisie sont cohérents avec le type de
question.

---

## 6. Le parent complète la banque

Un parent peut ajouter ses propres questions sur n'importe quelle notion — la
leçon du jour, un devoir précis. Elles rejoignent la banque et deviennent
sélectionnables par le moteur adaptatif au même titre que le contenu livré.
