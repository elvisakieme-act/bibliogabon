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
    const staffModules = entries.flatMap((entry) =>
      Object.keys(entry.modules ?? {}).filter(
        (id) => id.includes("routes/gestion") || id.includes("features/staff")
      )
    );

    expect(staffModules).toEqual([]);
  }, 120_000);
});
