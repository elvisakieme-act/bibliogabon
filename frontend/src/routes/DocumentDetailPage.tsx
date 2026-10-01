import { Link, useParams } from "@tanstack/react-router";

import { DocumentCitationBlock } from "@/components/catalog/DocumentCitationBlock";
import { DocumentCover } from "@/components/catalog/DocumentCover";
import { DocumentNotice } from "@/components/catalog/DocumentNotice";
import { SearchResultCard } from "@/components/catalog/SearchResultCard";
import { documentAccessNote } from "@/components/catalog/documentAccess";
import { SiteLayout } from "@/components/layout/SiteLayout";
import { EmptyState } from "@/components/ui/EmptyState";
import { Skeleton } from "@/components/ui/Skeleton";
import { useDocument, useSearch } from "@/features/catalog/hooks";
import { documentDetailReadLabel } from "@/routes/documentDetailLabels";

/**
 * La fiche d'un document.
 *
 * C'est la page qui transforme un visiteur en lecteur, et c'était la plus vide
 * du parcours : quatre champs, un bouton, et la moitié de l'écran en blanc.
 * Rien n'y permettait de répondre à la seule question qu'on se pose devant un
 * document — est-ce celui qu'il me faut, et puis-je le lire maintenant ?
 *
 * Elle répond donc dans cet ordre : ce que c'est (la nature académique, qui
 * était dans la charge utile sans jamais être affichée), qui l'a écrit et où,
 * ce qu'il contient, ce que l'accès autorise **en toutes lettres**, comment le
 * citer, et ce qu'il y a d'autre dans le même domaine.
 */
export function DocumentDetailPage() {
  const { id } = useParams({ from: "/documents/$id" });
  const document = useDocument(id);
  const item = document.data;
  // Les voisins de domaine passent par la recherche : le point d'entrée du
  // catalogue ne prend aucun filtre. Rien n'est demandé tant que le domaine
  // n'est pas connu, sans quoi la requête ramènerait tout le catalogue.
  const sameDomain = useSearch(
    { domain: item?.domain?.slug, page_size: 4 },
    { enabled: Boolean(item?.domain?.slug) }
  );

  if (document.isPending)
    return (
      <SiteLayout>
        <main className="container-editorial py-10">
          <Skeleton label="Chargement du document" />
        </main>
      </SiteLayout>
    );
  if (document.isError || !item)
    return (
      <SiteLayout>
        <main className="container-editorial py-10">
          <EmptyState
            title="Document indisponible"
            description="Ce document est introuvable ou temporairement indisponible."
          />
        </main>
      </SiteLayout>
    );

  const cta = documentDetailReadLabel(item);
  const voisins = (sameDomain.data?.results ?? []).filter((voisin) => voisin.id !== item.id);

  return (
    <SiteLayout>
      <main>
        {/* Bandeau sombre, comme l'accueil : le document s'y présente en entier
            — sa nature, son titre, ses auteurs et l'action de lecture — avant
            tout détail. Un lecteur qui sait déjà ce qu'il cherche n'a pas à
            défiler pour ouvrir. */}
        <section className="bg-[var(--navy-deep)] text-white">
          {/* Hors de la grille : sur un écran étroit la couverture passe en
              premier, et le fil d'Ariane se retrouvait sous elle — on dit d'où
              l'on vient avant de montrer où l'on est. */}
          <nav
            aria-label="Fil d'Ariane"
            className="container-editorial pt-8 text-sm text-white/60"
          >
            <Link to="/catalogue" className="hover:text-white hover:underline">
              Catalogue
            </Link>
            {item.domain ? (
              <>
                <span aria-hidden="true"> / </span>
                <Link
                  to="/domaines/$slug"
                  params={{ slug: item.domain.slug }}
                  className="hover:text-white hover:underline"
                >
                  {item.domain.name}
                </Link>
              </>
            ) : null}
          </nav>
          <div className="container-editorial grid gap-8 pb-10 pt-6 sm:pb-12 lg:grid-cols-[minmax(0,1fr)_15rem] lg:items-center lg:gap-14">
            <div className="order-2 lg:order-1">
              {/* Le filet du drapeau tient lieu de dos de reliure le long du
                  titre, comme sur l'accueil. */}
              <div className="flex gap-6">
                <span className="w-1 shrink-0 rounded-full gabon-stripe-v" aria-hidden="true" />
                <div>
                  {item.document_type ? (
                    <p className="font-semibold text-[var(--gold)]">
                      {item.document_type.name}
                    </p>
                  ) : null}
                  <h1 className="mt-2 font-display text-[clamp(1.9rem,3.2vw,2.75rem)] font-semibold leading-[1.15]">
                    {item.title}
                  </h1>
                  {item.authors.length > 0 ? (
                    <p className="mt-4 text-lg text-white/85">
                      {item.authors.map((auteur) => auteur.display_name).join(" · ")}
                    </p>
                  ) : null}
                  {item.owner ? <p className="mt-1 text-white/60">{item.owner}</p> : null}
                </div>
              </div>

              <div className="mt-8 flex flex-wrap items-center gap-x-5 gap-y-3">
                {item.access.can_read ? (
                  <a
                    href={`/lecture/${item.id}`}
                    className="inline-flex rounded-lg bg-[var(--gold)] px-6 py-3 text-sm font-semibold text-[var(--navy-deep)] transition hover:bg-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white"
                  >
                    {cta}
                  </a>
                ) : item.access.reason === "authentication_required" ? (
                  <Link
                    to="/connexion"
                    search={{ next: `/documents/${item.id}` }}
                    className="inline-flex rounded-lg bg-[var(--gold)] px-6 py-3 text-sm font-semibold text-[var(--navy-deep)] transition hover:bg-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white"
                  >
                    {cta}
                  </Link>
                ) : (
                  <span className="inline-flex rounded-lg border border-white/25 px-6 py-3 text-sm font-semibold text-white/70">
                    {cta}
                  </span>
                )}
                {/* En toutes lettres plutôt qu'en étiquette : « institution_only »
                    n'apprend rien à un étudiant qui veut savoir s'il peut lire. */}
                <p className="max-w-md text-sm leading-relaxed text-white/70">
                  {documentAccessNote(item)}
                </p>
              </div>
            </div>

            {/* La couverture déborde sur la section claire : le bandeau était
                sinon creusé d'un vide sombre sous l'action, puisque c'est elle
                qui commande la hauteur. Elle y gagne la présence d'un ouvrage
                posé sur la page. Sur un écran étroit elle passe au-dessus et
                reste de la taille d'un livre tenu en main — pleine largeur,
                elle écrasait le titre. */}
            <div className="order-1 w-32 sm:w-40 lg:order-2 lg:relative lg:z-10 lg:-mb-20 lg:w-auto">
              <DocumentCover
                document={item}
                className="rounded-xl shadow-editorial-lg ring-1 ring-white/10"
              />
            </div>
          </div>
        </section>

        <section className="container-editorial grid gap-12 border-t border-border py-12 lg:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)] lg:gap-16 lg:pb-16 lg:pt-28">
          <div className="space-y-10">
            {item.abstract ? (
              <div>
                <h2 className="font-display text-2xl text-[var(--navy)]">Résumé</h2>
                {/* Mesure limitée : au-delà d'une soixantaine de signes par
                    ligne, l'œil perd la ligne suivante en revenant à gauche. */}
                <p className="mt-4 max-w-[62ch] text-lg leading-relaxed text-[var(--ink)]">
                  {item.abstract}
                </p>
              </div>
            ) : null}

            <DocumentCitationBlock document={item} />
          </div>

          <aside>
            <h2 className="font-display text-2xl text-[var(--navy)]">Notice</h2>
            <div className="mt-4">
              <DocumentNotice document={item} />
            </div>
          </aside>
        </section>

        {voisins.length > 0 && item.domain ? (
          <section className="border-t border-border bg-[var(--navy-soft)]">
            <div className="container-editorial py-12 sm:py-16">
              <h2 className="font-display text-2xl text-[var(--navy)]">
                Autres documents en {item.domain.name.toLowerCase()}
              </h2>
              <div className="mt-6 grid gap-4 md:grid-cols-2">
                {voisins.slice(0, 4).map((voisin) => (
                  <SearchResultCard key={voisin.id} result={voisin} />
                ))}
              </div>
            </div>
          </section>
        ) : null}
      </main>
    </SiteLayout>
  );
}
