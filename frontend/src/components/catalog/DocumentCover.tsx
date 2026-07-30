import type { DocumentMetadata } from "@/api/types";

const FALLBACKS = [
  "from-[var(--navy)] via-[var(--green)] to-[var(--gold)]",
  "from-[var(--green)] via-[var(--navy)] to-[var(--gold)]",
  "from-[var(--gold)] via-[var(--green)] to-[var(--navy)]"
];

export function DocumentCover({ document, className = "" }: { document: DocumentMetadata; className?: string }) {
  if (document.cover) {
    return <img src={document.cover} alt="" className={`aspect-[4/3] w-full object-cover ${className}`} />;
  }

  const fallback = FALLBACKS[(document.domain?.slug.length ?? document.document_type.length) % FALLBACKS.length];
  return (
    <div className={`relative flex aspect-[4/3] w-full overflow-hidden bg-gradient-to-br ${fallback} p-5 text-white ${className}`} aria-hidden="true">
      <span className="absolute inset-3 border border-white/25" />
      <span className="absolute bottom-5 left-5 h-1 w-16 bg-white/70" />
    </div>
  );
}
