import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, UNAUTHORIZED_EVENT } from "@/api/client";
import { apiUpload } from "@/api/upload";

type Listener = (event: unknown) => void;

/** Emetteur minimal, pour que le faux XHR n'ait pas besoin d'un `any`. */
class Emitter {
  private listeners: Record<string, Listener[]> = {};

  addEventListener = (type: string, listener: Listener) => {
    (this.listeners[type] ??= []).push(listener);
  };

  emit(type: string, event: unknown) {
    for (const listener of this.listeners[type] ?? []) listener(event);
  }
}

class FakeXhr {
  static last: FakeXhr | null = null;

  method = "";
  url = "";
  headers: Record<string, string> = {};
  body: unknown = null;
  status = 0;
  responseText = "";
  aborted = false;
  upload = new Emitter();
  private events = new Emitter();

  constructor() {
    FakeXhr.last = this;
  }

  open(method: string, url: string) {
    this.method = method;
    this.url = url;
  }

  setRequestHeader(name: string, value: string) {
    this.headers[name] = value;
  }

  addEventListener = (type: string, listener: Listener) => {
    this.events.addEventListener(type, listener);
  };

  removeEventListener() {
    // Le vrai XHR en a un ; rien a faire ici.
  }

  send(body: unknown) {
    this.body = body;
  }

  abort() {
    this.aborted = true;
    this.events.emit("abort", {});
  }

  emitUploadProgress(loaded: number, total: number) {
    this.upload.emit("progress", { lengthComputable: true, loaded, total });
  }

  respond(status: number, payload: unknown) {
    this.status = status;
    this.responseText = typeof payload === "string" ? payload : JSON.stringify(payload);
    this.events.emit("load", {});
  }
}

function stubXhr() {
  vi.stubGlobal("XMLHttpRequest", FakeXhr);
  return () => {
    const xhr = FakeXhr.last;
    if (!xhr) throw new Error("aucune requete emise");
    return xhr;
  };
}

afterEach(() => {
  FakeXhr.last = null;
  vi.unstubAllGlobals();
});

function pdf() {
  return new File([new Uint8Array([1, 2, 3])], "cours.pdf", { type: "application/pdf" });
}

describe("apiUpload", () => {
  it("envoie un FormData sans fixer Content-Type", async () => {
    // Le navigateur doit ecrire la frontiere multipart lui-meme. La fixer a
    // la main produit un corps que le serveur ne sait pas decouper.
    const current = stubXhr();
    const promise = apiUpload("/api/staff/v1/documents/12/source/", pdf(), { token: "t" });
    const xhr = current();

    xhr.respond(201, { id: 12 });
    await promise;

    expect(xhr.method).toBe("POST");
    expect(xhr.url).toContain("/api/staff/v1/documents/12/source/");
    expect(xhr.body).toBeInstanceOf(FormData);
    expect((xhr.body as FormData).get("file")).toBeInstanceOf(File);
    expect(Object.keys(xhr.headers)).not.toContain("Content-Type");
    expect(xhr.headers.Authorization).toBe("Bearer t");
  });

  it("rapporte la progression de l'envoi", async () => {
    const progress: number[] = [];
    const current = stubXhr();
    const promise = apiUpload("/api/staff/v1/documents/12/source/", pdf(), {
      token: "t",
      onProgress: (ratio) => progress.push(ratio)
    });
    const xhr = current();

    xhr.emitUploadProgress(25, 100);
    xhr.emitUploadProgress(100, 100);
    xhr.respond(201, {});
    await promise;

    expect(progress).toEqual([0.25, 1]);
  });

  it("rejette avec ApiError sur un 413 en portant le code du serveur", async () => {
    const current = stubXhr();
    const promise = apiUpload("/api/staff/v1/documents/12/source/", pdf(), { token: "t" });
    const xhr = current();

    xhr.respond(413, {
      error: { code: "file_too_large", message: "Fichier trop volumineux.", field_errors: {} }
    });
    const error = await promise.catch((caught) => caught);

    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(413);
    expect((error as ApiError).code).toBe("file_too_large");
  });

  it("porte les erreurs de champ d'un refus 400", async () => {
    const current = stubXhr();
    const promise = apiUpload("/api/staff/v1/documents/12/source/", pdf(), { token: "t" });
    const xhr = current();

    xhr.respond(400, {
      error: {
        code: "invalid_request",
        message: "Aucun fichier recu.",
        field_errors: { file: ["Ce champ est obligatoire."] }
      }
    });
    const error = await promise.catch((caught) => caught);

    expect((error as ApiError).fieldErrors).toEqual({ file: ["Ce champ est obligatoire."] });
  });

  it("signale la perte de session sur un 401, comme apiRequest", async () => {
    const seen = vi.fn();
    window.addEventListener(UNAUTHORIZED_EVENT, seen);
    const current = stubXhr();
    const promise = apiUpload("/api/staff/v1/documents/12/source/", pdf(), { token: "t" });
    const xhr = current();

    xhr.respond(401, { error: { code: "not_authenticated", message: "", field_errors: {} } });
    await promise.catch(() => undefined);
    window.removeEventListener(UNAUTHORIZED_EVENT, seen);

    expect(seen).toHaveBeenCalled();
  });

  it("transmet le drapeau de remplacement en parametre de requete", async () => {
    const current = stubXhr();
    const promise = apiUpload("/api/staff/v1/documents/12/source/", pdf(), {
      token: "t",
      replace: true
    });
    const xhr = current();
    xhr.respond(201, {});
    await promise;

    expect(new URL(xhr.url).searchParams.get("replace")).toBe("true");
  });

  it("annule la requete quand le signal est declenche", async () => {
    const controller = new AbortController();
    const current = stubXhr();
    const promise = apiUpload("/api/staff/v1/documents/12/source/", pdf(), {
      token: "t",
      signal: controller.signal
    });
    const xhr = current();

    controller.abort();
    const error = await promise.catch((caught) => caught);

    expect(xhr.aborted).toBe(true);
    expect((error as Error).name).toBe("AbortError");
  });

  it("transforme une reponse illisible en erreur plutot qu'en succes muet", async () => {
    const current = stubXhr();
    const promise = apiUpload("/api/staff/v1/documents/12/source/", pdf(), { token: "t" });
    const xhr = current();

    xhr.respond(500, "<html>erreur du proxy</html>");
    const error = await promise.catch((caught) => caught);

    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(500);
  });
});
