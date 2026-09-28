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

/**
 * jsdom n'implémente pas `IntersectionObserver`.
 *
 * Le lecteur s'en sert pour charger une page à l'approche de l'écran et pour
 * savoir laquelle est lue. Le palliatif signale l'intersection **dès
 * l'observation** : dans un vrai navigateur, un élément présent dans la
 * fenêtre intersecte, et un palliatif silencieux ferait passer des tests sur
 * un lecteur qui ne charge jamais rien.
 */
if (!("IntersectionObserver" in globalThis)) {
  globalThis.IntersectionObserver = class {
    private readonly callback: IntersectionObserverCallback;

    constructor(callback: IntersectionObserverCallback) {
      this.callback = callback;
    }

    observe(target: Element) {
      this.callback(
        [{ target, isIntersecting: true } as unknown as IntersectionObserverEntry],
        this as unknown as IntersectionObserver
      );
    }

    unobserve() {}
    disconnect() {}
    takeRecords(): IntersectionObserverEntry[] {
      return [];
    }
  } as unknown as typeof IntersectionObserver;
}

/**
 * jsdom n'implémente pas `URL.createObjectURL`.
 *
 * Le lecteur s'en sert pour afficher une image de page récupérée avec son
 * jeton d'authentification — une balise `<img src>` ne peut pas porter
 * d'en-tête. Le palliatif rend une adresse reconnaissable et retient les
 * révocations, pour qu'un test puisse vérifier qu'aucune n'est oubliée.
 */
const revokedObjectUrls: string[] = [];
(globalThis as { __revokedObjectUrls?: string[] }).__revokedObjectUrls = revokedObjectUrls;

let objectUrlCounter = 0;
const nativeRevoke = URL.revokeObjectURL?.bind(URL);
URL.createObjectURL = () => `blob:bibliogabon/${++objectUrlCounter}`;
URL.revokeObjectURL = (url: string) => {
  revokedObjectUrls.push(url);
  nativeRevoke?.(url);
};

/**
 * jsdom n'implémente pas `matchMedia`.
 *
 * OpenSeadragon l'interroge au démarrage. Sans lui, le lecteur entier échoue
 * — et l'échec se présente comme une absence d'élément, ce qui envoie la
 * recherche du défaut au mauvais endroit.
 */
if (typeof window.matchMedia !== "function") {
  window.matchMedia = ((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener: () => {},
    removeEventListener: () => {},
    addListener: () => {},
    removeListener: () => {},
    dispatchEvent: () => false
  })) as unknown as typeof window.matchMedia;
}
