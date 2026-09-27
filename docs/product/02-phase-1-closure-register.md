# Clôture de la phase 1 — registre des points ouverts

Ce document existe pour qu'aucun point repéré ne se perde. **La phase 1 ne
peut être déclarée close qu'avec la section « À traiter » vide.**

Trois catégories, délibérément distinctes :

- **À traiter** — de la dette ou une incohérence. Se corrige, ne se discute pas.
- **Décision produit ouverte** — l'implémentation est bloquée par un arbitrage
  qui n'appartient pas au développeur. Se tranche, et rejoint alors le
  registre de décisions.
- **Reporté en phase 2, sciemment** — hors du périmètre annoncé de la phase 1,
  avec la raison.

Un relevé systématique de la base (marqueurs `TODO`, `FIXME`, `@ts-ignore`,
`type: ignore`, `any`, tests sautés) ne remonte **rien** au 27/09/2026 : le
seul `skipif` est le marqueur tesseract, et `REQUIRE_OCR=1` le transforme en
échec en CI. Ce qui suit vient donc de la lecture, pas des marqueurs.

## À traiter

*Vide.* Les trois points ouverts au 27/09/2026 sont traités — voir « Traité »
ci-dessous. Un nouveau point se rajoute ici dès qu'il est repéré, et n'en sort
qu'avec un test qui l'empêche de revenir.

## Traité

| # | Point | Correction | Ce qui l'empêche de revenir |
|---|---|---|---|
| A1 | `Author.normalized_name` écrit à la main, sous deux conventions | Le champ est dérivé de `display_name` par `Author.save()` : minuscules, accents dépliés, espaces normalisés. Migration de données `catalog.0005` pour les lignes existantes. Les deux appelants qui le calculaient ne le font plus. | Neuf tests, dont un qui passe une valeur à l'ancienne et vérifie qu'elle est ignorée, et un qui verrouille l'ordre de tri. La limite de `bulk_create` — qui ne passe pas par `save()` — est documentée sur le modèle **et** couverte par un test qui échoue si elle disparaît, pour qu'elle reste visible. |
| A2 | Sept listes TypeScript recopiant des énumérations Python | Un test backend lit les fichiers du frontend et vérifie que chaque valeur d'énumération y figure. Grossier — il n'exécute pas TypeScript — et suffisant pour que la dérive échoue en CI. | Huit cas paramétrés. Vérifié dans les deux sens : retirer une valeur de l'écran échoue, ajouter une valeur au serveur sans mettre l'écran à jour échoue aussi. Un chemin frontend introuvable **échoue** au lieu de sauter, pour que le garde-fou ne disparaisse pas à la première réorganisation. |
| A3 | Six avertissements ESLint `react-refresh/only-export-components` | Cinq fichiers mélangeaient composants et valeurs. `useAuth`, `AuthContext`, `documentReadLabel`, `documentDetailReadLabel`, `fieldErrorId`/`fieldErrorProps` et `NotFoundPage` ont chacun leur module. | `npm run lint` est silencieux : zéro erreur, zéro avertissement. Un nouveau mélange se signalera donc immédiatement, au lieu de se perdre dans le bruit. |

## Décisions produit ouvertes

| # | Question | Ce qui la bloque | Conséquence actuelle |
|---|---|---|---|
| B1 | Qui peut créer un auteur, et comment traite-t-on les doublons ? | Le registre des contributeurs est commun à tout le catalogue ; l'autorité et la déduplication sont des choix de gouvernance. | `/api/staff/v1/authors/` est en lecture seule. L'écran indique qu'un auteur absent doit être ajouté par la modération. Un co-auteur inconnu du registre bloque le dépôt. |
| B2 | Trie-t-on les auteurs par nom de famille, comme l'usage académique ? | Déduire le nom de famille d'un nom affiché est peu fiable (noms composés, institutions, « Université Omar Bongo »). Cela demanderait un champ `sort_name` distinct. | **A1 rend l'ordre cohérent, pas savant** : il porte sur le nom affiché, donc « Aline NZE » se classe sous A et non sous N. Un test le dit explicitement. Trancher B2 demanderait un champ dédié et une règle de saisie. |
| B3 | Quel fournisseur S3 héberge les documents privés ? (D007) | Dépend du volume réel et de l'arbitrage souveraineté / coût de bande passante. | Tout parle S3 via `DOCUMENT_STORAGE_ENDPOINT_URL` ; le choix n'est encodé nulle part. |
| B4 | Le workflow de publication pilote-t-il les dix états de `PublicationStatus` ou les cinq du §8.2 ? | Tranché par la tranche 3 du back-office. | Les dix états existent et sont traduits ; seuls `draft` et `submitted` sont atteignables par l'interface. |

## Reporté en phase 2, sciemment

| # | Point | Raison |
|---|---|---|
| C1 | Les images de page ne sont pas consommées par le lecteur | Elles sont produites et stockées en privé. Le lecteur rend le texte extrait, ce qui suffit à la phase 1. Les servir demande des URL signées (C2). |
| C2 | URL signées à durée de vie courte | Aucune réponse n'expose aujourd'hui de chemin de fichier, ce qui est la garantie forte. Les URL signées sont nécessaires pour C1, pas avant. |
| C3 | Limitation par appareil | Le compteur de sessions et `PageAccessLog` fournissent la matière ; la règle produit reste à définir. |
| C4 | Migration `document_reader.0004` irréversible en pratique | `PageAccessLog.page` est passé de `PROTECT` à `SET_NULL`. Documentée dans l'en-tête de la migration et dans la section de retour arrière de la liste de déploiement. |
