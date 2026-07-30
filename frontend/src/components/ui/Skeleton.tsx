export function Skeleton({ label = "Chargement" }: { label?: string }) {
  return <div aria-label={label} className="animate-pulse rounded-xl bg-[var(--navy-soft)]" role="status" />;
}
