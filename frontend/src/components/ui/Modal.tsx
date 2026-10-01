import { useEffect, useRef } from "react";

/**
 * Modale bâtie sur l'élément natif `<dialog>`.
 *
 * `showModal()` apporte le piège de focus, la fermeture par Échap, l'inertie
 * du reste de la page et l'arrière-plan — quatre comportements qu'une modale
 * en `<div>` doit réimplémenter, et que les implémentations maison ratent
 * presque toujours sur le premier : au clavier, on sort de la modale sans s'en
 * apercevoir et on agit sur ce qu'elle recouvre.
 */
export function Modal({
  open,
  title,
  onClose,
  children
}: {
  open: boolean;
  title: string;
  onClose(): void;
  children: React.ReactNode;
}) {
  const dialog = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const element = dialog.current;
    if (!element) return;
    if (open && !element.open) {
      element.showModal();
    } else if (!open && element.open) {
      element.close();
    }
  }, [open]);

  return (
    <dialog
      ref={dialog}
      aria-label={title}
      // `close` couvre Échap et le bouton : sans lui, fermer au clavier
      // laisserait l'état de l'appelant croire la modale encore ouverte, et
      // le bouton d'ouverture ne la rouvrirait plus.
      onClose={onClose}
      onClick={(event) => {
        // Un clic sur l'arrière-plan atteint le `<dialog>` lui-même ; un clic
        // dans le contenu atteint un enfant.
        if (event.target === dialog.current) onClose();
      }}
      className="m-auto w-[min(26rem,calc(100vw-2rem))] rounded-[calc(var(--radius)+0.25rem)] border border-[var(--border)] bg-[var(--card)] p-0 text-[var(--ink)] shadow-editorial backdrop:bg-[var(--navy-deep)]/60 backdrop:backdrop-blur-sm"
    >
      <div className="h-1 gabon-stripe" aria-hidden="true" />
      <div className="flex items-start justify-between gap-4 px-5 pt-4">
        <h2 className="font-display text-lg text-[var(--navy)]">{title}</h2>
        <button
          type="button"
          onClick={onClose}
          aria-label="Fermer"
          className="-me-1 rounded-lg px-2 py-1 text-xl leading-none text-[var(--muted-foreground)] transition hover:bg-[var(--navy-soft)] hover:text-[var(--navy)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--gold)]"
        >
          ×
        </button>
      </div>
      <div className="px-5 pb-5 pt-4">{children}</div>
    </dialog>
  );
}
