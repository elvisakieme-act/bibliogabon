import { useParams } from "@tanstack/react-router";

import { DocumentCover } from "@/components/catalog/DocumentCover";
import { DomainBadge } from "@/components/catalog/DomainBadge";
import { SiteLayout } from "@/components/layout/SiteLayout";
import { EmptyState } from "@/components/ui/EmptyState";
import { Skeleton } from "@/components/ui/Skeleton";
import { useDocument } from "@/features/catalog/hooks";

function detailCta(document: NonNullable<ReturnType<typeof useDocument>["data"]>) {
  if (document.access.can_read) return "Lire maintenant";
  if (document.access.reason === "authentication_required") return "Se connecter pour lire";
  if (document.access.reason === "entitlement_required") return "Acces requis";
  return "Indisponible";
}

export function DocumentDetailPage() {
  const { id } = useParams({ from: "/documents/$id" });
  const document = useDocument(id);
  if (document.isPending) return <SiteLayout><main className="container-editorial py-10"><Skeleton label="Chargement du document" /></main></SiteLayout>;
  if (document.isError || !document.data) return <SiteLayout><main className="container-editorial py-10"><EmptyState title="Document indisponible" description="Ce document est introuvable ou temporairement indisponible." /></main></SiteLayout>;
  const item = document.data;
  const cta = detailCta(item);
  const authors = item.authors.map((author) => author.display_name).join(", ");
  return <SiteLayout><main><div className="h-1 gabon-stripe" aria-hidden="true" /><section className="container-editorial grid gap-8 py-10 md:grid-cols-[minmax(0,0.85fr)_minmax(0,1.4fr)] md:py-16"><DocumentCover document={item} className="rounded-xl shadow-editorial-lg" /><div><a href="/catalogue" className="text-sm font-semibold text-[var(--green)] hover:underline">Catalogue</a>{item.domain ? <div className="mt-5"><DomainBadge domain={item.domain} /></div> : null}<h1 className="mt-4 font-display text-4xl font-semibold leading-tight text-[var(--navy)]">{item.title}</h1><p className="mt-5 text-muted-foreground">{item.abstract}</p><dl className="mt-7 grid gap-3 border-y border-border py-5 text-sm sm:grid-cols-2"><div><dt className="font-semibold text-[var(--navy)]">Auteur</dt><dd className="text-muted-foreground">{authors || "Non renseigne"}</dd></div><div><dt className="font-semibold text-[var(--navy)]">Publication</dt><dd className="text-muted-foreground">{item.publication_year ?? "Non renseignee"}</dd></div><div><dt className="font-semibold text-[var(--navy)]">Langue</dt><dd className="text-muted-foreground">{item.language_code.toUpperCase()}</dd></div><div><dt className="font-semibold text-[var(--navy)]">Pages</dt><dd className="text-muted-foreground">{item.page_count ?? "Non renseignees"}</dd></div></dl>{item.access.can_read ? <a href={`/lecture/${item.id}`} className="mt-7 inline-flex rounded-lg bg-[var(--navy)] px-5 py-3 text-sm font-semibold text-white hover:bg-[var(--navy-deep)]">{cta}</a> : <span className="mt-7 inline-flex rounded-lg border border-border bg-[var(--navy-soft)] px-5 py-3 text-sm font-semibold text-[var(--navy)]">{cta}</span>}</div></section></main></SiteLayout>;
}
