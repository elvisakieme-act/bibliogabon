import { useCallback, useRef } from "react";

/**
 * Quelle page est réellement lue.
 *
 * Chaque emplacement signale la part de lui-même visible à l'écran. Retenir
 * simplement le dernier à parler donnait la dernière page du document dès
 * l'ouverture — tous les emplacements se déclarent au premier rendu, et
 * l'ordre d'arrivée n'a rien à voir avec ce que le lecteur regarde.
 *
 * On retient donc la page **la plus visible**, et on ne remonte le résultat
 * qu'une fois par image : pendant un défilement, les observateurs émettent
 * des dizaines de fois par seconde, et un rendu par émission rendrait le
 * lecteur saccadé.
 */
export function useVisiblePage(onChange: (pageNumber: number) => void) {
  const ratios = useRef(new Map<number, number>());
  // Un drapeau, pas l'identifiant rendu par `requestAnimationFrame` :
  // l'identifiant n'est affecté qu'**après** l'appel, si bien qu'une
  // implémentation qui exécute la fonction tout de suite laisse derrière elle
  // un identifiant qui bloque toutes les mesures suivantes.
  const scheduled = useRef(false);
  const reported = useRef<number | null>(null);

  return useCallback(
    (pageNumber: number, ratio: number) => {
      ratios.current.set(pageNumber, ratio);
      if (scheduled.current) return;

      scheduled.current = true;
      requestAnimationFrame(() => {
        scheduled.current = false;
        let best: number | null = null;
        let bestRatio = 0;
        for (const [candidate, candidateRatio] of ratios.current) {
          // `>` et non `>=` : à égalité, la page la plus haute l'emporte,
          // puisque c'est elle qu'on lit en premier.
          if (candidateRatio > bestRatio) {
            bestRatio = candidateRatio;
            best = candidate;
          }
        }
        if (best !== null && best !== reported.current) {
          reported.current = best;
          onChange(best);
        }
      });
    },
    [onChange]
  );
}
