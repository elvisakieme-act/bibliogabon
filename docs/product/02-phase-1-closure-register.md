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

| # | Point | Pourquoi c'est un défaut | État |
|---|---|---|---|
| A1 | `Author.normalized_name` est renseigné à la main, sans convention | Deux conventions coexistent : les tests écrivent `"nze aline"` (nom de famille d'abord), `seed_demo` et l'API staff écrivent `display_name.lower()` → `"aline nze"`. Le champ pilote `Meta.ordering`, donc la liste d'auteurs d'une bibliothèque nationale est triée de deux façons selon l'origine de la ligne. | ouvert |
| A2 | Sept listes TypeScript recopient des énumérations Python sans garde-fou | `options.ts`, `rightsOptions.ts`, `publicationStatus.ts`, `completeness.ts` reproduisent `Category`, `AccessModel`, `AgreementType`, `WithdrawalRule`, `DocumentAuthor.Role`, `PublicationStatus` et les codes de complétude. Une valeur ajoutée côté serveur devient **non sélectionnable** à l'écran, en silence. Les états et codes dégradent proprement (affichage brut) ; les listes de choix, non. | ouvert |
| A3 | Six avertissements ESLint `react-refresh/only-export-components` | N'affecte que la granularité du rechargement à chaud, mais c'est le dernier bruit qui empêche `npm run lint` d'être silencieux — et un lint bruyant cesse d'être lu. | ouvert |

## Décisions produit ouvertes

| # | Question | Ce qui la bloque | Conséquence actuelle |
|---|---|---|---|
| B1 | Qui peut créer un auteur, et comment traite-t-on les doublons ? | Le registre des contributeurs est commun à tout le catalogue ; l'autorité et la déduplication sont des choix de gouvernance. | `/api/staff/v1/authors/` est en lecture seule. L'écran indique qu'un auteur absent doit être ajouté par la modération. Un co-auteur inconnu du registre bloque le dépôt. |
| B2 | Trie-t-on les auteurs par nom de famille, comme l'usage académique ? | Déduire le nom de famille d'un nom affiché est peu fiable (noms composés, institutions, « Université Omar Bongo »). Cela demanderait un champ `sort_name` distinct. | A1 normalise de façon déterministe sans deviner la structure du nom : l'ordre devient cohérent, sans être savant. |
| B3 | Quel fournisseur S3 héberge les documents privés ? (D007) | Dépend du volume réel et de l'arbitrage souveraineté / coût de bande passante. | Tout parle S3 via `DOCUMENT_STORAGE_ENDPOINT_URL` ; le choix n'est encodé nulle part. |
| B4 | Le workflow de publication pilote-t-il les dix états de `PublicationStatus` ou les cinq du §8.2 ? | Tranché par la tranche 3 du back-office. | Les dix états existent et sont traduits ; seuls `draft` et `submitted` sont atteignables par l'interface. |

## Reporté en phase 2, sciemment

| # | Point | Raison |
|---|---|---|
| C1 | Les images de page ne sont pas consommées par le lecteur | Elles sont produites et stockées en privé. Le lecteur rend le texte extrait, ce qui suffit à la phase 1. Les servir demande des URL signées (C2). |
| C2 | URL signées à durée de vie courte | Aucune réponse n'expose aujourd'hui de chemin de fichier, ce qui est la garantie forte. Les URL signées sont nécessaires pour C1, pas avant. |
| C3 | Limitation par appareil | Le compteur de sessions et `PageAccessLog` fournissent la matière ; la règle produit reste à définir. |
| C4 | Migration `document_reader.0004` irréversible en pratique | `PageAccessLog.page` est passé de `PROTECT` à `SET_NULL`. Documentée dans l'en-tête de la migration et dans la section de retour arrière de la liste de déploiement. |
