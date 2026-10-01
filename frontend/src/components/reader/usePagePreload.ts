import { useEffect, useRef, useState } from "react";

/**
 * Quand demander l'image d'une page.
 *
 * La seule chose que les deux défilements se partagent vraiment. Les charger
 * toutes inonderait la connexion — et le journal d'accès, qui enregistrerait
 * les 157 pages d'un cours comme lues avant que le lecteur en ait tourné une.
 * Et charger au moment où la page entre à l'écran la ferait apparaître vide :
 * il faut une marge d'avance.
 *
 * Le conteneur et le sens de l'avance viennent du mode : le vertical charge
 * vers le bas, l'horizontal vers la droite. C'est bien le conteneur qui défile
 * qu'il faut désigner, pas la fenêtre : une marge prise sur la fenêtre
 * n'avance rien, puisqu'elle n'élargit que la racine et qu'une page masquée
 * par le débordement d'un ancêtre reste masquée.
 *
 * En revanche *quelle* page est lue ne se partage pas : le défilement vertical
 * retient la plus visible, la bande horizontale celle qui est au centre. Même
 * mot, deux questions.
 */
export function usePagePreload({ root, margin }: { root: Element | null; margin: string }) {
  const holder = useRef<HTMLDivElement>(null);
  const [approaching, setApproaching] = useState(false);

  useEffect(() => {
    const element = holder.current;
    if (!element || approaching) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) setApproaching(true);
      },
      { root, rootMargin: margin }
    );
    observer.observe(element);
    return () => observer.disconnect();
  }, [approaching, margin, root]);

  return { holder, approaching };
}
