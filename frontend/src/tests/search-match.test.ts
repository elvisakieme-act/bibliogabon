import { describe, expect, it } from "vitest";

import { matchedOnlyInText, searchMatchLabel } from "@/components/catalog/searchMatch";

/**
 * Pourquoi un résultat est là.
 *
 * Le serveur note un titre qui correspond mille fois plus haut qu'un mot croisé
 * au fil d'une page, et les deux s'affichaient de la même façon : une recherche
 * sur « droit » semblait ramener tout le catalogue.
 */
describe("provenance d'un résultat", () => {
  it("annonce la correspondance la plus forte, et une seule", () => {
    // Égrener « titre, résumé, texte » sur chaque ligne ferait du bruit là où
    // une phrase suffit.
    expect(searchMatchLabel(["title", "abstract", "text"])).toBe("Le titre correspond");
    expect(searchMatchLabel(["abstract", "text"])).toBe("Le résumé correspond");
  });

  it("nomme le texte du document quand il est la seule source", () => {
    expect(searchMatchLabel(["text"])).toBe("Trouvé dans le texte du document");
    expect(matchedOnlyInText(["text"])).toBe(true);
  });

  it("ne traite pas comme faible un résultat que son titre porte aussi", () => {
    expect(matchedOnlyInText(["title", "text"])).toBe(false);
  });

  it("se tait quand aucun mot n'a été cherché", () => {
    // Une liste filtrée par domaine n'a répondu à rien : annoncer une
    // correspondance ferait croire à une pertinence jamais calculée.
    expect(searchMatchLabel([])).toBeNull();
    expect(matchedOnlyInText([])).toBe(false);
  });

  it("survit à un serveur qui ne connaît pas encore le champ", () => {
    // Un frontend déployé devant un serveur plus ancien est ordinaire. La page
    // de résultats entière disparaissait sur un `undefined` — vu à l'écran, pas
    // en test : le serveur de développement servait encore l'ancien code.
    expect(searchMatchLabel(undefined)).toBeNull();
    expect(matchedOnlyInText(undefined)).toBe(false);
  });

  it("ignore un champ qu'elle ne connaît pas plutôt que de l'afficher", () => {
    // Le serveur peut nommer un champ nouveau avant que l'écran le sache :
    // « keywords » brut sur une fiche publique n'apprendrait rien.
    expect(searchMatchLabel(["keywords"])).toBeNull();
  });
});
