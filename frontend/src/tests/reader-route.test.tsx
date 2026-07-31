import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, RouterProvider } from "@tanstack/react-router";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { StrictMode } from "react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ReaderControls } from "@/components/reader/ReaderControls";
import { ReaderPage } from "@/components/reader/ReaderPage";
import { tokenStore } from "@/auth/tokenStore";
import { createAppRouter } from "@/router";

const documentPayload = {
  id: 10,
  slug: "droit-public",
  title: "Droit public gabonais",
  abstract: "Resume public.",
  language_code: "fr",
  publication_year: 2026,
  document_type: "open_resource",
  access_model: "free",
  domain: null,
  authors: [],
  owner: null,
  page_count: 2,
  cover: null,
  access: { can_read: true, access_model: "free", reason: "free" }
};

function renderLectureRoute({
  strict = false,
  path = "/lecture/10"
}: {
  strict?: boolean;
  path?: string;
} = {}) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createAppRouter({ history: createMemoryHistory({ initialEntries: [path] }) });
  const route = <QueryClientProvider client={queryClient}><RouterProvider router={router} /></QueryClientProvider>;
  return render(strict ? <StrictMode>{route}</StrictMode> : route);
}

afterEach(() => {
  cleanup();
  tokenStore.clear();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("reader components", () => {
  it("renders page content without raw download controls", () => {
    render(
      <ReaderPage
        title="Droit public"
        page={{ session_key: "550e8400-e29b-41d4-a716-446655440000", document_id: 1, version_id: 1, page_number: 2, page_count: 5, language_code: "fr", text: "Page securisee" }}
      />
    );

    expect(screen.getByText("Page securisee")).toBeInTheDocument();
    expect(screen.queryByText(/Telecharger/i)).not.toBeInTheDocument();
  });

  it("calls previous and next controls", async () => {
    const previous = vi.fn();
    const next = vi.fn();
    render(
      <ReaderControls
        pageNumber={2}
        pageCount={5}
        onPrevious={previous}
        onNext={next}
      />
    );

    await userEvent.click(screen.getByRole("button", { name: /Page precedente/i }));
    await userEvent.click(screen.getByRole("button", { name: /Page suivante/i }));

    expect(previous).toHaveBeenCalledTimes(1);
    expect(next).toHaveBeenCalledTimes(1);
  });
});

describe("secure reader route", () => {
  it("starts the reader on the page requested by a resume link", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/api/v1/catalog/documents/10/")) {
        return new Response(JSON.stringify(documentPayload));
      }
      if (url.endsWith("/api/v1/reader/sessions/") && init?.method === "POST") {
        return new Response(JSON.stringify({
          session_key: "session-resume",
          document_id: 10,
          version_id: 1,
          expires_at: "2026-08-01T00:00:00Z"
        }), { status: 201 });
      }
      if (url.endsWith("/api/v1/reader/sessions/session-resume/pages/2/")) {
        return new Response(JSON.stringify({
          session_key: "session-resume",
          document_id: 10,
          version_id: 1,
          page_number: 2,
          page_count: 2,
          language_code: "fr",
          text: "Page reprise"
        }));
      }
      if (init?.method === "DELETE") return new Response(null, { status: 204 });
      throw new Error(`Unexpected request: ${init?.method ?? "GET"} ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    renderLectureRoute({ path: "/lecture/10?page=2" });

    expect(await screen.findByText("Page reprise")).toBeInTheDocument();
    expect(fetchMock.mock.calls.map(([url]) => String(url))).toContain(
      "http://127.0.0.1:8000/api/v1/reader/sessions/session-resume/pages/2/"
    );
  });

  it("persists a successfully loaded page change for an authenticated reader", async () => {
    tokenStore.set({ access: "access-token", refresh: "refresh-token" });
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/api/v1/me/")) {
        return new Response(JSON.stringify({
          id: 1,
          email: "reader@example.ga",
          display_name: "Reader",
          account_type: "individual"
        }));
      }
      if (url.endsWith("/api/v1/catalog/documents/10/")) {
        return new Response(JSON.stringify(documentPayload));
      }
      if (url.endsWith("/api/v1/reader/sessions/") && init?.method === "POST") {
        return new Response(JSON.stringify({
          session_key: "session-progress",
          document_id: 10,
          version_id: 1,
          expires_at: "2026-08-01T00:00:00Z"
        }), { status: 201 });
      }
      if (url.includes("/api/v1/reader/sessions/session-progress/pages/1/")) {
        return new Response(JSON.stringify({
          session_key: "session-progress",
          document_id: 10,
          version_id: 1,
          page_number: 1,
          page_count: 2,
          language_code: "fr",
          text: "Premiere page"
        }));
      }
      if (url.includes("/api/v1/reader/sessions/session-progress/pages/2/")) {
        return new Response(JSON.stringify({
          session_key: "session-progress",
          document_id: 10,
          version_id: 1,
          page_number: 2,
          page_count: 2,
          language_code: "fr",
          text: "Deuxieme page"
        }));
      }
      if (url.endsWith("/api/v1/me/reading-progress/10/") && init?.method === "PATCH") {
        return new Response(JSON.stringify({}));
      }
      if (init?.method === "DELETE") return new Response(null, { status: 204 });
      throw new Error(`Unexpected request: ${init?.method ?? "GET"} ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    renderLectureRoute();
    expect(await screen.findByText("Premiere page")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Page suivante/i }));
    expect(await screen.findByText("Deuxieme page")).toBeInTheDocument();

    await waitFor(() => {
      const progressCall = fetchMock.mock.calls.find(([url, init]) =>
        String(url).endsWith("/api/v1/me/reading-progress/10/")
        && (init as RequestInit | undefined)?.method === "PATCH"
        && (init as RequestInit | undefined)?.body === JSON.stringify({
          last_page_number: 2
        })
      );
      expect(progressCall).toBeDefined();
    });
  });

  it("closes a superseded StrictMode session when its creation resolves late", async () => {
    let sessionCount = 0;
    let resolveFirstSession: (response: Response) => void;
    const firstSession = new Promise<Response>((resolve) => {
      resolveFirstSession = resolve;
    });
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/api/v1/catalog/documents/10/")) return new Response(JSON.stringify(documentPayload));
      if (url.endsWith("/api/v1/reader/sessions/") && init?.method === "POST") {
        sessionCount += 1;
        if (sessionCount === 1) return firstSession;
        return new Response(JSON.stringify({ session_key: "session-current", document_id: 10, version_id: 1, expires_at: "2026-08-01T00:00:00Z" }), { status: 201 });
      }
      if (url.endsWith("/api/v1/reader/sessions/session-current/pages/1/")) {
        return new Response(JSON.stringify({ session_key: "session-current", document_id: 10, version_id: 1, page_number: 1, page_count: 2, language_code: "fr", text: "Page actuelle" }));
      }
      if (init?.method === "DELETE") return new Response(null, { status: 204 });
      throw new Error(`Unexpected request: ${init?.method ?? "GET"} ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    renderLectureRoute({ strict: true });
    await waitFor(() => expect(sessionCount).toBeGreaterThanOrEqual(2));
    resolveFirstSession!(new Response(JSON.stringify({ session_key: "session-superseded", document_id: 10, version_id: 1, expires_at: "2026-08-01T00:00:00Z" }), { status: 201 }));

    await waitFor(() => expect(fetchMock.mock.calls.map(([url, init]) => `${(init as RequestInit | undefined)?.method ?? "GET"} ${String(url)}`)).toContain(
      "DELETE http://127.0.0.1:8000/api/v1/reader/sessions/session-superseded/"
    ));
  });

  it("closes the active session before retrying a failed page request", async () => {
    let sessionCount = 0;
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/api/v1/catalog/documents/10/")) {
        return new Response(JSON.stringify(documentPayload));
      }
      if (url.endsWith("/api/v1/reader/sessions/") && init?.method === "POST") {
        sessionCount += 1;
        return new Response(JSON.stringify({ session_key: `session-${sessionCount}`, document_id: 10, version_id: 1, expires_at: "2026-08-01T00:00:00Z" }), { status: 201 });
      }
      if (url.endsWith("/api/v1/reader/sessions/session-1/pages/1/")) {
        throw new TypeError("Network unavailable");
      }
      if (url.endsWith("/api/v1/reader/sessions/session-2/pages/1/")) {
        return new Response(JSON.stringify({ session_key: "session-2", document_id: 10, version_id: 1, page_number: 1, page_count: 2, language_code: "fr", text: "Page securisee" }));
      }
      if (url.endsWith("/api/v1/reader/sessions/session-1/") && init?.method === "DELETE") {
        return new Response(null, { status: 204 });
      }
      throw new Error(`Unexpected request: ${init?.method ?? "GET"} ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    renderLectureRoute();
    await userEvent.click(await screen.findByRole("button", { name: "Reessayer" }));

    await waitFor(() => expect(screen.getByText("Page securisee")).toBeInTheDocument());
    const requests = fetchMock.mock.calls.map(([url, init]) => `${(init as RequestInit | undefined)?.method ?? "GET"} ${String(url)}`);
    expect(requests).toContain("DELETE http://127.0.0.1:8000/api/v1/reader/sessions/session-1/");
    expect(requests.indexOf("DELETE http://127.0.0.1:8000/api/v1/reader/sessions/session-1/")).toBeLessThan(
      requests.lastIndexOf("POST http://127.0.0.1:8000/api/v1/reader/sessions/")
    );
  });

  it("shows a login call to action when the reader session requires authentication", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/api/v1/catalog/documents/10/")) return new Response(JSON.stringify(documentPayload));
      if (url.endsWith("/api/v1/reader/sessions/") && init?.method === "POST") {
        return new Response(JSON.stringify({ error: { code: "authentication_required", message: "Authentication is required.", field_errors: {} } }), { status: 401 });
      }
      throw new Error(`Unexpected request: ${init?.method ?? "GET"} ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    renderLectureRoute();

    expect(await screen.findByRole("heading", { name: "Connexion requise" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Se connecter" })).toHaveAttribute("href", "/connexion?next=%2Flecture%2F10");
  });
});
