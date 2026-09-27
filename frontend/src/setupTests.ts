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
