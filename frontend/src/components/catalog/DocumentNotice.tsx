import type { DocumentMetadata } from "@/api/types";
import { documentCategoryLabel } from "@/components/catalog/documentAccess";

/**
 * La notice du document : ce qu'une bibliothèque appelle une notice.
 *
 * Pas une grille de cartes, mais une liste de descriptions à filets — la forme
 * d'un catalogue de bibliothèque, qui se parcourt du regard par la colonne de
 * gauche. Les quatre champs d'avant (auteur, publication, langue, pages)
 * laissaient de côté ce qu'un lecteur universitaire regarde en premier : la
 * **nature** du document. Un cours, une thèse et un sujet d'examen ne se lisent
 * pas pour les mêmes raisons, et l'information était dans la charge utile sans
 * jamais être affichée.
 *
 * Une ligne absente ne s'affiche pas. Écrire « Non renseigné » cinq fois
 * remplit la notice de vide et rend illisible ce qui est réellement là.
 */
const LANGUES: Record<string, string> = {
  fr: "Français",
  en: "Anglais"
};

export function DocumentNotice({ document }: { document: DocumentMetadata }) {
  const lignes: Array<{ terme: string; valeur: string }> = [];

  if (document.document_type)
    lignes.push({ terme: "Nature", valeur: document.document_type.name });
  if (document.domain) lignes.push({ terme: "Domaine", valeur: document.domain.name });
  if (document.owner) lignes.push({ terme: "Établissement", valeur: document.owner });
  if (document.publication_year) {
    lignes.push({ terme: "Année", valeur: String(document.publication_year) });
  }
  lignes.push({
    terme: "Langue",
    valeur: LANGUES[document.language_code] ?? document.language_code.toUpperCase()
  });
  if (document.page_count) {
    lignes.push({
      terme: "Pages",
      valeur: `${document.page_count} page${document.page_count > 1 ? "s" : ""}`
    });
  }
  const regime = documentCategoryLabel(document.category);
  if (regime) lignes.push({ terme: "Régime de dépôt", valeur: regime });

  return (
    <dl className="divide-y divide-[var(--border)] border-y border-[var(--border)] text-sm">
      {lignes.map((ligne) => (
        <div key={ligne.terme} className="grid grid-cols-[8.5rem_minmax(0,1fr)] gap-4 py-3">
          <dt className="text-[var(--muted-foreground)]">{ligne.terme}</dt>
          <dd className="font-medium text-[var(--navy)]">{ligne.valeur}</dd>
        </div>
      ))}
    </dl>
  );
}
