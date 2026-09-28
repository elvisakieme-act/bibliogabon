import { useState } from "react";

import { ApiError } from "@/api/client";
import type { StaffDocument } from "@/api/types";
import { AUTHOR_ROLE_OPTIONS } from "@/components/staff/rightsOptions";
import {
  useAddDocumentAuthor,
  useRemoveDocumentAuthor,
  useStaffAuthors
} from "@/features/staff/hooks";

function roleLabel(role: string) {
  return AUTHOR_ROLE_OPTIONS.find((option) => option.value === role)?.label ?? role;
}

export function AuthorsSection({
  document,
  documentId
}: {
  document: StaffDocument;
  documentId: number;
}) {
  const [search, setSearch] = useState("");
  const [authorId, setAuthorId] = useState("");
  const [role, setRole] = useState("author");
  const [error, setError] = useState("");
  const registry = useStaffAuthors(search);
  const attach = useAddDocumentAuthor(documentId);
  const detach = useRemoveDocumentAuthor(documentId);

  const attached = new Set(document.authors.map((entry) => entry.id));
  const candidates = (registry.data?.results ?? []).filter(
    (author) => !attached.has(author.id)
  );

  async function run(action: () => Promise<unknown>) {
    setError("");
    try {
      await action();
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? caught.message
          : "L'operation n'a pas pu aboutir. Réessayez."
      );
    }
  }

  return (
    <section className="space-y-4 rounded border border-slate-200 bg-white p-4">
      <h3 className="font-semibold">Auteurs et contributeurs</h3>
      {error ? (
        <p role="alert" className="rounded bg-red-50 p-3 text-sm text-red-800">
          {error}
        </p>
      ) : null}

      {document.authors.length > 0 ? (
        <ul className="divide-y divide-slate-100 text-sm">
          {document.authors.map((entry) => (
            <li key={entry.id} className="flex items-center justify-between gap-3 py-2">
              <span>
                {entry.display_name}
                <span className="ms-2 text-slate-500">{roleLabel(entry.role)}</span>
              </span>
              <button
                type="button"
                aria-label={`Détacher ${entry.display_name}`}
                className="rounded border border-slate-300 px-2 py-1 text-xs"
                disabled={detach.isPending}
                onClick={() => run(() => detach.mutateAsync(entry.id))}
              >
                Détacher
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-slate-600">
          Aucun auteur rattache. Le document ne pourra pas être soumis sans au moins un auteur
          ou co-auteur.
        </p>
      )}

      <div className="grid gap-3 border-t border-slate-100 pt-4 sm:grid-cols-3">
        <div className="flex flex-col gap-1">
          <label htmlFor="auteur-recherche" className="text-sm font-medium">
            Rechercher un auteur
          </label>
          <input
            id="auteur-recherche"
            type="search"
            className="rounded border border-slate-300 px-2 py-1.5 text-sm"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </div>
        <div className="flex flex-col gap-1">
          <label htmlFor="auteur-choix" className="text-sm font-medium">
            Auteur a rattacher
          </label>
          <select
            id="auteur-choix"
            className="rounded border border-slate-300 px-2 py-1.5 text-sm"
            value={authorId}
            onChange={(event) => setAuthorId(event.target.value)}
          >
            <option value="">Choisir</option>
            {candidates.map((author) => (
              <option key={author.id} value={String(author.id)}>
                {author.display_name}
                {author.affiliation ? ` — ${author.affiliation}` : ""}
              </option>
            ))}
          </select>
        </div>
        <div className="flex flex-col gap-1">
          <label htmlFor="auteur-role" className="text-sm font-medium">
            Role
          </label>
          <select
            id="auteur-role"
            className="rounded border border-slate-300 px-2 py-1.5 text-sm"
            value={role}
            onChange={(event) => setRole(event.target.value)}
          >
            {AUTHOR_ROLE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      <button
        type="button"
        disabled={!authorId || attach.isPending}
        onClick={() =>
          run(async () => {
            await attach.mutateAsync({ author: Number(authorId), role });
            setAuthorId("");
          })
        }
        className="rounded bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
      >
        Rattacher l&apos;auteur
      </button>
      <p className="text-xs text-slate-500">
        Un auteur absent du registre doit y être ajoute par la moderation : le registre des
        contributeurs est commun a tout le catalogue.
      </p>
    </section>
  );
}
