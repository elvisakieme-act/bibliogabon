import {
  MODE_HINTS,
  MODE_LABELS,
  READING_MODES,
  type ReadingMode,
  ZOOM_STEPS
} from "@/components/reader/readerPreferences";
import { Modal } from "@/components/ui/Modal";

/**
 * Options d'affichage du lecteur.
 *
 * Trois sens de lecture, chacun avec sa mécanique — reprises une par une.
 * Livrés d'un coup la première fois, ils partageaient le même mécanisme et
 * aucun des trois n'était servi : la molette zoomait au lieu de faire défiler,
 * et « horizontal » ne différait de « vertical » que par l'endroit où les pages
 * étaient posées. Mieux valait un mode qui fonctionne que trois qui se
 * ressemblent ; ils y sont revenus chacun avec le sien.
 */
export function ReaderDisplayOptions({
  open,
  mode,
  zoom,
  onClose,
  onModeChange,
  onZoomChange
}: {
  open: boolean;
  mode: ReadingMode;
  zoom: number;
  onClose(): void;
  onModeChange(mode: ReadingMode): void;
  onZoomChange(direction: 1 | -1): void;
}) {
  return (
    <Modal open={open} title="Affichage" onClose={onClose}>
      <fieldset className="border-0 p-0">
        <legend className="mb-2 text-sm font-semibold text-[var(--navy)]">
          Sens de lecture
        </legend>
        <div className="flex flex-col gap-2">
          {READING_MODES.map((candidate) => (
            <button
              key={candidate}
              type="button"
              onClick={() => onModeChange(candidate)}
              aria-pressed={mode === candidate}
              className={`flex flex-col gap-1 rounded-[var(--radius)] border px-3.5 py-3 text-start transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--gold)] ${
                mode === candidate
                  ? "border-[var(--gold)] bg-[var(--gold-soft)]"
                  : "border-[var(--border)] hover:border-[var(--navy-soft)] hover:bg-[var(--navy-soft)]"
              }`}
            >
              <span className="text-sm font-semibold text-[var(--navy)]">
                {MODE_LABELS[candidate]}
              </span>
              <span className="text-sm text-[var(--muted-foreground)]">
                {MODE_HINTS[candidate]}
              </span>
            </button>
          ))}
        </div>
      </fieldset>

      <p className="mt-5 border-t border-[var(--border)] pt-4 text-sm font-semibold text-[var(--navy)]">
        Taille de la page
      </p>
      <div className="mt-3 flex items-center gap-2" role="group" aria-label="Zoom">
        <ZoomButton
          label="Réduire"
          onClick={() => onZoomChange(-1)}
          disabled={zoom <= ZOOM_STEPS[0]}
        >
          −
        </ZoomButton>
        <span className="min-w-[4rem] text-center text-sm tabular-nums text-[var(--ink)]">
          {`${Math.round(zoom * 100)} %`}
        </span>
        <ZoomButton
          label="Agrandir"
          onClick={() => onZoomChange(1)}
          disabled={zoom >= ZOOM_STEPS[ZOOM_STEPS.length - 1]}
        >
          +
        </ZoomButton>
      </div>
    </Modal>
  );
}

function ZoomButton({
  label,
  onClick,
  disabled,
  children
}: {
  label: string;
  onClick(): void;
  disabled?: boolean;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-label={label}
      className="rounded-[var(--radius)] border border-[var(--border)] px-3.5 py-1.5 text-lg leading-none text-[var(--navy)] transition hover:bg-[var(--navy-soft)] disabled:cursor-not-allowed disabled:opacity-40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--gold)]"
    >
      {children}
    </button>
  );
}
