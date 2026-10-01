import type { DocumentMetadata } from "@/api/types";

/**
 * Les documents eux-mêmes, en guise de preuve.
 *
 * L'accroche montrait une photo d'archives : des étudiants qui pourraient
 * être ceux de n'importe quelle université du monde. Les couvertures, elles,
 * sont ce que cette bibliothèque contient et que personne d'autre ne peut
 * montrer — la page de titre d'un mémoire soutenu à Libreville.
 *
 * Elles se chevauchent comme sur une étagère plutôt que de s'aligner en
 * grille : une grille dirait « voici quatre produits », un rayonnage dit
 * « voici un fonds ». L'inclinaison est faible et alternée, pas aléatoire —
 * un désordre calculé se remarque, un désordre réel fatigue.
 */
const TILTS = ["-rotate-3", "rotate-1", "-rotate-1", "rotate-3"];

export function CoverShelf({ documents }: { documents: DocumentMetadata[] }) {
  const shown = documents.filter((document) => document.cover).slice(0, 4);
  if (shown.length === 0) return null;

  return (
    <ul
      aria-label="Documents du catalogue"
      className="flex items-end justify-center lg:justify-center"
    >
      {shown.map((document, index) => (
        <li key={document.id} className={index === 0 ? "" : "-ms-6 sm:-ms-8"}>
          <a
            href={`/documents/${document.id}`}
            className={`block w-24 overflow-hidden rounded-sm shadow-[0_18px_40px_-18px_rgba(0,0,0,0.75)] transition-transform duration-300 hover:-translate-y-2 focus-visible:-translate-y-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--gold)] sm:w-36 lg:w-40 ${TILTS[index % TILTS.length]}`}
          >
            <img
              src={document.cover ?? undefined}
              alt=""
              loading="lazy"
              className="block aspect-[1/1.414] w-full object-cover"
            />
            <span className="sr-only">{document.title}</span>
          </a>
        </li>
      ))}
    </ul>
  );
}
