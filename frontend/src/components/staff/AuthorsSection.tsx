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
    <section className="space-y-5 rounded-[calc(var(--radius)+0.25rem)] border border-[var(--border)] bg-[var(--card)] p-5 shadow-editorial">
      <h3 className="font-display text-lg text-[var(--navy)]">Auteurs et contributeurs</h3>
      {error ? (
        <p role="alert" className="rounded bg-red-50 p-3 text-sm text-red-800">
          {error}
        </p>
      ) : null}

      {document.authors.length > 0 ? (
        <ul className="divide-y divide-[var(--border)] text-sm">
          {document.authors.map((entry) => (
            <li key={entry.id} className="flex items-center justify-between gap-3 py-2">
              <span>
                {entry.display_name}
                <span className="ms-2 text-[var(--muted-foreground)]">
                  {roleLabel(entry.role)}
                </span>
              </span>
              <button
                type="button"
                aria-label={`Détacher ${entry.display_name}`}
                className="inline-flex items-center justify-center rounded-[var(--radius)] border border-[var(--border)] bg-white px-2.5 py-1 text-xs font-semibold text-[var(--navy)] transition hover:bg-[var(--navy-soft)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--gold)]"
                disabled={detach.isPending}
                onClick={() => run(() => detach.mutateAsync(entry.id))}
              >
                Détacher
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-[var(--muted-foreground)]">
          Aucun auteur rattache. Le document ne pourra pas être soumis sans au moins un auteur
          ou co-auteur.
        </p>
      )}

      <div className="grid gap-3 border-t border-[var(--border)] pt-4 sm:grid-cols-3">
        <div className="flex flex-col gap-1">
          <label
            htmlFor="auteur-recherche"
            className="text-sm font-semibold text-[var(--navy)]"
          >
            Rechercher un auteur
          </label>
          <input
            id="auteur-recherche"
            type="search"
            className="w-full rounded-[var(--radius)] border border-[var(--border)] bg-white px-3.5 py-2.5 text-sm transition focus-visible:border-[var(--gold)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--gold)]"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </div>
        <div className="flex flex-col gap-1">
          <label htmlFor="auteur-choix" className="text-sm font-semibold text-[var(--navy)]">
            Auteur a rattacher
          </label>
          <select
            id="auteur-choix"
            className="w-full rounded-[var(--radius)] border border-[var(--border)] bg-white px-3.5 py-2.5 text-sm transition focus-visible:border-[var(--gold)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--gold)]"
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
          <label htmlFor="auteur-role" className="text-sm font-semibold text-[var(--navy)]">
            Role
          </label>
          <select
            id="auteur-role"
            className="w-full rounded-[var(--radius)] border border-[var(--border)] bg-white px-3.5 py-2.5 text-sm transition focus-visible:border-[var(--gold)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--gold)]"
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
        className="inline-flex items-center justify-center rounded-[var(--radius)] bg-[var(--navy)] px-4 py-2.5 text-sm font-semibold text-white shadow-editorial transition hover:bg-[var(--navy-deep)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--gold)] focus-visible:ring-offset-2 disabled:opacity-45"
      >
        Rattacher l&apos;auteur
      </button>
      <p className="text-xs text-[var(--muted-foreground)]">
        Un auteur absent du registre doit y être ajoute par la moderation : le registre des
        contributeurs est commun a tout le catalogue.
      </p>
    </section>
  );
}
