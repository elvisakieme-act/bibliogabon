import { Modal } from "@/components/ui/Modal";
import {
  MODE_LABELS,
  SCROLL_MODES,
  ZOOM_STEPS,
  type ScrollMode
} from "@/components/reader/readerPreferences";

/**
 * Options d'affichage du lecteur.
 *
 * Elles vivent dans une modale, pas dans la barre : celle-ci porte la sortie,
 * la position et la marque, et rien d'autre. Une barre qui expose tous les
 * réglages en permanence les met au même rang que la lecture elle-même, et
 * n'en laisse plus la place sur un téléphone.
 */
const MODE_HINTS: Record<ScrollMode, string> = {
  vertical: "Les pages s'enchaînent, on fait défiler.",
  horizontal: "Une page à la fois, on passe à la suivante.",
  livre: "Deux pages côte à côte, comme un ouvrage ouvert."
};

const MODE_GLYPHS: Record<ScrollMode, string> = {
  vertical: "↕",
  horizontal: "↔",
  livre: "▭▭"
};

export function ReaderDisplayOptions({
  open,
  mode,
  zoom,
  onClose,
  onModeChange,
  onZoomChange
}: {
  open: boolean;
  mode: ScrollMode;
  zoom: number;
  onClose(): void;
  onModeChange(mode: ScrollMode): void;
  onZoomChange(direction: 1 | -1): void;
}) {
  return (
    <Modal open={open} title="Affichage" onClose={onClose}>
      <fieldset className="border-0 p-0">
        <legend className="mb-2 text-sm font-semibold text-[var(--navy)]">
          Sens de lecture
        </legend>
        <div className="flex flex-col gap-2">
          {SCROLL_MODES.map((candidate) => (
            <button
              key={candidate}
              type="button"
              onClick={() => onModeChange(candidate)}
              aria-pressed={mode === candidate}
              className={`flex items-start gap-3 rounded-[var(--radius)] border px-3.5 py-3 text-start transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--gold)] ${
                mode === candidate
                  ? "border-[var(--gold)] bg-[var(--gold-soft)]"
                  : "border-[var(--border)] hover:border-[var(--navy-soft)] hover:bg-[var(--navy-soft)]"
              }`}
            >
              <span aria-hidden className="mt-0.5 text-lg leading-none text-[var(--navy)]">
                {MODE_GLYPHS[candidate]}
              </span>
              <span className="min-w-0">
                <span className="block text-sm font-semibold text-[var(--navy)]">
                  {MODE_LABELS[candidate]}
                </span>
                <span className="block text-sm text-[var(--muted-foreground)]">
                  {MODE_HINTS[candidate]}
                </span>
              </span>
            </button>
          ))}
        </div>
      </fieldset>

      <div className="mt-5 border-t border-[var(--border)] pt-4">
        <p className="mb-2 text-sm font-semibold text-[var(--navy)]">Zoom</p>
        <div className="flex items-center gap-2" role="group" aria-label="Zoom">
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
