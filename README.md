# Agent de red teaming d'une application LLM

[![CI](https://github.com/amine-sd/agent-red-teaming-llm/actions/workflows/ci.yml/badge.svg)](https://github.com/amine-sd/agent-red-teaming-llm/actions/workflows/ci.yml)

> Une défense non testée reste une illusion, et une défense qui bloque tout n'en est pas une.

Ce projet construit une petite application LLM munie de quatre garde-fous, un agent qui les attaque
méthodiquement, et surtout une mesure crédible de **ce qui a réellement tenu, et à quel prix**.

> **Cadre d'usage.** La seule cible est l'application construite dans ce dépôt : elle tourne en
> local, sans donnée personnelle et sans utilisateur tiers. C'est un travail défensif. Les attaques
> ne visent aucun service tiers, aucune API commerciale, aucun système extérieur au projet.

> **Statut : en construction.** Aucun résultat n'est encore publié. Les tableaux de résultats
> apparaîtront ici quand le banc d'essai tournera.

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

Un agent attaquant part de soixante attaques de base, en génère des variantes, les envoie, lit la
réponse et fait monter la sévérité quand une variante passe.

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

## Ce qui est mesuré

| Mesure | Question |
|---|---|
| Taux de contournement | Quel garde-fou cède, et sur quelle famille ? |
| Faux positifs | Sur trente requêtes légitimes, combien la défense en bloque-t-elle à tort ? |
| Stabilité | La même attaque rejouée donne-t-elle le même verdict ? |

Le taux de faux positifs est **toujours rapporté à côté du taux de contournement** : tout le monde
mesure les attaques qui passent, presque personne ne mesure ce que la défense coûte en utilité.

## Pile technique

Python, FastAPI pour l'application cible, recherche lexicale BM25 dans les fiches, Ollama pour
servir les modèles en local. Attaques et
requêtes bénignes en YAML, banc d'essai en pytest, rapport en Markdown.
