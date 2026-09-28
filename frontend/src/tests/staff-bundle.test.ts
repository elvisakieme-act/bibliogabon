import { describe, expect, it } from "vitest";

/**
 * L'espace de gestion est charge a la demande : un lecteur ne doit pas
 * telecharger les ecrans de depot. Sans ce test, le premier import statique
 * ajoute vers `routes/gestion` annulerait la coupure sans rien casser de
 * visible — la regression serait un bundle plus lourd, que personne ne
 * remarque.
 */
describe("decoupage du bundle", () => {
  it("le fragment d'entree ne contient aucun module de l'espace de gestion", async () => {
    const { build } = await import("vite");
    const result = await build({
      logLevel: "silent",
      build: { write: false, minify: false }
    });
    const outputs = (Array.isArray(result) ? result : [result]) as Array<{
      output: Array<{
        type: string;
        isEntry?: boolean;
        fileName: string;
        modules?: Record<string, unknown>;
      }>;
    }>;
    const chunks = outputs.flatMap((bundle) => bundle.output);
    const entries = chunks.filter((chunk) => chunk.type === "chunk" && chunk.isEntry);

    expect(entries.length).toBeGreaterThan(0);
    const entryModules = entries.flatMap((entry) => Object.keys(entry.modules ?? {}));
    const staffModules = entryModules.filter(
      (id) => id.includes("routes/gestion") || id.includes("features/staff")
    );

    expect(staffModules).toEqual([]);

    // D013 promet que react-hook-form reste confine a /gestion. Sans cette
    // verification, la promesse ne serait qu'une intention : un usage depuis
    // un composant partage la ferait entrer dans le fragment du lecteur, qui
    // paierait 32 ko pour des formulaires qu'il ne voit jamais.
    //
    // Un import inutilise ne suffit pas a la declencher : rolldown l'elimine.
    // Ce qui compte, et ce que la verification attrape, est un usage
    // reellement atteignable depuis le rendu.
    expect(entryModules.filter((id) => id.includes("react-hook-form"))).toEqual([]);
  }, 120_000);

  it("le fragment d'entrée ne contient pas le moteur de tuiles", async () => {
    // OpenSeadragon pèse plus lourd que tout le reste du catalogue. Un
    // visiteur qui parcourt les documents sans en ouvrir un n'a aucune raison
    // de le télécharger — et sans ce test, le premier import statique vers le
    // lecteur annulerait la coupure sans rien casser de visible.
    const { build } = await import("vite");
    const result = await build({
      logLevel: "silent",
      build: { write: false, minify: false }
    });
    const outputs = (Array.isArray(result) ? result : [result]) as Array<{
      output: Array<{
        type: string;
        isEntry?: boolean;
        modules?: Record<string, unknown>;
      }>;
    }>;
    const entries = outputs
      .flatMap((bundle) => bundle.output)
      .filter((chunk) => chunk.type === "chunk" && chunk.isEntry);

    expect(entries.length).toBeGreaterThan(0);
    const entryModules = entries.flatMap((entry) => Object.keys(entry.modules ?? {}));

    expect(entryModules.filter((id) => id.includes("openseadragon"))).toEqual([]);
    expect(entryModules.filter((id) => id.includes("routes/LecturePage"))).toEqual([]);
  }, 120_000);
});
