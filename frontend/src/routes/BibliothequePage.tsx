import type { FavoriteItem, ReadingProgressItem } from "@/api/types";
import { DocumentCard } from "@/components/catalog/DocumentCard";
import { RequireAuth } from "@/auth/guards";
import { SiteLayout } from "@/components/layout/SiteLayout";
import { EmptyState } from "@/components/ui/EmptyState";
import { Skeleton } from "@/components/ui/Skeleton";
import { useAuth } from "@/auth/AuthProvider";
import { useFavorites, useReadingProgress, useRemoveFavorite } from "@/features/library/hooks";

export function BibliothequePage() {
  return <RequireAuth><LibraryContent /></RequireAuth>;
}

function LibraryContent() {
  const { user } = useAuth();
  const favorites = useFavorites();
  const progress = useReadingProgress();
  const removeFavorite = useRemoveFavorite();

  if (favorites.isPending || progress.isPending) {
    return <SiteLayout><main className="container-editorial py-10 sm:py-14"><Skeleton label="Chargement de votre bibliotheque" /></main></SiteLayout>;
  }

  if (favorites.isError || progress.isError) {
    return <SiteLayout><main className="container-editorial py-10 sm:py-14"><EmptyState title="Bibliotheque indisponible" description="Reessayez dans quelques instants." /></main></SiteLayout>;
  }

  return (
    <SiteLayout>
      <main className="container-editorial py-10 sm:py-14">
        <p className="text-sm font-semibold uppercase tracking-[0.18em] text-[var(--green)]">Ma collection</p>
        <h1 className="mt-3 font-display text-4xl font-semibold text-[var(--navy)]">Bonjour, {user?.display_name}</h1>
        <p className="mt-3 max-w-2xl text-muted-foreground">Retrouvez vos documents enregistres et reprenez vos lectures en cours.</p>
        <LibrarySection
          favorites={favorites.data?.results ?? []}
          progress={progress.data?.results ?? []}
          onRemoveFavorite={(documentId) => removeFavorite.mutate(documentId)}
          removingFavoriteId={removeFavorite.isPending ? removeFavorite.variables : undefined}
        />
      </main>
    </SiteLayout>
  );
}

export function LibrarySection({
  favorites,
  progress,
  onRemoveFavorite,
  removingFavoriteId
}: {
  favorites: FavoriteItem[];
  progress: ReadingProgressItem[];
  onRemoveFavorite?: (documentId: number) => void;
  removingFavoriteId?: number | string;
}) {
  return (
    <div className="mt-8 space-y-12">
      <section aria-label="Apercu de la bibliotheque" className="grid gap-4 sm:grid-cols-2">
        <div className="border border-border bg-white p-5 shadow-editorial"><p className="text-sm text-muted-foreground">Documents favoris</p><p className="mt-2 font-display text-3xl font-semibold text-[var(--navy)]">{favorites.length}</p></div>
        <div className="border border-border bg-white p-5 shadow-editorial"><p className="text-sm text-muted-foreground">Lectures en cours</p><p className="mt-2 font-display text-3xl font-semibold text-[var(--navy)]">{progress.length}</p></div>
      </section>
      <section aria-labelledby="continue-reading">
        <h2 id="continue-reading" className="font-display text-3xl font-semibold text-[var(--navy)]">Reprendre la lecture</h2>
        {progress.length ? <div className="mt-5 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">{progress.map((item) => <article key={item.document.id} className="border border-border bg-white p-5 shadow-editorial"><h3 className="font-display text-xl leading-tight text-[var(--navy)]">{item.document.title}</h3><p className="mt-2 text-sm text-muted-foreground">Page {item.last_page_number} sur {item.document.page_count ?? "-"}</p><a href={`/lecture/${item.document.id}`} className="mt-4 inline-flex border-b-2 border-[var(--gold)] pb-1 text-sm font-semibold text-[var(--navy)] hover:text-[var(--green)]">Reprendre</a></article>)}</div> : <div className="mt-5"><EmptyState title="Aucune lecture en cours" description="Vos documents commencés apparaitront ici." /></div>}
      </section>
      <section aria-labelledby="favorites">
        <h2 id="favorites" className="font-display text-3xl font-semibold text-[var(--navy)]">Mes favoris</h2>
        {favorites.length ? <div className="mt-5 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">{favorites.map((item) => <DocumentCard key={item.document.id} document={item.document} favorite={{ isFavorite: true, onToggle: () => onRemoveFavorite?.(item.document.id), isPending: removingFavoriteId === item.document.id }} />)}</div> : <div className="mt-5"><EmptyState title="Aucun favori" description="Ajoutez des documents a vos favoris depuis votre bibliotheque." /></div>}
      </section>
    </div>
  );
}
