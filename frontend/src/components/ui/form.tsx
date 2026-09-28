import { fieldErrorId } from "@/components/ui/fieldErrors";

/**
 * Champs de formulaire du produit.
 *
 * Les écrans de gestion utilisaient 161 classes `slate-*` génériques et pas un
 * seul jeton du produit : ni navy, ni or, ni vert, ni serif éditoriale, ni
 * ombre. L'audit de maquette dit pourtant que le frontend « should not drift
 * into a generic SaaS, generic library, or plain admin interface » — c'est
 * exactement ce qui était arrivé.
 *
 * Ces primitives portent l'identité une fois pour toutes : bordure douce,
 * fond, anneau de focus doré, état d'erreur lisible, et un espacement qui
 * respire. Un écran qui les utilise ne peut plus dériver seul.
 */

const CONTROL_BASE =
  "w-full rounded-[var(--radius)] border bg-white px-3.5 py-2.5 text-[15px] text-[var(--ink)] " +
  "transition placeholder:text-[var(--muted-foreground)] " +
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--gold)] " +
  "focus-visible:border-[var(--gold)] disabled:cursor-not-allowed disabled:bg-[var(--muted)] " +
  "disabled:text-[var(--muted-foreground)]";

function controlClass(invalid: boolean, extra?: string) {
  const border = invalid
    ? "border-red-400 bg-red-50/40"
    : "border-[var(--border)] hover:border-[var(--navy-soft)]";
  return [CONTROL_BASE, border, extra].filter(Boolean).join(" ");
}

export function Field({
  id,
  label,
  hint,
  required,
  errors,
  form,
  name,
  children
}: {
  id: string;
  label: string;
  hint?: string;
  required?: boolean;
  errors?: Record<string, string[]>;
  form: string;
  name: string;
  children: React.ReactNode;
}) {
  const messages = errors?.[name] ?? [];
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-sm font-semibold text-[var(--navy)]">
        {label}
        {required ? (
          <span aria-hidden className="ms-1 text-[var(--green)]">
            *
          </span>
        ) : null}
      </label>
      {children}
      {messages.length > 0 ? (
        <span id={fieldErrorId(form, name)} className="text-sm font-medium text-red-700">
          {messages.join(" ")}
        </span>
      ) : hint ? (
        <span className="text-sm text-[var(--muted-foreground)]">{hint}</span>
      ) : null}
    </div>
  );
}

export function TextInput({
  invalid,
  className,
  ...props
}: React.InputHTMLAttributes<HTMLInputElement> & { invalid?: boolean }) {
  return <input {...props} className={controlClass(Boolean(invalid), className)} />;
}

export function TextArea({
  invalid,
  className,
  ...props
}: React.TextareaHTMLAttributes<HTMLTextAreaElement> & { invalid?: boolean }) {
  return <textarea {...props} className={controlClass(Boolean(invalid), className)} />;
}

export function Select({
  invalid,
  className,
  children,
  ...props
}: React.SelectHTMLAttributes<HTMLSelectElement> & { invalid?: boolean }) {
  return (
    <select {...props} className={controlClass(Boolean(invalid), className)}>
      {children}
    </select>
  );
}

const BUTTON_BASE =
  "inline-flex items-center justify-center gap-2 rounded-[var(--radius)] px-4 py-2.5 " +
  "text-sm font-semibold transition focus-visible:outline-none focus-visible:ring-2 " +
  "focus-visible:ring-[var(--gold)] focus-visible:ring-offset-2 disabled:cursor-not-allowed " +
  "disabled:opacity-45";

const BUTTON_TONES = {
  primary: "bg-[var(--navy)] text-white shadow-editorial hover:bg-[var(--navy-deep)]",
  approve: "bg-[var(--green)] text-white shadow-editorial hover:brightness-95",
  danger: "bg-red-700 text-white shadow-editorial hover:bg-red-800",
  quiet:
    "border border-[var(--border)] bg-white text-[var(--navy)] hover:bg-[var(--navy-soft)]",
  ghost: "text-[var(--navy)] hover:bg-[var(--navy-soft)]"
} as const;

export function ActionButton({
  tone = "primary",
  className,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { tone?: keyof typeof BUTTON_TONES }) {
  return (
    <button
      type="button"
      {...props}
      className={[BUTTON_BASE, BUTTON_TONES[tone], className].filter(Boolean).join(" ")}
    />
  );
}

/**
 * Bloc de contenu du back-office.
 *
 * Reprend la respiration éditoriale des écrans publics — titre en serif,
 * ombre douce, coins arrondis — au lieu d'un cadre gris. La densité reste
 * supérieure à celle du catalogue : on saisit des données, on ne flâne pas.
 */
export function Panel({
  title,
  description,
  aside,
  children
}: {
  title?: string;
  description?: string;
  aside?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-[calc(var(--radius)+0.25rem)] border border-[var(--border)] bg-[var(--card)] p-5 shadow-editorial sm:p-6">
      {title ? (
        <header className="mb-4 flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 className="font-display text-lg text-[var(--navy)]">{title}</h3>
            {description ? (
              <p className="mt-1 text-sm text-[var(--muted-foreground)]">{description}</p>
            ) : null}
          </div>
          {aside}
        </header>
      ) : null}
      {children}
    </section>
  );
}

/** Message d'erreur au niveau du formulaire. */
export function FormAlert({ children }: { children: React.ReactNode }) {
  return (
    <p
      role="alert"
      className="rounded-[var(--radius)] border border-red-200 bg-red-50 px-4 py-3 text-sm font-medium text-red-800"
    >
      {children}
    </p>
  );
}

/** Confirmation discrète, sans interrompre la saisie. */
export function FormNotice({ children }: { children: React.ReactNode }) {
  return (
    <p
      role="status"
      className="rounded-[var(--radius)] border border-[var(--green-soft)] bg-[var(--green-soft)] px-4 py-3 text-sm font-medium text-[var(--green)]"
    >
      {children}
    </p>
  );
}
