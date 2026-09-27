import { SiteLayout } from "@/components/layout/SiteLayout";
import { EmptyState } from "@/components/ui/EmptyState";

export function NotFoundPage() {
  return (
    <SiteLayout>
      <EmptyState
        title="Page introuvable"
        description="Cette adresse ne correspond a aucune page publique de BiblioGABON."
      />
    </SiteLayout>
  );
}
