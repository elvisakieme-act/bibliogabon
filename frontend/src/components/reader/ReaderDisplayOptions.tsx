import { ZOOM_STEPS } from "@/components/reader/readerPreferences";
import { Modal } from "@/components/ui/Modal";

/**
 * Options d'affichage du lecteur.
 *
 * Il n'en reste qu'une. Trois sens de lecture avaient été proposés, mais les
 * trois reposaient sur le même mécanisme et aucun ne le servait : la molette
 * zoomait au lieu de faire défiler, et « horizontal » ne différait de
 * « vertical » que par l'endroit où les pages étaient posées. Mieux vaut un
 * mode qui fonctionne que trois qui se ressemblent.
 */
export function ReaderDisplayOptions({
  open,
  zoom,
  onClose,
  onZoomChange
}: {
  open: boolean;
  zoom: number;
  onClose(): void;
  onZoomChange(direction: 1 | -1): void;
}) {
  return (
    <Modal open={open} title="Affichage" onClose={onClose}>
      <p className="text-sm font-semibold text-[var(--navy)]">Taille de la page</p>
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
      <p className="mt-4 text-sm text-[var(--muted-foreground)]">
        Les pages s'enchaînent : faites défiler pour avancer dans le document.
      </p>
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
