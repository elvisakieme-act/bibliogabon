import { canvasPageNumber, type IiifCanvas } from "@/features/reader/manifest";

/**
 * Le découpage d'un document en doubles pages.
 *
 * La couverture se présente seule, comme un livre qu'on ouvre : les pages
 * paires sont à gauche et les impaires à droite, ce qui est la convention de
 * l'imprimé. Apparier (1,2) placerait toute la suite à l'envers, et un
 * lecteur qui connaît ses pages le verrait tout de suite.
 *
 * Le manifeste omet les pages non tuilées plutôt que d'inventer leurs
 * dimensions : la position dans la liste n'est donc pas le numéro de page, et
 * l'appariement se fait sur le numéro réel.
 */
export interface Spread {
  /** Page de gauche, absente pour la couverture. */
  left: IiifCanvas | null;
  right: IiifCanvas | null;
}

export function toSpreads(canvases: IiifCanvas[]): Spread[] {
  if (canvases.length === 0) return [];
  const spreads: Spread[] = [{ left: null, right: canvases[0] }];
  for (let index = 1; index < canvases.length; index += 2) {
    spreads.push({ left: canvases[index], right: canvases[index + 1] ?? null });
  }
  return spreads;
}

/** La double page qui contient cette page. */
export function spreadOfPage(spreads: Spread[], pageNumber: number): number {
  const found = spreads.findIndex(
    (spread) =>
      (spread.left && canvasPageNumber(spread.left) === pageNumber) ||
      (spread.right && canvasPageNumber(spread.right) === pageNumber)
  );
  return found === -1 ? 0 : found;
}

/** La première page d'une double : celle qu'on annonce et qu'on enregistre. */
export function leadingPage(spread: Spread): number | null {
  const first = spread.left ?? spread.right;
  return first ? canvasPageNumber(first) : null;
}
