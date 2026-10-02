import { Logo } from "@/components/brand/Logo";

/**
 * Barre du lecteur : sortir, se situer, se reconnaître.
 *
 * Trois zones et rien de plus. Les réglages d'affichage vivent derrière le
 * bouton de droite, dans une modale : une barre qui les expose tous en
 * permanence les met au même rang que la lecture, et n'en laisse plus la
 * place sur un téléphone.
 *
 * Elle reste visible en permanence plutôt que d'apparaître au survol : sur un
 * écran tactile il n'y a pas de survol, et une barre qui se cache oblige à
 * tâtonner pour retrouver la sortie.
 */
export function ReaderToolbar({
  pageNumber,
  pageCount,
  pagesOpen,
  onClose,
  onTogglePages,
  onOpenOptions
}: {
  pageNumber: number;
  pageCount: number;
  pagesOpen: boolean;
  onClose(): void;
  onTogglePages(): void;
  onOpenOptions(): void;
}) {
  return (
    <header className="relative flex items-center gap-3 border-b border-white/10 bg-[var(--navy-deep)] px-3 py-2 text-white sm:px-5">
      <div className="flex min-w-0 flex-1 items-center gap-3">
        <button
          type="button"
          onClick={onClose}
          className="shrink-0 rounded-lg px-2.5 py-1.5 text-sm font-semibold text-white/85 transition hover:bg-white/10 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--gold)]"
        >
          ← Retour
        </button>
        {/* Le volet des pages s'ouvre depuis la position : c'est là qu'on
            regarde quand on cherche où l'on en est.

            Pas de troncature : sur un téléphone, « Page 1 sur 157 » devenait
            « Page 1 sur… » — on coupait précisément ce qui situe le lecteur
            dans son document, et d'autant plus que le document est long. */}
        <button
          type="button"
          onClick={onTogglePages}
          aria-pressed={pagesOpen}
          // `aria-live` sur le bouton lui-même : la position change sans
          // qu'aucun bouton n'ait été actionné quand on fait défiler, et elle
          // doit s'annoncer. La répéter dans un second élément la ferait
          // entendre deux fois.
          aria-live="polite"
          className="whitespace-nowrap rounded-lg px-2 py-1 text-sm tabular-nums text-white/75 transition hover:bg-white/10 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--gold)]"
        >
          <span aria-hidden className="me-2">
            ☰
          </span>
          {`Page ${pageNumber} sur ${pageCount}`}
        </button>
      </div>

      {/* Centré sur la barre et non sur l'espace restant : positionné dans le
          flux, la marque se décalerait selon la longueur du compteur.
          
          Masquée sous `sm` : à 390 px, le centre de la barre tombe sur la fin
          de « Page 1 sur 3 » et le nom passe par-dessus. Entre une marque et
          une position, c'est la marque qui cède — elle est décorative, la
          position ne l'est pas. Aucun test de rendu ne voit ce défaut : jsdom
          ne met rien en page. */}
      <div className="pointer-events-none absolute inset-x-0 hidden justify-center sm:flex">
        <div className="pointer-events-auto text-white">
          <Logo linkToHome={false} compact className="text-white [&_span]:text-white" />
        </div>
      </div>

      {/* `shrink-0` et non `flex-1` : la marque est centrée hors du flux, donc
          rien n'oblige les deux côtés à se partager la barre — et ce partage
          prenait au compteur la place dont il avait besoin. */}
      <div className="flex shrink-0 justify-end">
        <button
          type="button"
          onClick={onOpenOptions}
          className="flex items-center gap-2 rounded-lg px-2.5 py-1.5 text-sm font-semibold text-white/85 transition hover:bg-white/10 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--gold)]"
        >
          <span aria-hidden>⚙</span>
          <span className="hidden sm:inline">Affichage</span>
          <span className="sr-only sm:hidden">Options d'affichage</span>
        </button>
      </div>
    </header>
  );
}
