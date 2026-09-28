import {
  PUBLICATION_STATUS_LABELS,
  PUBLICATION_STATUS_TONES,
  publicationStatusLabel
} from "@/components/staff/publicationStatus";

export function DocumentStateBadge({ status }: { status: string }) {
  const unknown = !(status in PUBLICATION_STATUS_LABELS);
  return (
    <span
      className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${
        PUBLICATION_STATUS_TONES[status] ?? "bg-slate-100 text-slate-700 ring-1 ring-slate-300"
      }`}
      title={unknown ? "État inconnu de cette interface" : undefined}
    >
      {publicationStatusLabel(status)}
    </span>
  );
}
