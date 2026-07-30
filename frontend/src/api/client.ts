import type { ApiErrorEnvelope } from "@/api/types";

const DEFAULT_API_BASE_URL = "http://127.0.0.1:8000";

type ViteEnvironment = {
  VITE_API_BASE_URL?: string;
};

export interface ApiRequestOptions {
  method?: string;
  token?: string | null;
  body?: unknown;
  signal?: AbortSignal;
}

export class ApiError extends Error {
  code: string;
  status: number;
  fieldErrors: Record<string, string[]>;

  constructor(status: number, code: string, message: string, fieldErrors = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.fieldErrors = fieldErrors;
  }
}

export function apiBaseUrl() {
  const environment = import.meta as ImportMeta & { env?: ViteEnvironment };
  return environment.env?.VITE_API_BASE_URL || DEFAULT_API_BASE_URL;
}

function urlFor(path: string) {
  if (path.startsWith("http")) return path;
  return `${apiBaseUrl()}${path.startsWith("/") ? path : `/${path}`}`;
}

async function parseError(response: Response): Promise<ApiError> {
  try {
    const payload = (await response.json()) as ApiErrorEnvelope;
    if (payload.error) {
      return new ApiError(
        response.status,
        payload.error.code,
        payload.error.message,
        payload.error.field_errors
      );
    }
  } catch {
    return new ApiError(response.status, "invalid_response", "The API response is invalid.");
  }
  return new ApiError(response.status, "request_failed", response.statusText);
}

export async function apiRequest<T>(
  path: string,
  options: ApiRequestOptions = {}
): Promise<T> {
  const headers: Record<string, string> = {
    Accept: "application/json"
  };
  if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
  }
  if (options.token) {
    headers.Authorization = `Bearer ${options.token}`;
  }

  const response = await fetch(urlFor(path), {
    method: options.method ?? "GET",
    headers,
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
    signal: options.signal
  });

  if (!response.ok) {
    throw await parseError(response);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}
