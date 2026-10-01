import { useEffect, useState } from "react";

/**
 * Suivre une requête média, et la suivre vraiment.
 *
 * Interrogée une seule fois au premier rendu, la largeur de l'écran ne répond
 * plus : faire pivoter un téléphone de portrait à paysage ne changeait rien, et
 * la double page du lecteur restait repliée alors que la place existait. On
 * s'abonne donc aux changements.
 *
 * Le repli est `false` : dans un environnement sans `matchMedia` — jsdom n'en a
 * pas toujours un — mieux vaut la disposition la plus simple que de prétendre
 * disposer d'un grand écran.
 */
export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(() =>
    typeof window !== "undefined" && typeof window.matchMedia === "function"
      ? window.matchMedia(query).matches
      : false
  );

  useEffect(() => {
    if (typeof window.matchMedia !== "function") return;
    const media = window.matchMedia(query);
    const update = () => setMatches(media.matches);
    update();
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, [query]);

  return matches;
}
