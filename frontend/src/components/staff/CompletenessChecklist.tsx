import { completenessLabel, isKnownCompletenessCode } from "@/components/staff/completeness";

export function CompletenessChecklist({
  codes,
  title = "À fournir avant de soumettre"
}: {
  codes: string[];
  title?: string;
}) {
  if (codes.length === 0) return null;
  return (
    <section className="rounded border border-amber-300 bg-amber-50 p-4">
      <h3 id="completude-titre" className="text-sm font-semibold text-amber-900">
        {title}
      </h3>
      <ul aria-labelledby="completude-titre" className="mt-2 space-y-1 text-sm text-amber-900">
        {codes.map((code) => (
          <li key={code} className="flex gap-2">
            <span aria-hidden>•</span>
            <span className={isKnownCompletenessCode(code) ? undefined : "font-mono"}>
              {completenessLabel(code)}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
