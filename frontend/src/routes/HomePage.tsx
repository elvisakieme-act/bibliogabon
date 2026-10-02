import { Search } from "lucide-react";

import { DocumentCard } from "@/components/catalog/DocumentCard";
import { CoverShelf } from "@/components/home/CoverShelf";
import { SiteLayout } from "@/components/layout/SiteLayout";
import { Skeleton } from "@/components/ui/Skeleton";
import { useDocuments, useDomains } from "@/features/catalog/hooks";

/**
 * Ce que la plateforme garantit, à la place des logos qu'elle n'a pas.
 *
 * Une page d'accueil institutionnelle emprunte d'ordinaire sa crédibilité à
 * des partenaires. Les nôtres sont en discussion : afficher leur logo serait
 * fabriquer une caution, et cela se retourne violemment quand quelqu'un
 * vérifie. Ces trois phrases disent ce qui est vrai aujourd'hui du produit
 * lui-même, et chacune est tenue par du code et des tests.
 */
const GARANTIES = [
  {
    titre: "Le fichier d'origine ne sort jamais",
    texte:
      "Un document se lit page après page. Le PDF déposé reste sur la plateforme : aucune réponse n'expose son emplacement, et chaque page demandée vérifie que vous avez le droit de la lire."
  },
  {
    titre: "Les droits de l'auteur suivent le document",
    texte:
      "Chaque dépôt passe par une autorisation écrite, examinée par la modération. Ce que le lecteur peut faire du texte — le copier ou non — découle de l'accord signé, pas d'un réglage global."
  },
  {
    titre: "Pensé pour une connexion mobile",
    texte:
      "Les pages arrivent par fragments : votre téléphone ne télécharge que ce que vous regardez, et le zoom reste net jusqu'au détail d'un tableau."
  }
];

export function HomePage() {
  // Les dernières entrées, maintenant que le catalogue sait les ordonner.
  // L'accueil disait « quelques documents » parce que l'unique ordre était le
  // titre : annoncer une fraîcheur que l'ordre ne garantit pas aurait été une
  // contrevérité, et une page d'accueil n'en supporte aucune.
  const featured = useDocuments({ page_size: 4, ordering: "-published_at" });
  const domains = useDomains();
  const disciplines = domains.data?.results ?? [];

  return (
    <SiteLayout>
      <main>
        {/* L'accroche ne vend pas la bibliothèque : elle l'ouvre. Un étudiant
            arrive en cherchant quelque chose, pas pour être convaincu — la
            recherche est donc l'action principale, et les documents eux-mêmes
            tiennent lieu d'argument. */}
        <section className="relative overflow-hidden border-b border-border bg-[var(--navy-deep)] text-white">
          <div className="container-editorial grid items-center gap-10 py-12 sm:py-16 lg:grid-cols-[minmax(0,32rem)_minmax(0,1fr)] lg:gap-12 lg:py-16">
            <div>
              {/* Le filet du drapeau, vertical : il tient lieu de dos de
                  reliure le long du texte, là où une bande horizontale en
                  haut de page n'aurait été qu'un ornement de plus. */}
              <div className="flex gap-6">
                <span className="w-1 shrink-0 rounded-full gabon-stripe-v" aria-hidden="true" />
                <div>
                  <h1 className="font-display text-[clamp(2rem,3.6vw,3rem)] font-semibold leading-[1.12]">
                    Lire les thèses, les mémoires et les cours des universités gabonaises.
                  </h1>
                  <p className="mt-5 max-w-lg text-lg leading-relaxed text-white/80">
                    Chaque document se lit page après page, depuis un téléphone comme depuis un
                    ordinateur, dans le respect des droits de son auteur.
                  </p>
                </div>
              </div>

              <form
                action="/recherche"
                role="search"
                className="mt-9 flex flex-col gap-2 rounded-[var(--radius)] bg-white p-2 shadow-editorial-lg sm:flex-row"
              >
                <label className="sr-only" htmlFor="recherche-accueil">
                  Rechercher dans le catalogue
                </label>
                <input
                  id="recherche-accueil"
                  name="q"
                  placeholder="Un titre, un auteur, un sujet"
                  className="min-w-0 flex-1 rounded-[var(--radius)] px-4 py-3 text-[var(--navy)] outline-none placeholder:text-[var(--muted-foreground)]"
                />
                <button className="inline-flex items-center justify-center gap-2 rounded-[var(--radius)] bg-[var(--green)] px-6 py-3 font-semibold text-white transition hover:bg-[var(--navy)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--gold)] focus-visible:ring-offset-2">
                  <Search className="size-4" aria-hidden="true" />
                  Rechercher
                </button>
              </form>

              {/* Les disciplines réelles, cliquables : une information utile
                  au premier regard, là où une rangée de pastilles décoratives
                  n'aurait rien appris. */}
              {disciplines.length > 0 ? (
                <nav aria-label="Disciplines" className="mt-5 flex flex-wrap gap-x-5 gap-y-2">
                  {disciplines.slice(0, 6).map((domain) => (
                    <a
                      key={domain.id}
                      href={`/domaines/${domain.slug}`}
                      className="text-sm text-white/70 underline-offset-4 transition hover:text-[var(--gold)] hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--gold)]"
                    >
                      {domain.name}
                    </a>
                  ))}
                  <a
                    href="/catalogue"
                    className="text-sm font-semibold text-white underline-offset-4 transition hover:text-[var(--gold)] hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--gold)]"
                  >
                    Tout le catalogue
                  </a>
                </nav>
              ) : null}
            </div>

            <div className="lg:pb-4">
              <CoverShelf documents={featured.data?.results ?? []} />
            </div>
          </div>
        </section>

        <section className="border-b border-border bg-white">
          <div className="container-editorial py-14 sm:py-20">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-baseline sm:justify-between">
              <h2 className="font-display text-3xl font-semibold text-[var(--navy)] sm:text-4xl">
                Entrés récemment au catalogue
              </h2>
              <a
                href="/catalogue"
                className="font-semibold text-[var(--navy)] underline-offset-4 hover:text-[var(--green)] hover:underline"
              >
                Voir tout le catalogue
              </a>
            </div>
            {featured.isPending ? (
              <div className="mt-8 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
                <Skeleton />
                <Skeleton />
                <Skeleton />
                <Skeleton />
              </div>
            ) : featured.data?.results.length ? (
              <div className="mt-8 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
                {featured.data.results.map((document) => (
                  <DocumentCard key={document.id} document={document} />
                ))}
              </div>
            ) : (
              <p className="mt-8 text-muted-foreground">
                Le catalogue se remplit. Les premiers documents paraîtront ici.
              </p>
            )}
          </div>
        </section>

        {/* Trois phrases, séparées par un filet, et non trois cartes : des
            cartes identiques mettraient ces garanties au rang d'arguments de
            vente interchangeables. */}
        <section className="border-b border-border bg-[var(--surface-alt)]">
          <div className="container-editorial py-14 sm:py-20">
            <h2 className="max-w-2xl font-display text-3xl font-semibold text-[var(--navy)] sm:text-4xl">
              Déposer ici, c'est garder la main sur son travail
            </h2>
            <dl className="mt-10 grid gap-x-10 gap-y-8 sm:grid-cols-3">
              {GARANTIES.map(({ titre, texte }) => (
                <div key={titre} className="border-t border-[var(--navy)] pt-5">
                  <dt className="font-display text-xl font-semibold text-[var(--navy)]">
                    {titre}
                  </dt>
                  <dd className="mt-3 text-[15px] leading-relaxed text-muted-foreground">
                    {texte}
                  </dd>
                </div>
              ))}
            </dl>
          </div>
        </section>

        <section className="bg-white">
          <div className="container-editorial flex flex-col gap-5 py-14 sm:flex-row sm:items-center sm:justify-between sm:py-16">
            <div className="max-w-xl">
              <h2 className="font-display text-2xl font-semibold text-[var(--navy)] sm:text-3xl">
                Vous enseignez ou vous publiez&nbsp;?
              </h2>
              <p className="mt-2 text-muted-foreground">
                Déposez un cours, un mémoire ou une thèse. La modération vérifie les droits
                avant toute publication.
              </p>
            </div>
            <a
              href="/inscription"
              className="inline-flex shrink-0 items-center justify-center rounded-[var(--radius)] bg-[var(--navy)] px-6 py-3 font-semibold text-white shadow-editorial transition hover:bg-[var(--navy-deep)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--gold)] focus-visible:ring-offset-2"
            >
              Créer un compte déposant
            </a>
          </div>
        </section>
      </main>
    </SiteLayout>
  );
}
