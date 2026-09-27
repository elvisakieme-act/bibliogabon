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

export interface SearchDomainSummary {
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

export interface ReaderPage {
  session_key: string;
  document_id: number;
  version_id: number;
  page_number: number;
  page_count: number;
  language_code: string;
  text: string;
}

export interface SearchResult {
  id: number;
  title: string;
  slug: string;
  abstract: string;
  language_code: string;
  publication_year: number | null;
  domain: SearchDomainSummary | null;
  authors: string[];
  access_model: string;
  indexed_page_count: number;
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
