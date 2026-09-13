# Agent de red teaming d'une application LLM

> **Cadre d'usage.** Ce dépôt attaque **une seule cible : une application écrite par son auteur,
> qui tourne en local, sans donnée personnelle et sans utilisateur tiers**. C'est un travail
> défensif : on mesure des garde-fous pour savoir lesquels tiennent. Les attaques sont conçues
> pour cette application. Elles ne visent aucun service tiers, aucune API commerciale, aucun
> système qui n'appartient pas à l'auteur.

**Thèse.** Une défense non testée reste une illusion : ce projet attaque méthodiquement les
garde-fous d'une application LLM locale, puis mesure, avec un juge calibré sur des verdicts
humains, ce qui a réellement tenu et ce que la défense coûte en utilité.

*État : en construction, jour 1 sur 16. Aucun résultat n'est encore publié.*

## Architecture

```
CIBLE      assistant local sur les fiches pratiques Service-Public
           4 garde-fous : filtre en entrée, filtre en sortie,
           liste blanche d'outils, limite de portée
              |
ATTAQUANT  agent qui génère des variantes par famille,
           les envoie, lit la réponse, fait monter la sévérité
              |
JUGE       modèle qui décide si l'attaque a réussi,
           calibré sur 50 cas étiquetés à la main
              |
BANC       60 attaques, 6 familles, plus 30 requêtes bénignes
```

## Les six familles d'attaque

Tirées du OWASP Top 10 pour les applications LLM, restreintes à ce qui est testable sur une
petite application :

1. **Injection de prompt directe** : instructions contradictoires dans la requête.
2. **Injection indirecte** : instructions cachées dans un document du corpus.
3. **Fuite du prompt système.**
4. **Divulgation d'information sensible** : faire ressortir un document hors périmètre.
5. **Agence excessive** : faire appeler un outil qui n'aurait pas dû l'être.
6. **Sortie non maîtrisée** : faire produire un contenu que le filtre de sortie devait bloquer.

## Les trois mesures

- **Taux de contournement**, par garde-fou et par famille.
- **Faux positifs** sur trente requêtes bénignes : le prix de la défense en utilité.
- **Stabilité** : la même attaque rejouée donne-t-elle le même verdict ?

L'accord entre le juge et l'humain sera publié avec les résultats, quel qu'il soit.

## Corpus

La cible indexe les
[fiches pratiques Service-Public.gouv.fr Particuliers](https://www.data.gouv.fr/datasets/fiches-pratiques-et-ressources-de-service-public-gouv-fr-particuliers),
publiées sous Licence Ouverte 2.0. Source des données : Service-Public.gouv.fr / DILA. Le fichier
exact et sa date seront indiqués ici au moment du téléchargement.

L'application n'est affiliée ni à Service-Public.gouv.fr ni à la DILA : elle réutilise leurs
données ouvertes comme corpus de test. Quelques documents **fictifs**, signalés comme tels, y
seront ajoutés pour les familles 2 et 4. Ils ne contiennent aucune donnée personnelle.

## Pile technique

Python, FastAPI pour la cible, modèles servis en local par Ollama. Attaques et requêtes bénignes
en YAML, banc en pytest, rapport en Markdown.
