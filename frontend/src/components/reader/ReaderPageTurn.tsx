import { useRef } from "react";

/**
 * Tourner une page, dans le document lui-même.
 *
 * Les flèches sont aux extrêmes gauche et droite, à mi-hauteur : là où la main
 * va les chercher, et non dans la barre du haut, qui est loin du regard
 * pendant la lecture.
 *
 * Les coins s'y ajoutent : on saisit le haut ou le bas d'une page et on la
 * tire, comme on tourne une feuille. Le geste doit être **tiré**, pas cliqué —
 * un clic sur un coin tournerait la page pendant qu'on veut seulement
 * déplacer la vue, et le lecteur perdrait sa place sans comprendre pourquoi.
 */
const CORNER_TRAVEL = 44;

export function ReaderPageTurn({
  canGoBack,
  canGoForward,
  onPrevious,
  onNext
}: {
  canGoBack: boolean;
  canGoForward: boolean;
  onPrevious(): void;
  onNext(): void;
}) {
  return (
    <>
      <EdgeArrow
        side="start"
        label="Page précédente"
        disabled={!canGoBack}
        onClick={onPrevious}
      >
        ‹
      </EdgeArrow>
      <EdgeArrow side="end" label="Page suivante" disabled={!canGoForward} onClick={onNext}>
        ›
      </EdgeArrow>

      <PageCorner
        corner="top-start"
        label="Page précédente"
        disabled={!canGoBack}
        onTurn={onPrevious}
      />
      <PageCorner
        corner="bottom-start"
        label="Page précédente"
        disabled={!canGoBack}
        onTurn={onPrevious}
      />
      <PageCorner
        corner="top-end"
        label="Page suivante"
        disabled={!canGoForward}
        onTurn={onNext}
      />
      <PageCorner
        corner="bottom-end"
        label="Page suivante"
        disabled={!canGoForward}
        onTurn={onNext}
      />
    </>
  );
}

function EdgeArrow({
  side,
  label,
  disabled,
  onClick,
  children
}: {
  side: "start" | "end";
  label: string;
  disabled: boolean;
  onClick(): void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-label={label}
      className={`absolute top-1/2 z-10 -translate-y-1/2 rounded-full border border-[var(--border)] bg-white/90 px-3.5 py-3 text-2xl leading-none text-[var(--navy)] shadow-editorial backdrop-blur-sm transition hover:bg-white disabled:pointer-events-none disabled:opacity-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--gold)] ${
        side === "start" ? "start-3 sm:start-5" : "end-3 sm:end-5"
      }`}
    >
      <span aria-hidden>{children}</span>
    </button>
  );
}

/**
 * Coin de page que l'on saisit pour tourner.
 *
 * Le coin capture le pointeur : sans cela le déplacement partirait au
 * conteneur en dessous, qui le prendrait pour un défilement.
 */
function PageCorner({
  corner,
  label,
  disabled,
  onTurn
}: {
  corner: "top-start" | "bottom-start" | "top-end" | "bottom-end";
  label: string;
  disabled: boolean;
  onTurn(): void;
}) {
  const origin = useRef<number | null>(null);
  const towardsStart = corner.endsWith("start");

  if (disabled) return null;

  const place = [
    corner.startsWith("top") ? "top-0" : "bottom-0",
    towardsStart ? "start-0" : "end-0"
  ].join(" ");

  return (
    <div
      role="button"
      tabIndex={0}
      aria-label={label}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onTurn();
        }
      }}
      onPointerDown={(event) => {
        origin.current = event.clientX;
        event.currentTarget.setPointerCapture(event.pointerId);
      }}
      onPointerMove={(event) => {
        if (origin.current === null) return;
        const travelled = event.clientX - origin.current;
        // On tire vers le centre : un coin de gauche se tire vers la droite
        // pour revenir en arrière, comme on soulève une page.
        const enough = towardsStart ? travelled > CORNER_TRAVEL : travelled < -CORNER_TRAVEL;
        if (enough) {
          origin.current = null;
          onTurn();
        }
      }}
      onPointerUp={() => {
        origin.current = null;
      }}
      onPointerCancel={() => {
        origin.current = null;
      }}
      className={`absolute z-10 h-24 w-16 cursor-grab touch-none active:cursor-grabbing sm:h-32 sm:w-24 ${place} ${
        corner.startsWith("top")
          ? towardsStart
            ? "bg-gradient-to-br"
            : "bg-gradient-to-bl"
          : towardsStart
            ? "bg-gradient-to-tr"
            : "bg-gradient-to-tl"
      } from-[var(--navy)]/14 to-transparent opacity-0 transition-opacity hover:opacity-100 focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--gold)]`}
    />
  );
}
