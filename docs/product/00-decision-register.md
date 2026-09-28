# BiblioGABON Decision Register

| ID | Date | Decision | Rationale | Impact | Owner |
|---|---|---|---|---|---|
| D001 | 2026-07-27 | Treat the maquette as UI/UX inspiration only | The product must be designed from first principles to avoid biasing scope and architecture | Frontend implementation cannot dictate product scope | Product |
| D002 | 2026-07-27 | Build a complete launchable platform, not an MVP | The concept has already been validated in a challenge | Roadmap must include core platform, business, content, and governance capabilities | Product |
| D003 | 2026-07-27 | Use hybrid monetization: B2B, B2C, sponsored access | This balances institutional revenue, student accessibility, and impact | Billing and organization modules must support several access models | Business |
| D004 | 2026-07-27 | Use Django/PostgreSQL/Redis-Celery/S3-compatible storage as initial backend direction | Existing architecture notes already converge on this pragmatic stack | Subsystem plans should assume this stack until a formal decision changes it | Tech |
| D005 | 2026-07-30 | Build the real web frontend in a clean `frontend/` app while preserving the maquette's UI/UX DNA | The maquette contains strong visual patterns but also mock data, demo flows, and routes outside API V1 scope | Frontend V1 must migrate visual components selectively and rebuild data/auth/routing around `/api/v1/` | Product/Tech |
| D006 | 2026-09-26 | Rebuild the ingestion pillar to its planned shape: Celery workers behind a broker, configurable object storage, OCR, page images | A synchronous stopgap had been written outside any plan and diverged from the pillar on five axes; its only real run had failed | The pipeline becomes asynchronous and replayable; production requires a broker and an S3 backend, and fails to start without them | Tech |
| D007 | 2026-09-26 | *(clos par D016 le 28/09/2026 : SeaweedFS auto-hébergé.)* Keep the S3-compatible provider an open deployment decision, encoded nowhere in the code | Everything talks S3 through `DOCUMENT_STORAGE_ENDPOINT_URL`, so the choice can wait for real volume | Self-hosting favours SeaweedFS (Apache 2.0, built for many small files — page rendering produces ~150 objects per document); a managed zero-egress service such as R2 removes operations work and attacks the bandwidth-cost risk, at the price of the sovereignty principle | Product/Tech |
| D008 | 2026-09-27 | Give the Content Admin its own account type, distinct from Platform Staff | Its remit is bounded — metadata, rights, status, publication — while Platform Staff carries configuration, billing and sensitive operations; collapsing them handed a moderator billing power | `AccountType.CONTENT_ADMIN`; existing platform_staff accounts keep their meaning, promotion is deliberate | Tech |
| D009 | 2026-09-27 | Sponsor Partner is an organization admin of a sponsor organization, not a fifth account type | Its capabilities are those of an organization admin; a distinct type would duplicate the organization-scoped logic | The distinction lives on `Organization.organization_type`, where it already existed | Product/Tech |
| D010 | 2026-09-27 | Administrative authority comes from roles alone; a Django model permission grants nothing | Letting a permission confer moderator actions would make the whole role matrix bypassable by assigning one | Admin permission methods derive from the predicates; a test locks the bypass shut | Tech |
| D011 | 2026-09-27 | Build a real production back-office; Django Admin becomes a developer and operations surface only | §8.2 describes a product back-office, but the operations, frontend and API specs each deferred it, so it was never planned. Django Admin exposes storage keys and raw JSON and has no task-oriented flow — depositing one document there means five model forms and a shell command | Phase 1 closes in four slices instead of one: staff API and deposit, deposit screens, validation workflow, organizations and support | Product/Tech |
| D012 | 2026-09-27 | Put the staff API in its own namespace `/api/staff/v1/` with its own schema | The public contract promises never to reveal whether an unpublished document exists; the staff API exists to show them. One schema would document internal endpoints publicly and couple their versions | Two schemas, two version lifetimes; the staff API reuses the existing services unchanged | Tech |
| D013 | 2026-09-27 | Adopt `react-hook-form` for the staff area; the reader's auth pages keep their `useState` forms | The staff area's forms are the product's data-entry surface — metadata, authors, rights, upload — where the reader has two short auth forms. Hand-rolled state means re-implementing, per form, the wiring a server refusal needs: which field failed, whether it was touched, `aria-invalid`, `aria-describedby`, and focusing the first error | One dependency, confined to `/gestion`. `field_errors` from the API envelope map onto inputs with `setError` instead of bespoke state; the shared `components/ui/FieldErrors` keeps the accessibility contract identical on both sides. Existing reader forms are not migrated | Tech |

## Decision Process

New structural decisions must be added here when they affect product scope, architecture, business model, content rights, launch strategy, or partner commitments.

Each decision should include:

- A clear statement of the decision.
- The reason the decision was made.
- The expected impact.
- The owner responsible for revisiting it if assumptions change.
| D014 | 2026-09-27 | Le workflow de publication porte les cinq états du plan directeur §8.2, plus le rejet — six valeurs, contre dix | Les trois états de revue dupliquaient des barrières déjà tenues ailleurs, et mieux : les droits par `RightsAgreement.authorization_status`, que `missing_publication_requirements` exige approuvé ; le traitement par `DocumentVersion.status` et `ProcessingJob`, qu'agrège l'endpoint d'ingestion. Deux représentations du même verrou finissent par se contredire, et c'est alors la publication qui devient imprévisible. `suspended` partait avec, `withdrawn` portant déjà le même sens | `PublicationStatus` compte six valeurs ; migration `catalog.0006` reprend les lignes existantes (les trois revues vers `submitted`, `suspended` vers `withdrawn`) et refuse le retour arrière, qui serait une invention. La gouvernance des droits est corrigée : elle énonçait la chaîne à dix | Product |
| D015 | 2026-09-27 | Seule la modération crée un auteur ; le registre des contributeurs n'est pas ouvert aux déposants | Un registre national où chacun ajoute librement se remplit de doublons et de variantes orthographiques en quelques mois, et les fusionner après coup coûte bien plus qu'un aller-retour | `/api/staff/v1/authors/` reste en lecture pour un enseignant ; la création s'ouvre au `content_admin` en tranche 3. L'écran de dépôt dit déjà qu'un auteur absent doit être demandé à la modération | Product |
| D016 | 2026-09-28 | Les fichiers privés sont hébergés sur SeaweedFS auto-hébergé | Évalué en séance contre sa passerelle S3 avec boto3 : toutes les opérations du produit passent, 144 petits objets par seconde en écriture. Apache 2.0, conçu pour beaucoup de petits objets — le rendu de pages en produit environ 150 par document. La souveraineté des données prime sur l'économie d'exploitation qu'un service managé apporterait | Clôt D007. Rien ne change dans le code : `DOCUMENT_STORAGE_ENDPOINT_URL` suffit. L'exploitation — sauvegardes, réplication, supervision, mises à jour — revient à l'équipe, et la liste de déploiement le dit désormais | Product/Tech |
| D017 | 2026-09-28 | Les auteurs sont triés par nom affiché, pas par nom de famille | Trier à l'usage académique demanderait de savoir quel mot est le nom de famille. Le déduire serait une heuristique qui se tromperait en silence sur les noms composés, les particules et les institutions — « Université Omar Bongo » n'a pas de nom de famille. Un champ `sort_name` dédié serait fiable mais n'est pas justifié à l'échelle actuelle du registre | Clôt B2. `Author.normalized_name` reste dérivé de `display_name`, et un test énonce explicitement que « Aline NZE » se classe sous A. La question se rouvrira si le registre grandit au point qu'un bibliothécaire s'y perde | Product |

## Open Decision Areas

Le suivi détaillé, avec la dette et les reports assumés, vit dans
`docs/product/02-phase-1-closure-register.md`. La phase 1 ne se clôt qu'avec
sa section « À traiter » vide.


- Whether the publication workflow drives all ten `PublicationStatus` states or collapses to the five named in §8.2 (settled by back-office slice 3).
- Exact B2B pricing tiers and quotas.
- Exact B2C pass durations and FCFA prices.
- First content categories to prioritize by academic domain.
- First institutional pilot targets.
- First payment aggregator or Mobile Money integration partner.
- Data retention policy and legal review process.
