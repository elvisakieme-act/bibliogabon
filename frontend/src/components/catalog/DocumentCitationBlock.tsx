import { useState } from "react";

import type { DocumentMetadata } from "@/api/types";
import { documentCitation } from "@/components/catalog/documentCitation";

/**
 * La référence, prête à recopier.
 *
 * Une bibliothèque académique qui ne donne pas la référence oblige chaque
 * lecteur à la reconstituer — et c'est ainsi qu'un mémoire gabonais finit cité
 * sans son établissement. Le bouton copie ; le texte reste sélectionnable pour
 * qui préfère le faire à la main, ou pour qui n'a pas de presse-papiers.
 */
export function DocumentCitationBlock({ document }: { document: DocumentMetadata }) {
  const [copie, setCopie] = useState(false);
  // L'adresse réelle de la page, pas une adresse reconstruite : une référence
  // qui pointe ailleurs que là où le lecteur se trouve est une référence fausse.
  const reference = documentCitation(
    document,
    typeof window === "undefined" ? "" : window.location.href
  );

  async function copier() {
    try {
      await navigator.clipboard.writeText(reference);
      setCopie(true);
      window.setTimeout(() => setCopie(false), 2500);
    } catch {
      // Presse-papiers refusé : le texte reste sélectionnable, et prétendre
      // avoir copié serait pire que ne rien dire.
    }
  }

  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--navy-soft)] p-5">
      <p className="font-display text-lg text-[var(--navy)]">Citer ce document</p>
      <p className="mt-3 text-sm leading-relaxed text-[var(--ink)]">{reference}</p>
      <button
        type="button"
        onClick={() => void copier()}
        className="mt-4 inline-flex items-center gap-2 rounded-lg border border-[var(--border)] bg-white px-3.5 py-2 text-sm font-semibold text-[var(--navy)] transition hover:border-[var(--navy-soft)] hover:bg-[var(--navy-soft)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--gold)]"
      >
        {copie ? "Référence copiée" : "Copier la référence"}
      </button>
    </div>
  );
}
