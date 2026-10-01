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
        [
          {
            target,
            isIntersecting: true,
            // La part visible, et pas seulement « il intersecte » : le
            // lecteur choisit la page **la plus** visible, donc un
            // palliatif qui l'omet lui fait croire qu'aucune page ne l'est.
            intersectionRatio: 1
          } as unknown as IntersectionObserverEntry
        ],
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

/**
 * jsdom n'implémente pas `<dialog>.showModal()`.
 *
 * Les options d'affichage du lecteur reposent sur l'élément natif, qui
 * apporte le piège de focus, la fermeture par Échap et l'inertie de la page —
 * quatre comportements qu'une modale en `<div>` doit réimplémenter. Le
 * palliatif reproduit l'ouverture et la fermeture, pas l'isolation : ce que
 * les tests vérifient ici, c'est le contenu et les choix, pas le
 * comportement du navigateur.
 */
if (typeof HTMLDialogElement !== "undefined" && !HTMLDialogElement.prototype.showModal) {
  HTMLDialogElement.prototype.showModal = function showModal() {
    this.open = true;
  };
  HTMLDialogElement.prototype.close = function close() {
    this.open = false;
    this.dispatchEvent(new Event("close"));
  };
}

/**
 * jsdom n'implémente pas `PointerEvent`.
 *
 * Sans lui, un événement de pointeur est fabriqué comme un `Event` nu :
 * `clientX` ne voyage pas, et un geste de glissement arrive au gestionnaire
 * sans coordonnées. Le test échoue alors sur « le geste n'a rien fait »,
 * ce qui envoie la recherche du défaut vers le composant plutôt que vers
 * l'environnement.
 */
if (typeof window.PointerEvent === "undefined") {
  class TestPointerEvent extends MouseEvent {
    readonly pointerId: number;
    readonly pointerType: string;
    readonly isPrimary: boolean;

    constructor(type: string, init: PointerEventInit = {}) {
      super(type, init);
      this.pointerId = init.pointerId ?? 0;
      this.pointerType = init.pointerType ?? "mouse";
      this.isPrimary = init.isPrimary ?? true;
    }
  }
  window.PointerEvent = TestPointerEvent as unknown as typeof PointerEvent;
  globalThis.PointerEvent = window.PointerEvent;
}

/**
 * jsdom n'implémente pas la capture de pointeur.
 *
 * Les coins de page du mode livre s'en servent pour que le déplacement ne
 * parte pas au visualiseur en dessous, qui le prendrait pour un panoramique.
 * Sans palliatif, le geste lève une exception et le test échoue sur la
 * conséquence plutôt que sur la cause.
 */
if (typeof Element !== "undefined" && !Element.prototype.setPointerCapture) {
  Element.prototype.setPointerCapture = () => {};
  Element.prototype.releasePointerCapture = () => {};
  Element.prototype.hasPointerCapture = () => false;
}

/**
 * jsdom n'implémente pas `scrollIntoView`.
 *
 * Le lecteur s'en sert pour amener une page sous les yeux quand la barre la
 * demande. Sans palliatif, le composant lève une exception au montage et les
 * tests échouent sur la conséquence plutôt que sur la cause.
 */
if (typeof Element !== "undefined" && !Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = () => {};
}
