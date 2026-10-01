import { useState } from "react";
import { Link, useNavigate } from "@tanstack/react-router";

import { registerIndividual } from "@/api/auth";
import { useAuth } from "@/auth/useAuth";
import { ApiError } from "@/api/client";
import { FieldErrors } from "@/components/ui/FieldErrors";
import { fieldErrorProps } from "@/components/ui/fieldErrors";
import { Logo } from "@/components/brand/Logo";

/**
 * Ce qu'un compte apporte réellement, et rien de plus.
 *
 * Chaque phrase correspond à quelque chose qui existe : la progression de
 * lecture est enregistrée, la bibliothèque personnelle garde les favoris, et
 * les documents réservés s'ouvrent par un rattachement vérifié — jamais
 * déclaré par le lecteur lui-même, c'est l'établissement qui l'accorde.
 * Promettre davantage à l'inscription se paie à la première déception.
 */
const AVANTAGES = [
  "Reprendre une lecture là où vous l'avez laissée, d'un appareil à l'autre.",
  "Garder dans votre bibliothèque les documents qui comptent pour vos travaux.",
  "Ouvrir les documents réservés à votre établissement, une fois votre rattachement vérifié."
];

export function InscriptionPage() {
  const auth = useAuth();
  const navigate = useNavigate();
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string[]>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setFieldErrors({});
    setIsSubmitting(true);
    try {
      const session = await registerIndividual({ email, password, display_name: displayName });
      auth.setSession(session);
      await navigate({ to: "/profil" });
    } catch (caught: unknown) {
      // Les erreurs par champ etaient jetees : l'utilisateur ne voyait
      // qu'un message generique la ou le serveur disait precisement quoi.
      if (caught instanceof ApiError) {
        setFieldErrors(caught.fieldErrors ?? {});
      }
      setError("Inscription impossible. Vérifiez les informations saisies.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="grid min-h-screen lg:grid-cols-2">
      {/* Ce que donne un compte, et rien d'autre. La page ne le disait pas : on
          demandait trois champs à un étudiant sans lui dire ce qu'il y gagne,
          et la lecture libre, elle, n'en demande aucun. Les trois phrases sont
          tenues par du code — progression, favoris, droits d'établissement. */}
      <section className="hidden bg-[var(--navy)] p-12 text-white lg:flex lg:flex-col lg:justify-between">
        <Logo onDark />
        <div>
          <h2 className="max-w-md font-display text-4xl font-semibold leading-tight">
            Un compte garde vos lectures.
          </h2>
          <ul className="mt-8 max-w-md space-y-5 text-white/80">
            {AVANTAGES.map((avantage) => (
              <li key={avantage} className="flex gap-4">
                <span aria-hidden="true" className="mt-2 h-px w-6 shrink-0 bg-[var(--gold)]" />
                <span className="leading-relaxed">{avantage}</span>
              </li>
            ))}
          </ul>
        </div>
        <p className="text-sm text-white/60">
          La lecture des documents en accès libre ne demande aucun compte.
        </p>
      </section>
      <section className="flex items-center justify-center bg-background px-5 py-12">
        <div className="w-full max-w-md">
          <div className="mb-10 lg:hidden">
            <Logo />
          </div>
          <h1 className="font-display text-4xl font-semibold text-[var(--navy)]">
            Rejoindre BiblioGABON
          </h1>
          {/* Les mêmes raisons, sous le titre, quand le panneau n'a pas la
              place de s'afficher. Le masquer sous `lg` rendait l'inscription à
              trois champs sans motif — sur les écrans où se trouvent la plupart
              des lecteurs. */}
          <ul className="mt-5 space-y-2 text-sm text-muted-foreground lg:hidden">
            {AVANTAGES.map((avantage) => (
              <li key={avantage} className="flex gap-3">
                <span
                  aria-hidden="true"
                  className="mt-2.5 h-px w-4 shrink-0 bg-[var(--gold)]"
                />
                <span>{avantage}</span>
              </li>
            ))}
          </ul>
          <form className="mt-7 space-y-5" onSubmit={onSubmit}>
            {error ? (
              <p
                role="alert"
                className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800"
              >
                {error}
              </p>
            ) : null}
            <label className="block text-sm font-semibold text-[var(--navy)]">
              Nom affiché
              <input
                required
                value={displayName}
                onChange={(event) => setDisplayName(event.target.value)}
                className="mt-2 w-full rounded-lg border border-border px-3 py-2.5 font-normal outline-none focus:border-[var(--green)] focus:ring-2 focus:ring-[var(--green)]/20"
                {...fieldErrorProps("inscription", "display_name", fieldErrors)}
              />
              <FieldErrors form="inscription" field="display_name" fieldErrors={fieldErrors} />
            </label>
            <label className="block text-sm font-semibold text-[var(--navy)]">
              Email
              <input
                required
                type="email"
                autoComplete="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                className="mt-2 w-full rounded-lg border border-border px-3 py-2.5 font-normal outline-none focus:border-[var(--green)] focus:ring-2 focus:ring-[var(--green)]/20"
                {...fieldErrorProps("inscription", "email", fieldErrors)}
              />
              <FieldErrors form="inscription" field="email" fieldErrors={fieldErrors} />
            </label>
            <label className="block text-sm font-semibold text-[var(--navy)]">
              Mot de passe
              <input
                required
                type="password"
                autoComplete="new-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                className="mt-2 w-full rounded-lg border border-border px-3 py-2.5 font-normal outline-none focus:border-[var(--green)] focus:ring-2 focus:ring-[var(--green)]/20"
                {...fieldErrorProps("inscription", "password", fieldErrors)}
              />
              <FieldErrors form="inscription" field="password" fieldErrors={fieldErrors} />
            </label>
            <button
              disabled={isSubmitting}
              className="w-full rounded-lg bg-[var(--navy)] px-4 py-3 text-sm font-semibold text-white transition hover:bg-[var(--navy-deep)] disabled:opacity-60"
            >
              {isSubmitting ? "Création…" : "Créer mon compte"}
            </button>
          </form>
          <p className="mt-6 text-sm text-muted-foreground">
            Déjà inscrit ?{" "}
            <Link to="/connexion" className="font-semibold text-[var(--green)] hover:underline">
              Se connecter
            </Link>
          </p>
        </div>
      </section>
    </main>
  );
}
