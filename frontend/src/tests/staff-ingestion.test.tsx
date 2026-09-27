import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { StaffIngestionStatus } from "@/api/types";
import { AuthProvider } from "@/auth/AuthProvider";
import { IngestionStatus } from "@/components/staff/IngestionStatus";
import { SourceUpload } from "@/components/staff/SourceUpload";
import { tokenStore } from "@/auth/tokenStore";

afterEach(() => {
  cleanup();
  tokenStore.clear();
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

beforeEach(() => {
  tokenStore.set({ access: "access-token", refresh: "refresh-token" });
});

function wrap(node: React.ReactNode) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>{node}</AuthProvider>
    </QueryClientProvider>
  );
}

function pdf(bytes: number, type = "application/pdf", name = "cours.pdf") {
  return new File([new Uint8Array(bytes)], name, { type });
}

/** XHR minimal, pour observer ce que l'ecran envoie — ou n'envoie pas. */
class FakeXhr {
  static instances: FakeXhr[] = [];
  private listeners: Record<string, Array<(event: unknown) => void>> = {};
  upload = { addEventListener: () => undefined };
  status = 0;
  responseText = "";

  constructor() {
    FakeXhr.instances.push(this);
  }

  open() {}
  setRequestHeader() {}
  removeEventListener() {}
  addEventListener(type: string, listener: (event: unknown) => void) {
    (this.listeners[type] ??= []).push(listener);
  }
  send() {}
  abort() {}
  respond(status: number, payload: unknown) {
    this.status = status;
    this.responseText = JSON.stringify(payload);
    for (const listener of this.listeners.load ?? []) listener({});
  }
}

function stubUpload() {
  FakeXhr.instances = [];
  vi.stubGlobal("XMLHttpRequest", FakeXhr);
  return FakeXhr;
}

function stubMe() {
  vi.stubGlobal(
    "fetch",
    vi.fn(
      async () =>
        new Response(
          JSON.stringify({
            id: 5,
            email: "prof@bibliogabon.ga",
            display_name: "Enseignant",
            account_type: "teacher_author"
          })
        )
    )
  );
}

describe("envoi du fichier source", () => {
  it("refuse un fichier hors borne sans ouvrir de requete", async () => {
    // Faire monter 300 Mo pour s'entendre refuser est une perte de temps et
    // de bande passante, sur des connexions ou elle coute.
    stubMe();
    const xhr = stubUpload();
    wrap(
      <SourceUpload documentId={77} maxBytes={1024} acceptedMimeTypes={["application/pdf"]} />
    );

    await userEvent.upload(await screen.findByLabelText(/fichier source/i), pdf(4096));

    expect(await screen.findByRole("alert")).toHaveTextContent(/trop volumineux/i);
    expect(xhr.instances).toHaveLength(0);
  });

  it("refuse un type non accepte sans ouvrir de requete", async () => {
    stubMe();
    const xhr = stubUpload();
    wrap(
      <SourceUpload documentId={77} maxBytes={10_000} acceptedMimeTypes={["application/pdf"]} />
    );

    // `applyAccept: false` simule un utilisateur qui passe outre le filtre du
    // selecteur — l'attribut `accept` est une commodite, pas une garantie :
    // « Tous les fichiers » y suffit. C'est la verification JS qui protege.
    await userEvent.upload(
      await screen.findByLabelText(/fichier source/i),
      pdf(10, "image/png", "capture.png"),
      { applyAccept: false }
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(/type/i);
    expect(xhr.instances).toHaveLength(0);
  });

  it("rend lisiblement le refus 413 du serveur", async () => {
    // Les bornes du client peuvent differer de celles du serveur, par
    // exemple derriere un proxy plus strict : le refus distant doit se lire.
    stubMe();
    const xhr = stubUpload();
    wrap(
      <SourceUpload
        documentId={77}
        maxBytes={100_000}
        acceptedMimeTypes={["application/pdf"]}
      />
    );

    await userEvent.upload(await screen.findByLabelText(/fichier source/i), pdf(64));
    await userEvent.click(screen.getByRole("button", { name: /envoyer/i }));

    await waitFor(() => expect(xhr.instances).toHaveLength(1));
    xhr.instances[0].respond(413, {
      error: {
        code: "file_too_large",
        message: "Le fichier depasse la taille maximale.",
        field_errors: {}
      }
    });

    expect(await screen.findByRole("alert")).toHaveTextContent(/depasse la taille maximale/i);
  });

  it("rend lisiblement le refus 415 du serveur", async () => {
    stubMe();
    const xhr = stubUpload();
    wrap(
      <SourceUpload
        documentId={77}
        maxBytes={100_000}
        acceptedMimeTypes={["application/pdf"]}
      />
    );

    await userEvent.upload(await screen.findByLabelText(/fichier source/i), pdf(64));
    await userEvent.click(screen.getByRole("button", { name: /envoyer/i }));

    await waitFor(() => expect(xhr.instances).toHaveLength(1));
    xhr.instances[0].respond(415, {
      error: {
        code: "unsupported_media_type",
        message: "Type de fichier non accepte.",
        field_errors: {}
      }
    });

    expect(await screen.findByRole("alert")).toHaveTextContent(/non accepte/i);
  });

  it("annonce la reussite avec la version et le nombre de pages", async () => {
    stubMe();
    const xhr = stubUpload();
    const onUploaded = vi.fn();
    wrap(
      <SourceUpload
        documentId={77}
        maxBytes={100_000}
        acceptedMimeTypes={["application/pdf"]}
        onUploaded={onUploaded}
      />
    );

    await userEvent.upload(await screen.findByLabelText(/fichier source/i), pdf(64));
    await userEvent.click(screen.getByRole("button", { name: /envoyer/i }));
    await waitFor(() => expect(xhr.instances).toHaveLength(1));
    xhr.instances[0].respond(201, {
      id: 77,
      ingestion: { version_label: "v1", status: "pending", page_count: null }
    });

    expect(await screen.findByRole("status")).toHaveTextContent(/v1/);
    await waitFor(() => expect(onUploaded).toHaveBeenCalled());
  });

  it("ne montre jamais le chemin local ni une URL de stockage", async () => {
    stubMe();
    stubUpload();
    wrap(
      <SourceUpload
        documentId={77}
        maxBytes={100_000}
        acceptedMimeTypes={["application/pdf"]}
      />
    );

    await userEvent.upload(await screen.findByLabelText(/fichier source/i), pdf(64));

    const rendered = document.body.textContent ?? "";
    expect(rendered).not.toMatch(/:\/\//);
    expect(rendered.toLowerCase()).not.toContain("storage");
  });
});

function ingestion(overrides: Partial<StaffIngestionStatus> = {}): StaffIngestionStatus {
  return {
    state: "in_progress",
    version: {
      version_label: "v1",
      status: "processing",
      is_current: true,
      page_count: null,
      processed_at: null
    },
    job: {
      status: "running",
      retry_count: 0,
      error_code: "",
      error_message: "",
      started_at: "2026-09-27T10:00:00Z",
      completed_at: null
    },
    ...overrides
  };
}

function stubIngestion(responses: StaffIngestionStatus[]) {
  let call = 0;
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = new URL(String(input));
    if (url.pathname === "/api/v1/me/") {
      return new Response(
        JSON.stringify({
          id: 5,
          email: "prof@bibliogabon.ga",
          display_name: "Enseignant",
          account_type: "teacher_author"
        })
      );
    }
    if (url.pathname === "/api/staff/v1/documents/77/ingestion/") {
      const payload = responses[Math.min(call, responses.length - 1)];
      call += 1;
      return new Response(JSON.stringify(payload));
    }
    return new Response(JSON.stringify({}));
  });
  vi.stubGlobal("fetch", fetchMock);
  return {
    ingestionCalls: () =>
      fetchMock.mock.calls.filter(
        ([input]) => new URL(String(input)).pathname === "/api/staff/v1/documents/77/ingestion/"
      ).length
  };
}

describe("suivi du traitement", () => {
  it("dit qu'aucun fichier n'a encore ete recu", async () => {
    stubIngestion([ingestion({ state: "no_source", version: null, job: null })]);
    wrap(<IngestionStatus documentId={77} />);

    expect(await screen.findByText(/aucun fichier/i)).toBeInTheDocument();
  });

  it("interroge le serveur tant que le traitement court", async () => {
    const { ingestionCalls } = stubIngestion([ingestion(), ingestion(), ingestion()]);
    wrap(<IngestionStatus documentId={77} />);

    await screen.findByText(/en cours/i);
    await waitFor(() => expect(ingestionCalls()).toBeGreaterThan(1), { timeout: 6000 });
  });

  it("cesse d'interroger des que le traitement aboutit", async () => {
    const { ingestionCalls } = stubIngestion([
      ingestion({
        state: "ready",
        version: {
          version_label: "v1",
          status: "processed",
          is_current: true,
          page_count: 157,
          processed_at: "2026-09-27T10:05:00Z"
        }
      })
    ]);
    wrap(<IngestionStatus documentId={77} />);

    expect(await screen.findByText(/157/)).toBeInTheDocument();
    const settled = ingestionCalls();
    await new Promise((resolve) => setTimeout(resolve, 2600));
    expect(ingestionCalls()).toBe(settled);
  });

  it("cesse d'interroger apres un echec et en donne la raison", async () => {
    const { ingestionCalls } = stubIngestion([
      ingestion({
        state: "failed",
        job: {
          status: "failed",
          retry_count: 3,
          error_code: "ingest_failed",
          error_message: "Le PDF ne contient aucune page exploitable.",
          started_at: "2026-09-27T10:00:00Z",
          completed_at: "2026-09-27T10:01:00Z"
        }
      })
    ]);
    wrap(<IngestionStatus documentId={77} />);

    expect(
      await screen.findByText("Le PDF ne contient aucune page exploitable.")
    ).toBeInTheDocument();
    expect(screen.getByText(/3 tentative/i)).toBeInTheDocument();
    const settled = ingestionCalls();
    await new Promise((resolve) => setTimeout(resolve, 2600));
    expect(ingestionCalls()).toBe(settled);
  });

  it("n'expose ni cle de stockage ni URL dans le suivi", async () => {
    stubIngestion([
      ingestion({
        state: "ready",
        version: {
          version_label: "v1",
          status: "processed",
          is_current: true,
          page_count: 12,
          processed_at: "2026-09-27T10:05:00Z"
        }
      })
    ]);
    wrap(<IngestionStatus documentId={77} />);
    await screen.findByText(/12/);

    const rendered = document.body.textContent ?? "";
    expect(rendered).not.toMatch(/\.pdf/i);
    expect(rendered).not.toMatch(/:\/\//);
    expect(rendered.toLowerCase()).not.toContain("storage");
  });
});
