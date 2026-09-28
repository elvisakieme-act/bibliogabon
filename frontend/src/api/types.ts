export interface ApiErrorEnvelope {
  error: {
    code: string;
    message: string;
    field_errors: Record<string, string[]>;
  };
}

export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

// Les cinq valeurs de `accounts.User.AccountType` cote backend. Le type
// n'en declarait qu'une : un compte de moderation violait donc le type
// declare, et TypeScript ne pouvait verifier aucune comparaison de role.
export type AccountType =
  "individual" | "teacher_author" | "organization_admin" | "content_admin" | "platform_staff";

export interface ApiUser {
  id: number;
  email: string;
  display_name: string;
  account_type: AccountType;
}

export interface AuthTokens {
  access: string;
  refresh: string;
}

export interface DomainSummary {
  id: number;
  name: string;
  slug: string;
}

export interface DocumentTypeSummary {
  id: number;
  name: string;
  slug: string;
  icon: string;
  color: string;
}

export interface SearchDomainSummary {
  name: string;
  slug: string;
}

/** La recherche renvoie le type sans identifiant, comme le domaine. */
export interface SearchDocumentTypeSummary {
  name: string;
  slug: string;
}

export interface DocumentMetadata {
  id: number;
  slug: string;
  title: string;
  abstract: string;
  language_code: string;
  publication_year: number | null;
  document_type: string;
  category: string;
  access_model: string;
  domain: DomainSummary | null;
  authors: Array<{ id: number; display_name: string; role: string }>;
  owner: string | null;
  page_count: number | null;
  cover: string | null;
  access: {
    can_read: boolean;
    access_model: string;
    reason: string;
  };
}

export interface ReaderSession {
  session_key: string;
  document_id: number;
  version_id: number;
  expires_at: string;
}

/**
 * Position d'un mot sur la page : [x0, y0, x1, y1, mot].
 *
 * En fractions de la largeur et de la hauteur, jamais en pixels — la largeur
 * de rendu est un réglage du serveur, et des pixels se décaleraient en
 * silence le jour où il change.
 */
export type WordBox = [number, number, number, number, string];

export interface ReaderPage {
  session_key: string;
  document_id: number;
  version_id: number;
  page_number: number;
  page_count: number;
  language_code: string;
  text: string;
  words: WordBox[];
  /**
   * Ce que le lecteur peut faire du texte, dicté par l'accord de droits :
   *
   * - `selectable` — licence ouverte : sélection et copie libres.
   * - `protected` — la copie est empêchée, mais le lecteur d'écran et la
   *   recherche dans la page continuent de fonctionner. C'est une dissuasion,
   *   pas une protection : le texte est dans la page.
   * - `withheld` — clause de confidentialité : le serveur n'envoie aucune
   *   position. `words` est vide, et la page n'est que son image.
   */
  text_policy: "selectable" | "protected" | "withheld";
  /** `null` quand la page n'a pas de rendu : le lecteur affiche le texte. */
  image: string | null;
}

export interface SearchResult {
  id: number;
  title: string;
  slug: string;
  abstract: string;
  language_code: string;
  publication_year: number | null;
  document_type: SearchDocumentTypeSummary | null;
  domain: SearchDomainSummary | null;
  authors: string[];
  access_model: string;
  indexed_page_count: number;
  cover: string | null;
  score: number;
  text_match: boolean;
}

export interface FavoriteItem {
  document: DocumentMetadata;
  created_at: string;
}

export interface ReadingProgressItem {
  document: DocumentMetadata;
  last_page_number: number;
  updated_at: string;
}

// --- Espace de gestion (/api/staff/v1/) --------------------------------------
//
// Aucun de ces types ne porte de cle de stockage, de bucket ni d'URL de
// fichier : le contrat serveur ne les expose pas, et le type le redit ici
// pour qu'un ecran ne puisse pas en inventer un.

export interface StaffNamedRef {
  id: number;
  name: string;
}

export interface StaffAuthor {
  id: number;
  display_name: string;
  role: string;
  position: number;
}

export interface StaffIndex {
  name: string;
  version: string;
  schema: string;
  upload: {
    max_bytes: number;
    accepted_mime_types: string[];
  };
}

export interface StaffAuthorProfile {
  id: number;
  display_name: string;
  author_type: string;
  affiliation: string;
}

export interface StaffRights {
  agreement_type: string;
  rights_holder_name: string;
  authorization_status: string;
  withdrawal_rule: string;
  valid_for_publication: boolean;
}

export interface StaffIngestionSummary {
  version_label: string;
  status: string;
  page_count: number | null;
}

export interface StaffDocument {
  id: number;
  slug: string;
  title: string;
  abstract: string;
  language_code: string;
  publication_year: number | null;
  category: string;
  access_model: string;
  publication_status: string;
  academic_domain: StaffNamedRef | null;
  document_type: StaffNamedRef | null;
  owner_organization: StaffNamedRef | null;
  authors: StaffAuthor[];
  rights: StaffRights | null;
  ingestion: StaffIngestionSummary | null;
  // Deux barrieres distinctes : la declaration complete ouvre la soumission,
  // la declaration approuvee ouvre la publication. Les confondre rendrait la
  // soumission impossible, l'approbation venant apres elle.
  missing_for_submission: string[];
  missing_for_publication: string[];
  created_at: string;
  updated_at: string;
  published_at: string | null;
}

export type IngestionState = "no_source" | "in_progress" | "ready" | "failed";

export interface StaffIngestionStatus {
  state: IngestionState;
  version: {
    version_label: string;
    status: string;
    is_current: boolean;
    page_count: number | null;
    processed_at: string | null;
  } | null;
  job: {
    status: string;
    retry_count: number;
    error_code: string;
    error_message: string;
    started_at: string | null;
    completed_at: string | null;
  } | null;
}

export interface StaffPerson {
  id: number;
  display_name: string;
}

export type ReviewStatus = "open" | "approved" | "rejected" | "cancelled";

export interface StaffReview {
  id: number;
  status: ReviewStatus;
  document: StaffDocument;
  opened_by: StaffPerson | null;
  reviewer: StaffPerson | null;
  decided_by: StaffPerson | null;
  decision_reason: string;
  internal_notes: string;
  opened_at: string;
  decided_at: string | null;
}

export interface StaffAuditEvent {
  id: number;
  event_type: string;
  summary: string;
  created_at: string;
  actor: StaffPerson | null;
  // Filtre par liste blanche cote serveur : aucun champ n'est garanti present.
  metadata: Record<string, unknown>;
}

export interface StaffOrganization {
  id: number;
  name: string;
  slug: string;
  organization_type: string;
  status: string;
  requires_identity_verification: boolean;
  active_member_count?: number;
}

export interface StaffMembership {
  id: number;
  user: { id: number; email: string; display_name: string };
  role: string;
  status: string;
  // Une adhesion non verifiee n'accorde rien : sans ce champ a l'ecran, un
  // administrateur ne comprendra pas pourquoi un membre ne peut pas lire.
  verification_status: string;
  verification_method: string;
  starts_at: string;
  ends_at: string | null;
}

export interface StaffQuota {
  id: number;
  status: string;
  seat_limit: number;
  offer: { id: number; name: string };
  contract_reference: string;
  starts_at: string;
  ends_at: string;
}

export interface StaffInstitutionReport {
  id: number;
  organization: { id: number; name: string; slug: string };
  period: { start: string; end: string };
  status: string;
  // Agregats uniquement. Aucun champ ne nomme un lecteur : un test backend
  // parcourt cette charge utile et echoue si une metriqueureure en ajoute un.
  metrics: Record<string, unknown>;
  generated_at: string;
}

export type TicketCategory = "support" | "document_report" | "withdrawal_request";

export interface StaffTicket {
  id: number;
  category: TicketCategory;
  status: string;
  priority: string;
  title: string;
  description: string;
  created_by: StaffPerson | null;
  assigned_to: StaffPerson | null;
  document: { id: number; title: string; slug: string } | null;
  organization: { id: number; name: string } | null;
  resolution_summary: string;
  opened_at: string;
  resolved_at: string | null;
}

export interface StaffTicketFilters {
  category?: TicketCategory;
  status?: string;
  page?: number;
}

export interface StaffReviewFilters {
  status?: ReviewStatus;
  assigned?: "me" | "none" | "any";
  page?: number;
}

export interface ReviewDecision {
  decision: "approved" | "rejected" | "cancelled";
  reason?: string;
}

export interface StaffDocumentFilters {
  status?: string;
  domain?: string;
  type?: string;
  q?: string;
  page?: number;
  page_size?: number;
}

export interface RightsDeclaration {
  agreement_type: string;
  rights_holder_name: string;
  access_model: string;
  withdrawal_rule: string;
  revenue_sharing_rule?: string;
  confidentiality_terms?: string;
  consent_reference?: string;
  valid_from?: string | null;
  valid_until?: string | null;
}

export interface RightsDecision {
  decision: "approved" | "rejected";
  reviewer_decision: string;
  audit_reference?: string;
  rejection_reason?: string;
}
