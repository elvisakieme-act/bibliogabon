interface ReaderControlsProps {
  pageNumber: number;
  pageCount: number;
  onPrevious(): void;
  onNext(): void;
}

export function ReaderControls({ pageNumber, pageCount, onPrevious, onNext }: ReaderControlsProps) {
  return (
    <nav aria-label="Navigation du lecteur" className="flex items-center justify-between border-t border-border pt-5">
      <button
        type="button"
        onClick={onPrevious}
        disabled={pageNumber === 1}
        className="rounded-lg border border-border bg-white px-4 py-2 text-sm font-semibold text-[var(--navy)] disabled:cursor-not-allowed disabled:opacity-45"
      >
        Page precedente
      </button>
      <p className="text-sm text-muted-foreground">Page {pageNumber} sur {pageCount}</p>
      <button
        type="button"
        onClick={onNext}
        disabled={pageNumber === pageCount}
        className="rounded-lg bg-[var(--navy)] px-4 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-45"
      >
        Page suivante
      </button>
    </nav>
  );
}
