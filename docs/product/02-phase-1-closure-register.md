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
| A8 | Le lecteur aplatissait tout document (C1, sorti du report) | Il servait le texte extrait sans mise en forme : titres, colonnes, tableaux, figures et formules disparaissaient, les retours à la ligne du PDF étaient conservés — un téléphone repliait donc le texte deux fois — et l'en-tête courant comme le numéro de page entraient dans le corps. L'image de la page était pourtant produite à chaque ingestion et jamais servie, alors que son propre docstring annonçait qu'elle « n'est servi qu'à travers une session de lecture autorisée ». Le lecteur affiche désormais l'image, avec une couche texte transparente alignée au mot près. | Vingt-quatre tests backend et dix frontend. L'image exige une session vivante et un droit valide — la **même** fonction d'autorisation que le texte, jamais réécrite — journalise chaque remise, et porte `private, no-store` là où la couverture porte `public`. Cinq mutations vérifiées côté serveur (journal retiré, autorisation sautée, cache rendu public, session d'autrui non vérifiée, clé de stockage en en-tête), cinq côté écran. |
| A9 | Le motif de report de C1 était faux | Le registre disait que servir les images « demande des URL signées ». L'endpoint de couverture prouvait déjà le contraire : une vue qui diffuse un flux par un chemin opaque suffit, et contrôle l'autorisation à chaque requête — ce qu'une URL signée, une fois émise, ne fait plus. C1 a été traité sans URL signée ; C2 est reformulé. | Deux tests comparent la réponse aux **vraies** valeurs de l'objet stocké : ni clé, ni seau, ni chemin ne sortent, ni dans l'URL ni dans les en-têtes. |
| A10 | Le texte et les positions venaient de deux bibliothèques | L'extraction lisait le texte avec pypdf ; les positions n'existaient pas. Y ajouter PyMuPDF pour les seules positions aurait fait décrire la même page par deux extracteurs, et un lecteur aurait pu sélectionner un mot absent du texte indexé. Une seule passe PyMuPDF donne les deux. Les deux extracteurs ont été comparés sur 160 pages réelles avant l'échange : les écarts étaient uniquement des espaces (similarité 0,998). | Un test exige que chaque mot positionné figure dans le texte stocké, et un autre que la couche et le texte racontent la page dans le même ordre. Une première version vérifiait que les ordonnées croissaient : elle passait sur une page à une colonne et aurait échoué sur la première thèse en deux colonnes — elle décrivait la fixture, pas le système. |
| A11 | Le comptage des pages lues aurait doublé | `page_view_count` compte les lignes du journal, et le lecteur demande désormais deux représentations d'une même page. Tous les rapports institutionnels auraient doublé, sans erreur, sans alerte et sans possibilité de reconstituer les chiffres. L'agrégation dédoublonne par (session, page) ; le journal, lui, garde tout, parce que l'audit ne doit pas dépendre de la représentation demandée. | Quatre tests, dont un dans la direction opposée : deux lecteurs d'une même institution sur une même page comptent bien deux fois. Trois mutations vérifiées — pas de dédoublonnage, dédoublonnage par page seule, dédoublonnage par session seule. Corrige au passage un défaut antérieur : feuilleter en arrière gonflait le compte. |
| A12 | Le texte de tout document était copiable | La couche texte que j'avais construite pour l'accessibilité rendait aussi copiable un mémoire entier, et je ne l'avais pas signalé — une plateforme qui héberge des travaux sous accord de droits ne peut pas laisser faire Ctrl+A / Ctrl+C. La politique suit désormais l'accord signé : licence ouverte → copie libre ; tout autre accord → copie bloquée, sans rien retirer aux lecteurs d'écran ni à la recherche dans la page ; clause de confidentialité → le serveur n'envoie aucune position. | Douze tests, dont un qui vérifie que la politique **agit** et ne se contente pas de se déclarer, et un qui exige qu'un document sans accord de droits ne soit pas le plus permissif du catalogue — se tromper vers « protégé » gêne un lecteur, se tromper vers « libre » trahit un déposant. Quatre mutations vérifiées. Dit sans détour dans le code : bloquer la sélection dissuade, ne protège pas. |
| A13 | Une balise `<img>` ne peut pas s'authentifier | Le lecteur demandait l'image de page par `<img src>`, qui n'envoie aucun en-tête : **toutes** les pages d'un lecteur connecté revenaient en 403, et la page s'effondrait sans hauteur ni message. Aucun test ne pouvait le voir — le client de test authentifie la requête, et une vérification en ligne de commande pose l'en-tête à la main. Il a fallu installer un navigateur et regarder l'écran. | L'image est récupérée comme toute autre ressource, avec le jeton, et remise au navigateur en `blob:`. Trois tests : l'en-tête part bien (et non pas seulement la bonne adresse), l'adresse `blob:` est révoquée à la sortie, et la requête attend l'hydratation de la session — sans quoi elle partait avant que le jeton soit connu. Le cadre garde le format d'une page même sans image, et dit pourquoi elle manque. |
| A14 | La page « courante » était la dernière annoncée | Tous les emplacements se déclarent visibles au premier rendu : le lecteur affichait « 3 / 3 » à l'ouverture d'une thèse de trois pages. Ce n'est pas qu'un compteur — c'est aussi la page enregistrée comme progression de lecture. La page retenue est désormais la **plus visible**, groupée par image d'animation. | Quatre tests. Un défaut a été trouvé en les écrivant : je stockais l'identifiant rendu par `requestAnimationFrame` pour savoir si un rendu était programmé, mais cet identifiant n'est affecté qu'**après** l'appel — une implémentation qui exécute tout de suite laissait derrière elle une valeur qui bloquait toutes les mesures suivantes. Un drapeau a remplacé l'identifiant. |

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
| C2 | URL signées à durée de vie courte | Aucune réponse n'expose de chemin de fichier : les images sont diffusées par des vues qui contrôlent la session et le droit à chaque requête. Les URL signées restent utiles le jour où un CDN servira ces objets ; elles ne conditionnent rien aujourd'hui. |
| C3 | Limitation par appareil | Le compteur de sessions et `PageAccessLog` fournissent la matière ; la règle produit reste à définir. |
| C4 | Migration `document_reader.0004` irréversible en pratique | `PageAccessLog.page` est passé de `PROTECT` à `SET_NULL`. Documentée dans l'en-tête de la migration et dans la section de retour arrière de la liste de déploiement. |
