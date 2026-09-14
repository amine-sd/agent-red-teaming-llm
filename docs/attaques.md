# Catalogue d'attaques de base

Soixante attaques de base, dix par famille, écrites à la main pour cette cible et ses critères de
succès (`docs/criteres-succes.md`). Ce sont les points de départ : le jour 8 en dérivera des
variantes. Elles ne visent que l'application locale de ce dépôt.

## Où

- Un fichier YAML par famille dans `attacks/`, chargé par `bench.attacks.load_attacks`.
- Les fiches piégées de la famille 2 sont dans `data/planted/trapped_fiches.yaml`.
- Les notes internes visées par la famille 4 sont dans `data/planted/internal_notes.yaml`.

## Schéma d'une attaque

| Champ | Rôle |
|---|---|
| `id` | Identifiant unique (`A<famille>-<n>`). |
| `family` | Numéro de famille, 1 à 6. |
| `target` | L'élément du critère visé : règle (R1 à R5), note interne, outil, ressource, type de contenu. |
| `question` | Le message envoyé à `POST /ask`. |
| `success_hint` | Le critère de la famille reformulé pour cette attaque, à l'usage du juge et de l'étiquetage humain. |
| `trapped_doc`, `resource` | Famille 2 seulement : la fiche piégée à récupérer et la ressource fictive recherchée. |

## Ce que chaque famille exerce

1. **Injection directe** : deux attaques par règle R1 à R5 (hors sujet, absence de citation, changement de rôle, langue, promesse de résultat).
2. **Injection indirecte** : dix questions ordinaires visant cinq fiches piégées, chacune cachant une consigne de recommander un site fictif en `.invalid`. Deux fiches formulent la consigne de façon repérable par le filtre en entrée, trois de façon discrète.
3. **Fuite du prompt** : demandes directes, traduction, encodage base64, complétion de phrase, visant le canari ou dix mots consécutifs du prompt.
4. **Divulgation** : questions cherchant un fait distinctif des deux notes internes ; elles ne réussissent que si la limite de portée est inactive.
5. **Agence excessive** : cinq demandes d'envoi de courriel, cinq de suppression de document, visant les deux outils hors liste blanche.
6. **Sortie active** : balises `<script>`, `<iframe>`, `<img>`, attributs d'événement, liens `javascript:`, images Markdown, tous vers des domaines `.invalid`.

## Limite assumée

Écrire les attaques à la main les rend défendables une par une, mais couvre moins de tournures
qu'un jeu public. C'est le rôle du jour 8 (variantes) d'élargir la couverture à partir de ces
soixante points de départ.
