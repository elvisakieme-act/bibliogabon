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

export interface ApiUser {
  id: number;
  email: string;
  display_name: string;
  account_type: "individual";
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
