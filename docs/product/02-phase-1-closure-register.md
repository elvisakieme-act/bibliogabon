# Clôture de la phase 1 — registre des points ouverts

Ce document existe pour qu'aucun point repéré ne se perde. **La phase 1 ne
peut être déclarée close qu'avec la section « À traiter » vide.**

> **Au 28/09/2026 : la section « À traiter » est vide et la phase 1 est
> close.** L'audit ligne par ligne, avec ce qui n'est pas fait, vit dans
> `docs/product/03-phase-1-audit.md`.

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

*Vide.* Un nouveau point se rajoute ici dès qu'il est repéré, et n'en sort qu'avec un
test qui l'empêche de revenir.

## Traité

| # | Point | Correction | Ce qui l'empêche de revenir |
|---|---|---|---|
| A1 | `Author.normalized_name` écrit à la main, sous deux conventions | Le champ est dérivé de `display_name` par `Author.save()` : minuscules, accents dépliés, espaces normalisés. Migration de données `catalog.0005` pour les lignes existantes. Les deux appelants qui le calculaient ne le font plus. | Neuf tests, dont un qui passe une valeur à l'ancienne et vérifie qu'elle est ignorée, et un qui verrouille l'ordre de tri. La limite de `bulk_create` — qui ne passe pas par `save()` — est documentée sur le modèle **et** couverte par un test qui échoue si elle disparaît, pour qu'elle reste visible. |
| A2 | Sept listes TypeScript recopiant des énumérations Python | Un test backend lit les fichiers du frontend et vérifie que chaque valeur d'énumération y figure. Grossier — il n'exécute pas TypeScript — et suffisant pour que la dérive échoue en CI. | Huit cas paramétrés. Vérifié dans les deux sens : retirer une valeur de l'écran échoue, ajouter une valeur au serveur sans mettre l'écran à jour échoue aussi. Un chemin frontend introuvable **échoue** au lieu de sauter, pour que le garde-fou ne disparaisse pas à la première réorganisation. |
| A3 | Six avertissements ESLint `react-refresh/only-export-components` | Cinq fichiers mélangeaient composants et valeurs. `useAuth`, `AuthContext`, `documentReadLabel`, `documentDetailReadLabel`, `fieldErrorId`/`fieldErrorProps` et `NotFoundPage` ont chacun leur module. | `npm run lint` est silencieux : zéro erreur, zéro avertissement. Un nouveau mélange se signalera donc immédiatement, au lieu de se perdre dans le bruit. |
| A4 | Le catalogue n'avait aucune couverture, et n'en avait aucun moyen | `Document` n'a pas de champ de couverture et `"cover": None` était codé en dur à trois endroits, pendant que l'image de la page 1 était produite à chaque ingestion sans jamais être consommée. Elle devient la couverture, servie par un point d'accès opaque (`api/v1/covers.py`). | Dix-huit tests. Un document non publié, privé, inconnu ou sans page rendue renvoie 404 — jamais 403, qui confirmerait l'existence d'un brouillon. Deux tests comparent la réponse aux **vraies** valeurs de l'objet stocké : ni clé, ni seau, ni chemin ne sortent. |
| A5 | La recherche ne portait pas la couverture | Elle a son propre sérialiseur et ne passe pas par `serialize_document_metadata` : l'écran de résultats serait resté entièrement gris pendant que le catalogue affichait ses vignettes. Enrichie dans la couche API, **après** pagination. | Trois tests. Un document indexé mais sans page rendue doit rapporter `null` : sans lui, fabriquer l'adresse pour tout résultat passait la suite entière, puisque la recherche ne renvoie que des documents découvrables. Un test de coût constant échoue à 7 requêtes contre 19 si le groupage disparaît. |
| A6 | La découvrabilité s'écrivait deux fois, mot pour mot | `search_discovery.document_is_discoverable` répétait `document_reader.document_is_reader_accessible`. Deux copies ne divergent pas le jour où on les écrit : elles divergent le jour où un état de publication s'ajoute et qu'un seul fichier est modifié. La première délègue désormais à la seconde — `search_discovery` vient après `document_reader` dans la séquence, donc le sens de dépendance est respecté. | Un test parcourt **tous** les états de publication croisés à **tous** les modèles d'accès et exige la même réponse des deux fonctions. Un état nouveau y entre sans qu'on ait à y penser. |
| A7 | Les types publics n'avaient aucun garde-fou de parité | `test_frontend_type_parity` ne couvrait que `/gestion`. Le pendant public (`api/v1/tests/test_frontend_public_type_parity.py`) confronte huit interfaces aux réponses réelles : catalogue en liste **et** en détail, recherche, domaines, types, session et page de lecture, favoris, profil. Il a trouvé deux écarts dès sa première exécution — `category` absent de `DocumentMetadata`, `document_type` absent de `SearchResult`. | Égalité exacte dans les deux sens, sur un document complet et réellement ingéré — un document dépouillé donnerait une charge dépouillée et la parité passerait sur une réponse que l'écran ne verra jamais. Trois mutations vérifiées : champ retiré du type, champ inventé dans le type, chemin du frontend devenu faux. La troisième **échoue** au lieu de sauter. |

## Décisions produit ouvertes

*Vide.* Les quatre questions ouvertes au 27/09/2026 sont tranchées — voir
ci-dessous. Une nouvelle question se rajoute ici dès qu'elle bloque une
implémentation, et n'en sort qu'avec une entrée au registre de décisions.

## Décisions tranchées

| # | Question | Décision | Consigné |
|---|---|---|---|
| B1 | Qui peut créer un auteur ? | La modération seule. L'ouverture aux déposants remplirait le registre national de doublons, plus coûteux à fusionner qu'un aller-retour. | D015 |
| B4 | Combien d'états pour le workflow ? | Cinq, plus le rejet. Les trois états de revue dupliquaient des barrières tenues ailleurs et mieux ; aucune barrière n'est perdue. | D014 |
| B3 | Quel fournisseur S3 ? | SeaweedFS auto-hébergé. La souveraineté prime sur l'économie d'exploitation d'un service managé. | D016 |
| B2 | Tri académique des auteurs ? | Non : tri par nom affiché. Déduire un nom de famille se tromperait en silence, et un champ dédié n'est pas justifié à cette échelle. | D017 |

## Reporté en phase 2, sciemment

| # | Point | Raison |
|---|---|---|
| C1 | Les images de page ne sont pas consommées par le lecteur | Elles sont produites et stockées en privé. Le lecteur rend le texte extrait, ce qui suffit à la phase 1. Les servir demande des URL signées (C2). |
| C2 | URL signées à durée de vie courte | Aucune réponse n'expose aujourd'hui de chemin de fichier, ce qui est la garantie forte. Les URL signées sont nécessaires pour C1, pas avant. |
| C3 | Limitation par appareil | Le compteur de sessions et `PageAccessLog` fournissent la matière ; la règle produit reste à définir. |
| C4 | Migration `document_reader.0004` irréversible en pratique | `PageAccessLog.page` est passé de `PROTECT` à `SET_NULL`. Documentée dans l'en-tête de la migration et dans la section de retour arrière de la liste de déploiement. |
