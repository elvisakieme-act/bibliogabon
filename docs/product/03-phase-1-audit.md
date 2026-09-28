# Audit de clôture de la phase 1

Au 28/09/2026. Chaque ligne du plan directeur est confrontée à ce qui existe
réellement, avec la preuve. **Une ligne cochée sur la foi d'une demi-mesure est
exactement ce qui a produit le trou du back-office** : marquée complète sur la
foi de Django Admin, alors que rien n'était prévu.

Trois états, sans troisième voie confortable : **fait**, **partiel** — avec ce
qui manque, nommément — ou **non fait**.

## Les cinq lignes de la roadmap (§ Phase 1)

### 1. « Mettre en place backend, base, stockage, authentification et rôles » — fait

Django 5 / DRF, PostgreSQL en production et SQLite en développement, 62
migrations. Stockage objet derrière `DOCUMENT_STORAGE_BACKEND` : filesystem en
développement, S3 en production, qui **refuse de démarrer sur filesystem**.
Authentification JWT, et sept acteurs projetés sur cinq types de compte plus le
rôle d'adhésion, avec `accounts/permissions.py` comme source unique — les trois
surfaces (API publique, API staff, admin Django) posent la même question.

Trois axes tenus distincts et testés dans les deux sens : l'identité dit qui
s'authentifie, le **rôle** ce qui est permis, l'**habilitation** ce qui est
lisible. Un rôle n'ouvre jamais un document ; une habilitation n'autorise jamais
une action.

**Réserve** : le fournisseur S3 de production n'est pas choisi (D007). Ce n'est
pas un manque de code — rien ne l'encode — mais une décision qui reste à
prendre avant la mise en service.

### 2. « Construire catalogue, comptes, organisations et back-office minimum complet » — fait

Catalogue, comptes et organisations étaient là avant cette séance. Le
back-office, non : il avait été marqué complet sur la foi de Django Admin, qui
expose des clés de stockage et du JSON brut, et où déposer un document demande
cinq formulaires et une commande shell. Il est désormais construit, en quatre
tranches : API staff et dépôt, écrans de dépôt, workflow de validation,
organisations et support.

Dix-neuf écrans et endpoints staff, sous `/gestion` chargé à la demande — un
lecteur ne télécharge jamais ce code, et un test l'atteste après vingt-huit
tâches d'ajouts.

### 3. « Implémenter le dépôt documentaire et le workflow de validation » — fait

Un enseignant dépose sans terminal : brouillon, métadonnées, auteurs, droits,
fichier, soumission. Un modérateur voit la file, décide avec un motif enregistré,
et le journal d'audit est consultable.

Les six états de `PublicationStatus` sont tous atteignables, ce qui n'était pas
le cas : le retrait et l'archivage n'avaient aucun service, et un document
rejeté restait bloqué à vie — trouvé par le parcours manuel, pas par un test
unitaire.

### 4. « Intégrer le traitement asynchrone initial » — fait

Celery derrière Redis, avec chaîne et barrière : découpage, extraction du texte,
OCR, rendu d'image de page, indexation, puis finalisation après la barrière —
l'ordre compte, sinon le texte reconnu par l'OCR n'entre jamais dans l'index.
Vérifié contre un vrai broker et de vrais workers, pas seulement en mode
synchrone : 157 pages traitées, et un cycle de réessai conforme au délai
configuré.

### 5. « Créer les premiers parcours de lecture sécurisée » — fait

Lecture page par page derrière une session à durée de vie limitée, chaque page
revalidant la session **et** l'habilitation, avec journalisation d'accès. Aucun
fichier brut, aucune clé de stockage, aucune URL signée dans une réponse — et
un test balaie cinq réponses pour s'en assurer.

**Réserve explicite** : les URL signées et les images de page dans le lecteur
sont en phase 2, ce que le plan directeur prévoit lui-même (« Stabiliser les
droits d'accès, sessions et URLs signées » y figure).

## Les cinq puces du §8.2

| Puce | État | Preuve, ou ce qui manque |
|---|---|---|
| Documents, auteurs, domaines, collections, statuts | **fait** | Écrans de liste et de fiche, registre d'auteurs, six états traduits |
| Workflow de validation : brouillon, en vérification, publié, retiré, archivé | **fait** | D014 : six valeurs, plus le rejet. File de revue, décision motivée, retrait et archivage audités |
| Gestion des droits : dépôt volontaire, fonds institutionnel, travaux étudiants, contenus ouverts | **fait** | Cinq types d'accord, séparation des pouvoirs structurelle — le déposant déclare, le modérateur décide, et le sérialiseur de déclaration n'expose pas les champs de décision |
| Organisations : quotas, utilisateurs rattachés, contrats, rapports d'usage | **fait** | Écrans membres / quotas / rapport, cadrage inter-organisations éprouvé en accès croisé |
| Support, signalement de document, demandes de retrait | **fait** | Trois catégories distinctes, deux entrées publiques, file de triage |

## Ce qui n'est pas fait, et doit être dit

| Point | État | Pourquoi |
|---|---|---|
| Paiements et abonnements (§8.3) | **domaine seul** | `billing/services.py` crée et révoque les habilitations quand un abonnement, un quota ou une campagne s'active. **Aucun endpoint, aucun écran, aucun agrégateur de paiement intégré.** La phase 1 ne nomme pas la facturation dans ses cinq lignes, et le partenaire Mobile Money reste une décision ouverte. |
| Recherche full-text | **substitut** | Une table dénormalisée par document, reconstruite depuis le texte des pages, scorée en Python. Fonctionnelle, non industrielle. Le plan directeur place la recherche full-text en phase 2. |
| Tableau de bord personnel (§8.1) | **partiel** | Favoris et progression de lecture existent. « Téléchargements autorisés » et « abonnements » n'ont ni endpoint ni écran — le premier dépend des URL signées (phase 2), le second de la facturation. |
| EPUB | **non fait** | Aucune prise en charge. Le plan directeur place « industrialiser l'ingestion PDF/EPUB » en phase 2. |
| URL signées, images de page dans le lecteur, limites par appareil | **non fait, assumé** | Phase 2 dans le plan directeur lui-même. Les images de page sont produites et stockées en privé ; le lecteur rend le texte extrait. |
| Limitation de débit sur les endpoints publics de signalement | **non fait, noté** | Appartient au durcissement de lancement. Écrit dans le module plutôt que corrigé à moitié. |
| Observabilité | **partiel** | Journalisation applicative configurée, journal d'audit immuable et consultable, runbooks de sauvegarde / restauration / incident. Aucune métrique ni trace exportée vers un système de supervision. |

## Ce que la vérification a réellement couvert

**750 tests backend** avec `REQUIRE_OCR=1` et **aucun sauté** — l'OCR tourne
pour de vrai en CI. **159 tests frontend.** Ruff, Prettier, ESLint et TypeScript
silencieux ; `makemigrations --check` propre.

Trois garde-fous lisent le frontend depuis les tests backend, sans exécuter
TypeScript, et **échouent au lieu de sauter** si un chemin est faux : parité des
énumérations, parité des types de réponse, étanchéité des deux schémas OpenAPI.
Ils existent parce que les écrans sont testés sur des stubs, et qu'un stub qui
ment laisserait tout au vert.

Quatre parcours manuels contre un serveur réel — 30, 33, 30 et 32 vérifications.
Ils ont trouvé ce qu'aucun test unitaire ne voyait : un document rejeté bloqué à
vie, et un seed qui ne réparait pas les comptes qu'il prétendait garantir.

## Ce que je n'affirme pas

Ce système n'a **jamais tourné en production**, ni sous charge réelle, ni sur
PostgreSQL en conditions réelles. Les mesures de performance citées viennent
d'une machine de développement. Aucun document réel du catalogue gabonais n'a
été ingéré. Aucun utilisateur réel n'a utilisé un écran.

La phase 1 est close au sens où **ses cinq lignes sont livrées et vérifiées**,
pas au sens où le produit serait éprouvé.
