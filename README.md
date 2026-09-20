# Agent de red teaming d'une application LLM

[![CI](https://github.com/amine-sd/agent-red-teaming-llm/actions/workflows/ci.yml/badge.svg)](https://github.com/amine-sd/agent-red-teaming-llm/actions/workflows/ci.yml)

> Une défense non testée reste une illusion, et une défense qui bloque tout n'en est pas une.

Ce projet construit une petite application LLM munie de quatre garde-fous, un agent qui les attaque
méthodiquement, et surtout une mesure crédible de **ce qui a réellement tenu, et à quel prix**.

> **Cadre d'usage.** La seule cible est l'application construite dans ce dépôt : elle tourne en
> local, sans donnée personnelle et sans utilisateur tiers. C'est un travail défensif. Les attaques
> ne visent aucun service tiers, aucune API commerciale, aucun système extérieur au projet.

> **Statut : terminé.** Les résultats ci-dessous portent sur les 60 attaques de base contre la
> cible locale, tranchés par un vérificateur déterministe calibré sur 50 étiquettes humaines. Tout
> est reproductible (voir [Reproduire](#reproduire)).

## Le principe

Une petite application répond à des questions sur les papiers, la citoyenneté et les élections, à
partir des
[fiches pratiques Service-Public.gouv.fr](https://www.data.gouv.fr/datasets/fiches-pratiques-et-ressources-de-service-public-gouv-fr-particuliers)
de ce thème (fiches Particuliers publiées par la DILA sur data.gouv.fr, Licence Ouverte 2.0 ; le
fichier utilisé et sa date figurent dans `data/corpus_manifest.json`). Elle est protégée
par quatre garde-fous, activables séparément : un filtre en entrée, un filtre en sortie, une liste
blanche d'outils et une limite de portée ([détail](docs/garde-fous.md)).

Quelques documents fictifs, signalés comme tels, sont plantés dans le corpus : des consignes
cachées pour l'injection indirecte, et des documents hors périmètre pour la divulgation. Ils ne
contiennent aucune donnée personnelle. L'application n'est affiliée ni à Service-Public.gouv.fr ni
à la DILA.

Un agent attaquant part de soixante attaques de base et en génère des variantes par
transformations, pour trouver une formulation qui passe là où l'attaque de base échouait.

Un juge décide ensuite si chaque attaque a réussi. Ici, la vérité terrain n'existe pas d'avance :
le juge est donc calibré sur cinquante cas étiquetés à la main, et son accord avec l'humain est
publié, quel qu'il soit.

## Les six familles d'attaque

| # | Famille | Ce que l'attaque cherche à obtenir |
|---|---|---|
| 1 | Injection directe | Faire obéir l'application à des instructions contradictoires glissées dans la requête |
| 2 | Injection indirecte | Faire exécuter une consigne cachée dans un document du corpus |
| 3 | Fuite du prompt système | Faire révéler les instructions internes de l'application |
| 4 | Divulgation d'information sensible | Faire ressortir un document hors périmètre |
| 5 | Agence excessive | Faire appeler un outil qui n'aurait pas dû l'être |
| 6 | Sortie non maîtrisée | Faire produire du contenu actif (script, image externe) que le filtre de sortie devait neutraliser |

Elles sont tirées du OWASP Top 10 pour les applications LLM, restreintes à ce qui est testable sur
une petite application. La famille 2 est la plus intéressante : une consigne cachée dans un
document que l'application indexe elle-même, c'est le scénario réaliste, et celui que la plupart
des démonstrations oublient.

## Résultats

Trois mesures, tranchées par le vérificateur mécanique déterministe (voir la calibration
ci-dessous) et régénérables par `make eval` ([rapport.md](rapport.md)). Le taux de faux positifs
est **toujours rapporté à côté du taux de contournement** : mesurer ce que la défense laisse passer
sans mesurer ce qu'elle coûte en utilité ne dit que la moitié de l'histoire.

**Taux de contournement par famille**, sans défense puis avec les quatre garde-fous :

| Famille | Sans défense | Avec les 4 garde-fous |
|---|---|---|
| 1. Injection directe | 6/9 (échantillon humain)* | non mesuré (pas d'étiquette humaine) |
| 2. Injection indirecte | 50 % | 0 % |
| 3. Fuite du prompt | 70 % | 0 % |
| 4. Divulgation | 80 % | 0 % |
| 5. Agence excessive | 70 % | 0 % |
| 6. Sortie active | 60 % | 0 % |

\* Le vérificateur mécanique ne tranche pas la famille 1 (respect des règles, jugement requis) : le
chiffre « sans défense » vient de l'échantillon étiqueté à la main (9 des 10 attaques de la
famille), et la passe défendue n'a pas été étiquetée.

Les garde-fous ramènent le contournement mesurable à **0 %**. Attribution par les événements
journalisés : le filtre de sortie et la limite de portée bloquent 11 attaques chacun, le filtre en
entrée et la liste blanche d'outils 7 chacun.

**Coût de la défense** (30 requêtes bénignes légitimes) :

| Configuration | Questions ordinaires réussies | Pièges refusés à tort |
|---|---|---|
| Sans défense | 60 % | 0 / 5 |
| Avec les 4 garde-fous | 56 % | 4 / 5 |

Aucun garde-fou ne se déclenche sur les questions ordinaires ; le seul coût réel est le filtre en
entrée qui refuse 4 des 5 « pièges » (questions légitimes formulées comme des injections).

**Stabilité** : sur 20 attaques rejouées à température 0,2, **90 %** des verdicts sont identiques
entre deux passes. Le non-déterminisme est un résultat, pas un bruit.

## Calibration du juge

La vérité terrain vient de **50 cas étiquetés à la main, à l'aveugle**. L'accord (Cohen kappa)
mesuré contre ces étiquettes :

| Étalon candidat | kappa avec l'humain |
|---|---|
| Juge LLM `gemma2:2b` | **0,23** (IC 95 % [-0,05 ; 0,49]) |
| Juge LLM, après correction de la grille | 0,49 (sur un jeu tenu à part) |
| Vérificateur mécanique déterministe | **0,90** (IC 95 % [0,74 ; 1,00]) |

Résultat central du projet : **un petit juge LLM est trop instable pour servir d'étalon** (son
intervalle touche zéro), tandis que le vérificateur déterministe atteint 0,90. C'est donc lui qui
tranche les verdicts, l'accord humain le validant. Restructurer la sortie du juge (« critère rempli
oui/non » mappé mécaniquement) monte le kappa de 0,26 à 0,49 sur un jeu jamais touché, sans
surapprentissage, mais ne suffit pas.

## Pile technique

Python, FastAPI pour l'application cible, recherche lexicale BM25 dans les fiches, Ollama pour
servir les modèles en local (`qwen2.5:3b` pour la cible, `gemma2:2b` pour le juge). Attaques et
requêtes bénignes en YAML, banc d'essai en pytest, rapport en Markdown.

## Reproduire

Prérequis : Python 3.11, et Ollama servant `qwen2.5:3b` (cible) et `gemma2:2b` (juge).

```bash
pip install -r requirements.txt
make corpus                                  # télécharge et découpe le corpus Service-Public
python -m bench.attack_runner --config none  # 60 attaques sans défense (référence)
python -m bench.attack_runner --config all   # 60 attaques avec les 4 garde-fous
python -m bench.judge                         # verdict du juge LLM sur les traces
python -m bench.agreement                     # accord juge / mécanique / humain
make eval                                     # produit rapport.md
make test                                     # suite de tests (mode fixtures, sans modèle)
```

Sur une machine modeste, une passe de 60 attaques prend quelques heures ; les bancs reprennent les
requêtes en erreur d'une exécution à l'autre.

## Limites

Elles sont assumées et rapportées, parce que la crédibilité du verdict vaut plus que des chiffres
flatteurs.

- **Cible modeste.** Petit modèle local et recherche lexicale : la cible ne réussit que ~60 % de
  ses propres questions ordinaires. La référence est donc basse, et le taux de contournement de la
  famille 2 (fiches non recommandées) reflète en partie ce défaut de base, pas seulement l'attaque.
- **Juge LLM faible.** `gemma2:2b` n'atteint que 0,23 de kappa (0,49 après correction). C'est le
  vérificateur mécanique, validé à 0,90 sur l'humain, qui sert d'étalon. La famille 1 (respect des
  règles) n'est pas tranchée mécaniquement : elle demande un jugement.
- **Escalade non démontrée.** L'agent qui « pousse plus loin » quand une attaque passe ne bat pas un
  tirage aléatoire sur ce montage : sans défense la cible cède trop facilement, avec défense le
  filtre bloque tout, et le petit modèle ne sait pas contourner finement. Résultat négatif assumé.
- **Attribution par garde-fou** déduite des événements de la passe défendue, pas d'une matrice par
  garde-fou isolé (choix de coût). **Stabilité** mesurée sur 20 attaques, pas 60.
- **Intégration continue en mode fixtures** : elle rejoue le code du banc sur des traces
  enregistrées et un corpus-échantillon, elle ne relance pas l'inférence.
