interface LogoProps {
  withWordmark?: boolean;
  /**
   * Faux dans le lecteur, où la marque n'est qu'une identité.
   *
   * Un logo cliquable y ferait une seconde sortie, concurrente du bouton
   * « Retour » — et celle-là quitterait la lecture sans que rien l'annonce.
   */
  linkToHome?: boolean;
  /**
   * Marque réduite, mot-symbole masqué sous `sm`.
   *
   * Dans la barre du lecteur, la marque est centrée sur toute la largeur
   * tandis que la position et la sortie occupent les côtés : sur un
   * téléphone, les trois zones se recouvrent et le compteur de pages passe
   * derrière le nom. Observé à 390 px — aucun test de rendu ne le voit, car
   * jsdom ne met rien en page.
   */
  compact?: boolean;
  className?: string;
}

export function Logo({
  withWordmark = true,
  linkToHome = true,
  compact = false,
  className
}: LogoProps) {
  const content = (
    <>
      <img src="/bibliogabon-logo.png" alt="" className={compact ? "h-7 w-7" : "h-10 w-10"} />
      {withWordmark ? (
        <span className={`font-display ${compact ? "hidden text-lg sm:inline" : "text-xl"}`}>
          BiblioGABON
        </span>
      ) : null}
    </>
  );
  const shared = `inline-flex items-center gap-2 ${className ?? ""}`;

  if (!linkToHome) {
    return (
      <span className={shared} aria-label="BiblioGABON">
        {content}
      </span>
    );
  }

  return (
    <a href="/" aria-label="BiblioGABON" className={shared}>
      {content}
    </a>
  );
}
