import { describe, expect, it } from "vitest";

import {
  centredPage,
  pageHeightInStrip,
  stripSidePadding
} from "@/components/reader/stripLayout";

/**
 * L'arithmétique du défilement horizontal.
 *
 * Elle est éprouvée ici parce que jsdom ne mesure rien : une page y est
 * toujours large de zéro, et ces deux calculs n'auraient eu pour témoin qu'une
 * capture d'écran. Les deux défauts du premier jet étaient précisément là.
 */
const A4 = { width: 2480, height: 3508 };

describe("hauteur d'une page de la bande", () => {
  it("ajuste à la hauteur sur un écran large", () => {
    // Le cas ordinaire : une page A4 est plus haute que large, et c'est la
    // hauteur qui manque.
    expect(pageHeightInStrip({ width: 1392, height: 803 }, A4, 1)).toBe(803);
  });

  it("ajuste à la largeur sur un téléphone tenu droit", () => {
    // Ajustée à la seule hauteur, la page devenait plus large que l'écran : il
    // fallait défiler de côté *à l'intérieur* d'une page pour en lire une
    // ligne, dans un mode qui promet la page entière.
    const height = pageHeightInStrip({ width: 342, height: 763 }, A4, 1);

    expect(height).toBe(483);
    // Et la largeur qui en découle tient dans l'écran.
    expect(height! * (A4.width / A4.height)).toBeLessThanOrEqual(342);
  });

  it("laisse une page couchée tenir en largeur", () => {
    // Un plan ou un tableau en paysage : c'est encore la largeur qui commande,
    // même sur un grand écran.
    const paysage = { width: 3508, height: 2480 };

    expect(pageHeightInStrip({ width: 1392, height: 803 }, paysage, 1)).toBe(803);
    expect(pageHeightInStrip({ width: 900, height: 803 }, paysage, 1)).toBe(636);
  });

  it("multiplie par le zoom, et laisse alors dépasser", () => {
    const base = pageHeightInStrip({ width: 1392, height: 803 }, A4, 1)!;

    // Au pixel près, et par en dessous : la page agrandie doit rester celle
    // qu'on a demandée, sans jamais arrondir au-delà de la place offerte.
    const agrandie = pageHeightInStrip({ width: 1392, height: 803 }, A4, 2.5)!;
    expect(agrandie).toBeLessThanOrEqual(base * 2.5);
    expect(agrandie).toBeGreaterThan(base * 2.5 - 1);

    const reduite = pageHeightInStrip({ width: 1392, height: 803 }, A4, 0.5)!;
    expect(reduite).toBeLessThanOrEqual(base * 0.5);
    expect(reduite).toBeGreaterThan(base * 0.5 - 1);
  });

  it("ne donne pas de hauteur avant d'avoir mesuré", () => {
    // Une hauteur nulle n'afficherait rien du tout ; sans hauteur, la page
    // garde celle de la feuille de style.
    expect(pageHeightInStrip({ width: 0, height: 0 }, A4, 1)).toBeNull();
    expect(pageHeightInStrip({ width: 1392, height: 0 }, A4, 1)).toBeNull();
  });
});

describe("espace réservé au début et à la fin de la bande", () => {
  it("laisse la première page venir au centre", () => {
    // Sans cet espace, le défilement s'arrêtait avant : à l'ouverture d'un
    // cours de 157 pages, la page la plus centrée était la deuxième, et la
    // barre annonçait « Page 2 sur 157 » d'un document qu'on venait d'ouvrir.
    const box = { width: 1392, height: 803 };
    const padding = stripSidePadding(box, A4, 1);
    const width = pageHeightInStrip(box, A4, 1)! * (A4.width / A4.height);

    expect(padding).toBeGreaterThan(0);
    // Décalée de cet espace, la page occupe exactement le milieu.
    expect(padding + width / 2).toBeCloseTo(box.width / 2, 0);
  });

  it("ne réserve rien quand la page déborde déjà", () => {
    // Agrandie, la page est plus large que la fenêtre : le défilement la
    // parcourt d'un bord à l'autre, il n'y a rien à centrer.
    expect(stripSidePadding({ width: 1392, height: 803 }, A4, 3)).toBe(0);
  });

  it("ne réserve rien avant d'avoir mesuré, ni sans page", () => {
    expect(stripSidePadding({ width: 0, height: 0 }, A4, 1)).toBe(0);
    expect(stripSidePadding({ width: 1392, height: 803 }, undefined, 1)).toBe(0);
  });
});

describe("page que l'on lit", () => {
  const pages = [
    { page: 6, left: 100, width: 400 },
    { page: 7, left: 540, width: 400 },
    { page: 8, left: 980, width: 400 }
  ];

  it("retient celle qui est au centre, pas celle de gauche", () => {
    // Le défaut qu'on corrige : à visibilité égale, « la plus visible »
    // retenait la première de la liste. Le lecteur voyait la page 7 et lisait
    // « Page 6 sur 157 ».
    expect(centredPage(740, pages)).toBe(7);
  });

  it("suit le centre de la fenêtre", () => {
    expect(centredPage(300, pages)).toBe(6);
    expect(centredPage(1180, pages)).toBe(8);
  });

  it("tranche une égalité pour la page la plus proche du début", () => {
    // Deux pages à égale distance : c'est celle de gauche qu'on lit en premier.
    expect(centredPage(520, pages)).toBe(6);
  });

  it("n'annonce rien quand rien n'est encore mesuré", () => {
    // Annoncer la première page ferait perdre la sienne à qui reprend sa
    // lecture au milieu du document.
    expect(centredPage(740, [])).toBeNull();
  });
});
