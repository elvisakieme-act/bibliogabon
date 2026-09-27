import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/api/client";
import {
  addDocumentAuthor,
  createStaffDocument,
  decideDocumentRights,
  declareDocumentRights,
  getDocumentIngestion,
  getStaffDocument,
  listStaffDocuments,
  removeDocumentAuthor,
  submitStaffDocument,
  updateStaffDocument
} from "@/api/staff";

const TOKEN = "staff-access-token";

afterEach(() => {
  vi.unstubAllGlobals();
});

function captureFetch(response: Response) {
  const fetchMock = vi.fn(async () => response.clone());
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function json(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" }
  });
}

function requestOf(fetchMock: ReturnType<typeof captureFetch>) {
  const [input, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
  return { url: new URL(String(input)), init };
}

describe("client de l'API staff", () => {
  it("liste les documents sur le perimetre staff, jamais sur l'API publique", async () => {
    const fetchMock = captureFetch(json({ count: 0, next: null, previous: null, results: [] }));

    await listStaffDocuments({ token: TOKEN });

    const { url, init } = requestOf(fetchMock);
    expect(url.pathname).toBe("/api/staff/v1/documents/");
    expect((init.headers as Record<string, string>).Authorization).toBe(`Bearer ${TOKEN}`);
  });

  it("transmet les filtres et la pagination en parametres de requete", async () => {
    const fetchMock = captureFetch(json({ count: 0, next: null, previous: null, results: [] }));

    await listStaffDocuments({
      token: TOKEN,
      filters: {
        status: "draft",
        domain: "droit",
        type: "cours",
        q: "reseaux",
        page: 3,
        page_size: 25
      }
    });

    const { url } = requestOf(fetchMock);
    expect(Object.fromEntries(url.searchParams)).toEqual({
      status: "draft",
      domain: "droit",
      type: "cours",
      q: "reseaux",
      page: "3",
      page_size: "25"
    });
  });

  it("n'envoie pas de parametre vide", async () => {
    // Un `?q=` vide ferait filtrer le serveur sur une chaine vide au lieu de
    // ne pas filtrer du tout.
    const fetchMock = captureFetch(json({ count: 0, next: null, previous: null, results: [] }));

    await listStaffDocuments({ token: TOKEN, filters: { q: "", status: undefined } });

    expect(requestOf(fetchMock).url.search).toBe("");
  });

  it("atteint le bon chemin pour chaque operation", async () => {
    const cases: Array<[() => Promise<unknown>, string, string]> = [
      [() => getStaffDocument(12, TOKEN), "/api/staff/v1/documents/12/", "GET"],
      [() => createStaffDocument({ title: "T" }, TOKEN), "/api/staff/v1/documents/", "POST"],
      [
        () => updateStaffDocument(12, { title: "T" }, TOKEN),
        "/api/staff/v1/documents/12/",
        "PATCH"
      ],
      [() => submitStaffDocument(12, TOKEN), "/api/staff/v1/documents/12/submit/", "POST"],
      [
        () => addDocumentAuthor(12, { author: 3, role: "author" }, TOKEN),
        "/api/staff/v1/documents/12/authors/",
        "POST"
      ],
      [
        () => removeDocumentAuthor(12, 3, TOKEN),
        "/api/staff/v1/documents/12/authors/3/",
        "DELETE"
      ],
      [
        () =>
          declareDocumentRights(
            12,
            {
              agreement_type: "teacher_voluntary",
              rights_holder_name: "Auteur",
              access_model: "free",
              withdrawal_rule: "author_request"
            },
            TOKEN
          ),
        "/api/staff/v1/documents/12/rights/",
        "PUT"
      ],
      [
        () =>
          decideDocumentRights(
            12,
            { decision: "approved", reviewer_decision: "ok", audit_reference: "BG-1" },
            TOKEN
          ),
        "/api/staff/v1/documents/12/rights/decision/",
        "POST"
      ],
      [() => getDocumentIngestion(12, TOKEN), "/api/staff/v1/documents/12/ingestion/", "GET"]
    ];

    for (const [call, path, method] of cases) {
      const fetchMock = captureFetch(json({}));
      await call();
      const { url, init } = requestOf(fetchMock);
      expect(url.pathname, path).toBe(path);
      expect(init.method ?? "GET", path).toBe(method);
      vi.unstubAllGlobals();
    }
  });

  it("ne pretend pas recevoir un document quand le serveur repond 204", async () => {
    // Le detachement d'auteur repond 204 sans corps. Typer un document ici
    // ferait lire `undefined.title` a l'appelant.
    captureFetch(new Response(null, { status: 204 }));

    await expect(removeDocumentAuthor(12, 3, TOKEN)).resolves.toBeUndefined();
  });

  it("transforme l'enveloppe d'erreur en ApiError portant les erreurs de champ", async () => {
    captureFetch(
      json(
        {
          error: {
            code: "invalid_request",
            message: "Document invalide.",
            field_errors: { title: ["Ce champ est obligatoire."] }
          }
        },
        400
      )
    );

    const error = await createStaffDocument({}, TOKEN).catch((caught) => caught);

    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).code).toBe("invalid_request");
    expect((error as ApiError).fieldErrors).toEqual({
      title: ["Ce champ est obligatoire."]
    });
  });

  it("ne confond pas 404 et 403 : un document hors perimetre reste introuvable", async () => {
    // Le serveur repond 404 sur un document qu'on n'a pas le droit de voir,
    // pour ne pas confirmer l'existence d'un brouillon. Le client ne doit
    // pas reinterpreter ce code.
    captureFetch(
      json(
        { error: { code: "not_found", message: "Document introuvable.", field_errors: {} } },
        404
      )
    );

    const error = await getStaffDocument(99, TOKEN).catch((caught) => caught);

    expect((error as ApiError).status).toBe(404);
    expect((error as ApiError).code).toBe("not_found");
  });
});
