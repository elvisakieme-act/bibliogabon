import { useCallback, useRef } from "react";

/**
 * Laquelle des pages aperçues est celle qu'on lit.
 *
 * Au défilement vertical, c'est la page la plus visible : les pages y sont plus
 * hautes que l'écran, donc celle qui en occupe la plus grande part est bien
 * celle qu'on lit. La bande horizontale ne peut pas s'en servir — plusieurs
 * pages entières y tiennent côte à côte, et « la plus visible » y désignait
 * toujours celle de gauche. Même question, deux réponses, deux mécanismes :
 * c'est en les confondant que les trois modes avaient été cassés ensemble.
 *
 * La page retenue est la plus visible, pas la dernière annoncée : tous les
 * observateurs parlent au premier rendu, et garder la dernière réponse donnait
 * la dernière page du document à l'ouverture.
 */
export function useMostVisiblePage(onVisiblePage: (pageNumber: number) => void) {
  const ratios = useRef(new Map<number, number>());
  const scheduled = useRef(false);
  const reported = useRef<number | null>(null);
  const visibleRef = useRef(onVisiblePage);
  visibleRef.current = onVisiblePage;

  const report = useCallback((page: number, ratio: number) => {
    ratios.current.set(page, ratio);
    if (scheduled.current) return;
    scheduled.current = true;
    requestAnimationFrame(() => {
      scheduled.current = false;
      let best: number | null = null;
      let bestRatio = 0;
      for (const [candidate, candidateRatio] of ratios.current) {
        // `>` et non `>=` : à égalité, la page la plus proche du début
        // l'emporte, puisque c'est elle qu'on lit en premier.
        if (candidateRatio > bestRatio) {
          bestRatio = candidateRatio;
          best = candidate;
        }
      }
      if (best !== null && best !== reported.current) {
        reported.current = best;
        visibleRef.current(best);
      }
    });
  }, []);

  return { report, reported };
}
