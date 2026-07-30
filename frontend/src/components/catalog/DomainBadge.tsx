import type { DomainSummary, SearchDomainSummary } from "@/api/types";

const DOT_COLORS = ["bg-[var(--green)]", "bg-[var(--gold)]", "bg-[var(--navy)]"];

export function DomainBadge({ domain }: { domain: DomainSummary | SearchDomainSummary }) {
  const color = DOT_COLORS[domain.name.length % DOT_COLORS.length];

  return (
    <span className="inline-flex items-center gap-2 rounded-full bg-[var(--green-soft)] px-3 py-1 text-xs font-semibold text-[var(--navy)]">
      <span aria-hidden="true" className={`size-1.5 rounded-full ${color}`} />
      {domain.name}
    </span>
  );
}
