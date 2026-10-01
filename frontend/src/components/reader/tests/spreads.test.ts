import { describe, expect, it } from "vitest";

import { leadingPage, spreadOfPage, toSpreads } from "@/components/reader/spreads";
import type { IiifCanvas } from "@/features/reader/manifest";

/**
 * Le découpage d'un document en doubles pages.
 *
 * C'est l'endroit où une erreur ne se voit pas tout de suite et se voit
 * ensuite partout : apparier (1,2) au lieu de (2,3) place toute la suite à
 * l'envers, et un lecteur qui connaît ses pages s'en aperçoit avant nous.
 */
function canvas(number: number): IiifCanvas {
  return {
    id: `http://localhost/api/v1/reader/sessions/x/canvas/${number}`,
    width: 2480,
    height: 3508,
    items: [{ items: [{ body: { service: [] as never } }] }]
  } as unknown as IiifCanvas;
}

describe("doubles pages", () => {
  it("ouvre sur la couverture, seule", () => {
    // Un livre s'ouvre sur sa couverture : elle est à droite, sans vis-à-vis.
    const [premiere] = toSpreads([1, 2, 3, 4, 5].map(canvas));

    expect(premiere.left).toBeNull();
    expect(leadingPage(premiere)).toBe(1);
  });

  it("apparie ensuite les pages paires à gauche", () => {
    // La convention de l'imprimé : page paire à gauche, impaire à droite.
    const spreads = toSpreads([1, 2, 3, 4, 5].map(canvas));

    expect(spreads.map((s) => [s.left && leadingPage(s), s.right])).toHaveLength(3);
    expect(leadingPage(spreads[1])).toBe(2);
    expect(leadingPage(spreads[2])).toBe(4);
  });

  it("laisse la dernière page seule quand le compte est pair", () => {
    // Quatre pages : couverture, puis (2,3), puis 4 sans vis-à-vis.
    const spreads = toSpreads([1, 2, 3, 4].map(canvas));

    expect(spreads).toHaveLength(3);
    expect(spreads[2].right).toBeNull();
    expect(leadingPage(spreads[2])).toBe(4);
  });

  it("retrouve la double d'une page, qu'elle soit à gauche ou à droite", () => {
    const spreads = toSpreads([1, 2, 3, 4, 5].map(canvas));

    expect(spreadOfPage(spreads, 1)).toBe(0);
    expect(spreadOfPage(spreads, 2)).toBe(1);
    expect(spreadOfPage(spreads, 3)).toBe(1);
    expect(spreadOfPage(spreads, 4)).toBe(2);
  });

  it("retombe sur la première double pour une page absente", () => {
    // Le manifeste omet les pages non tuilées plutôt que d'inventer leurs
    // dimensions : un lien de reprise peut donc désigner une page qui n'y
    // figure pas, et le lecteur doit s'ouvrir quand même.
    const spreads = toSpreads([1, 2, 3].map(canvas));

    expect(spreadOfPage(spreads, 99)).toBe(0);
  });

  it("ne produit aucune double pour un document vide", () => {
    expect(toSpreads([])).toEqual([]);
  });
});
