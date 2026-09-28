import "@testing-library/jest-dom/vitest";

import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// Testing Library ne nettoie automatiquement que si le framework expose
// `afterEach` en global. Vitest n'est pas configuré avec `globals: true`
// ici, donc le nettoyage n'avait jamais lieu : le DOM s'accumulait d'un
// test à l'autre, et un `getByLabelText` pouvait trouver le formulaire
// rendu par le test précédent.
afterEach(cleanup);

window.scrollTo = () => {};

/**
 * jsdom n'implémente pas `ResizeObserver`.
 *
 * La couche texte du lecteur s'en sert pour réajuster la largeur des mots
 * après un redimensionnement. C'est l'environnement de test qui est
 * incomplet, pas le code : on le complète ici plutôt que d'ajouter au
 * composant une garde qui n'aurait aucun sens dans un navigateur.
 */
if (!("ResizeObserver" in globalThis)) {
  globalThis.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  } as unknown as typeof ResizeObserver;
}
