import {
  MODE_LABELS,
  SCROLL_MODES,
  ZOOM_STEPS,
  type ScrollMode
} from "@/components/reader/readerPreferences";

/**
 * Barre du lecteur : sortie, position, sens de défilement, zoom.
 *
 * Elle reste visible en permanence plutôt que d'apparaître au survol : sur un
 * écran tactile, il n'y a pas de survol, et une barre qui se cache oblige à
 * tâtonner pour retrouver la sortie.
 */
export function ReaderToolbar({
  title,
  pageNumber,
  pageCount,
  mode,
  zoom,
  onModeChange,
  onZoomChange,
  onPrevious,
  onNext,
  onClose
}: {
  title: string;
  pageNumber: number;
  pageCount: number;
  mode: ScrollMode;
  zoom: number;
  onModeChange(mode: ScrollMode): void;
  onZoomChange(zoom: number): void;
  onPrevious(): void;
  onNext(): void;
  onClose(): void;
}) {
  const atFirst = pageNumber <= 1;
  const atLast = pageNumber >= pageCount;

  return (
    <header className="flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-white/10 bg-[var(--navy-deep)] px-3 py-2 text-white sm:px-5">
      <button
        type="button"
        onClick={onClose}
        className="rounded-lg px-2.5 py-1.5 text-sm font-semibold text-white/85 transition hover:bg-white/10 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--gold)]"
      >
        ← Quitter
      </button>

      <h1 className="min-w-0 flex-1 truncate font-display text-base text-white/95 sm:text-lg">
        {title}
      </h1>

      <nav aria-label="Navigation" className="flex items-center gap-1">
        <IconButton label="Page précédente" onClick={onPrevious} disabled={atFirst}>
          ‹
        </IconButton>
        {/* Une seule expression, donc un seul nœud de texte : rendu en
            fragments, `aria-live` annonce « 2 », « / », « 5 » séparément. */}
        <p
          aria-live="polite"
          className="min-w-[5.5rem] text-center text-sm tabular-nums text-white/80"
        >
          {`${pageNumber} / ${pageCount}`}
        </p>
        <IconButton label="Page suivante" onClick={onNext} disabled={atLast}>
          ›
        </IconButton>
      </nav>

      <div className="flex items-center gap-1" role="group" aria-label="Zoom">
        <IconButton
          label="Réduire"
          onClick={() => onZoomChange(-1)}
          disabled={zoom <= ZOOM_STEPS[0]}
        >
          −
        </IconButton>
        <span className="min-w-[3.25rem] text-center text-sm tabular-nums text-white/80">
          {`${Math.round(zoom * 100)} %`}
        </span>
        <IconButton
          label="Agrandir"
          onClick={() => onZoomChange(1)}
          disabled={zoom >= ZOOM_STEPS[ZOOM_STEPS.length - 1]}
        >
          +
        </IconButton>
      </div>

      <div
        className="flex items-center gap-0.5 rounded-lg bg-white/10 p-0.5"
        role="group"
        aria-label="Sens de défilement"
      >
        {SCROLL_MODES.map((candidate) => (
          <button
            key={candidate}
            type="button"
            onClick={() => onModeChange(candidate)}
            aria-pressed={mode === candidate}
            title={MODE_LABELS[candidate]}
            className={`rounded-md px-2.5 py-1 text-xs font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--gold)] ${
              mode === candidate
                ? "bg-[var(--gold)] text-[var(--navy-deep)]"
                : "text-white/75 hover:bg-white/10 hover:text-white"
            }`}
          >
            <span aria-hidden>{MODE_GLYPHS[candidate]}</span>
            <span className="sr-only">{MODE_LABELS[candidate]}</span>
          </button>
        ))}
      </div>
    </header>
  );
}

const MODE_GLYPHS: Record<ScrollMode, string> = {
  vertical: "↕",
  horizontal: "↔",
  livre: "▭▭"
};

function IconButton({
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
      className="rounded-md px-2.5 py-1 text-lg leading-none text-white/85 transition hover:bg-white/10 hover:text-white disabled:cursor-not-allowed disabled:opacity-35 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--gold)]"
    >
      {children}
    </button>
  );
}
