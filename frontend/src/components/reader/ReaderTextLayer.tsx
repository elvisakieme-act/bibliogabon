import { useLayoutEffect, useRef } from "react";

import type { ReaderPage as ReaderPagePayload, WordBox } from "@/api/types";

/**
 * Couche texte transparente, superposée à l'image de la page.
 *
 * L'image donne la mise en forme d'origine — titres, colonnes, tableaux,
 * figures, formules. Elle ne donne rien d'autre : ni sélection, ni recherche
 * dans la page, ni lecture d'écran. Cette couche rend tout cela, sans rien
 * masquer de l'image.
 *
 * Deux choix méritent d'être expliqués :
 *
 * - **La taille de police vient de la hauteur de la boîte**, exprimée en
 *   `cqh` : la page est un conteneur dimensionné, donc un mot garde sa taille
 *   relative quel que soit le zoom ou la largeur d'écran. Une taille en pixels
 *   se désaligneraut dès le premier redimensionnement.
 *
 * - **La largeur est corrigée après mesure.** Aucune police du navigateur ne
 *   reproduit exactement celle du document : le mot rendu est plus large ou
 *   plus étroit que sa boîte, et la sélection attraperait le mot voisin. On
 *   mesure donc la largeur réelle et on applique un `scaleX` — c'est ce que
 *   fait pdf.js, pour la même raison.
 */
export function ReaderTextLayer({
  words,
  policy
}: {
  words: WordBox[];
  policy: ReaderPagePayload["text_policy"];
}) {
  const container = useRef<HTMLDivElement>(null);

  useLayoutEffect(() => {
    const root = container.current;
    if (!root) return;
    const fit = () => {
      for (const span of Array.from(root.children) as HTMLElement[]) {
        // On repart de l'échelle neutre : sans cela, une seconde mesure
        // corrigerait une largeur déjà corrigée et le mot rétrécirait à
        // chaque redimensionnement.
        span.style.transform = "";
        const target = span.offsetWidth;
        const natural = span.scrollWidth;
        if (natural > 0 && target > 0 && Math.abs(natural - target) > 1) {
          span.style.transform = `scaleX(${target / natural})`;
        }
      }
    };
    fit();
    const observer = new ResizeObserver(fit);
    observer.observe(root);
    return () => observer.disconnect();
  }, [words]);

  if (words.length === 0) return null;

  // `select-none` empêche la copie sans rien retirer aux lecteurs d'écran ni
  // à la recherche dans la page : c'est le seul point de ce sujet où il n'y a
  // pas d'arbitrage. Mais c'est une dissuasion, pas une protection — le texte
  // est dans la page, et qui ouvre les outils du navigateur le récupère. La
  // seule protection réelle est `withheld`, où le serveur n'envoie rien.
  const protectedLayer = policy !== "selectable";

  return (
    <div
      ref={container}
      className={`absolute inset-0 ${protectedLayer ? "select-none" : "select-text"}`}
      style={{ containerType: "size" }}
      onCopy={protectedLayer ? (event) => event.preventDefault() : undefined}
      onContextMenu={protectedLayer ? (event) => event.preventDefault() : undefined}
    >
      {words.map(([x0, y0, x1, y1, word], index) => (
        <span
          // La position ne suffit pas comme clé : deux mots peuvent partager
          // une boîte après arrondi. L'index est stable ici, la liste ne
          // changeant jamais d'ordre pour une page donnée.
          key={`${index}-${word}`}
          className="absolute origin-top-left whitespace-pre text-transparent"
          style={{
            left: `${x0 * 100}%`,
            top: `${y0 * 100}%`,
            width: `${(x1 - x0) * 100}%`,
            height: `${(y1 - y0) * 100}%`,
            fontSize: `${(y1 - y0) * 100}cqh`,
            lineHeight: 1
          }}
        >
          {word}
        </span>
      ))}
    </div>
  );
}
