const FALLBACKS = [
  "from-[var(--navy)] via-[var(--green)] to-[var(--gold)]",
  "from-[var(--green)] via-[var(--navy)] to-[var(--gold)]",
  "from-[var(--gold)] via-[var(--green)] to-[var(--navy)]"
];

/**
 * Ce dont une couverture a besoin, et rien de plus.
 *
 * Le composant exigeait un `DocumentMetadata` entier, ce qui l'interdisait aux
 * résultats de recherche — qui ont leur propre forme de charge. Une vignette
 * n'a besoin que d'une adresse et de quoi choisir un repli.
 */
export interface CoverSubject {
  cover: string | null;
  title: string;
  domain?: { slug: string } | null;
}

export function DocumentCover({
  document,
  className = ""
}: {
  document: CoverSubject;
  className?: string;
}) {
  if (document.cover) {
    return (
      // Une page rendue est au format d'un document, pas d'une photo : le
      // ratio 3/4 la montre presque entière au lieu de la rogner sur les
      // côtés. `object-top` garde le titre, qui est en haut de page.
      <img
        src={document.cover}
        alt=""
        loading="lazy"
        className={`aspect-[3/4] w-full bg-[var(--navy-soft)] object-cover object-top ${className}`}
      />
    );
  }

  const fallback =
    FALLBACKS[(document.domain?.slug.length ?? document.title.length) % FALLBACKS.length];
  return (
    <div
      className={`relative flex aspect-[3/4] w-full overflow-hidden bg-gradient-to-br ${fallback} p-5 text-white ${className}`}
      aria-hidden="true"
    >
      <span className="absolute inset-3 border border-white/25" />
      <span className="absolute bottom-5 left-5 h-1 w-16 bg-white/70" />
    </div>
  );
}
