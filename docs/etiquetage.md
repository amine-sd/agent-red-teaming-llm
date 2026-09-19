# Étiquetage humain (jour 11)

La valeur du projet tient à la crédibilité du verdict. Pour la mesurer, il faut une vérité terrain
construite à la main, indépendante du juge modèle. C'est l'objet de cette journée : **50 cas
étiquetés par un humain, à l'aveugle.**

## Le protocole

- **Support** : `data/labels_humains.yaml`, généré par `python -m bench.sample_labels`. Cinquante
  cas tirés parmi les 60 attaques de base, **stratifiés par famille et par verdict** (environ 8 par
  famille, avec un mélange de cas que la mesure mécanique dit réussis et échoués). Sans ce mélange,
  l'accord ne voudrait rien dire si une famille était presque toujours du même verdict.
- **À l'aveugle** : la feuille montre le critère, la preuve, la question et la réponse, exactement
  ce que le juge a vu. Elle ne montre **jamais** l'avis du juge ni le verdict mécanique. Regarder
  l'un ou l'autre avant d'avoir fini rendrait la mesure circulaire.
- **Trois valeurs** : `réussi`, `échoué`, `incertain`. `incertain` seulement en cas de doute réel.
- **Ne remplir que** les champs `verdict` et `note` de chaque cas. `note` est facultatif : une
  raison courte, précieuse au jour 12 pour comprendre les désaccords.

## Pourquoi à la main, et pas par un modèle

Étiqueter avec un modèle, puis comparer ces étiquettes à celles d'un autre modèle (le juge), serait
circulaire : on mesurerait l'accord de deux modèles, pas la justesse du juge. Les 50 verdicts
viennent donc de l'humain, sans exception. C'est une règle du projet.

## Après l'étiquetage

Le jour 12 lit `data/labels_humains.yaml`, le compare aux verdicts du juge (`results/judge/base/`)
et calcule l'accord (Cohen kappa et son intervalle de confiance), publié quel qu'il soit. Les
désaccords servent à corriger la grille du juge, puis on remesure sur une part des cas gardée de
côté, pour ne pas surapprendre.
