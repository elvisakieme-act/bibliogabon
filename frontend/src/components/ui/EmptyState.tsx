export function EmptyState({ title, description }: { title: string; description: string }) {
  return (
    <section className="rounded-2xl border border-border bg-white p-8 text-center shadow-editorial">
      <div className="mx-auto mb-4 h-1 w-20 gabon-rule" aria-hidden="true" />
      <h2 className="font-display text-2xl text-[var(--navy)]">{title}</h2>
      <p className="mt-2 text-sm text-muted-foreground">{description}</p>
    </section>
  );
}
