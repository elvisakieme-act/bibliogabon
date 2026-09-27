import { useEffect, useState } from "react";

import { getCurrentUser, updateCurrentUser } from "@/api/auth";
import { ApiError } from "@/api/client";
import { useAuth } from "@/auth/useAuth";
import { tokenStore } from "@/auth/tokenStore";
import { RequireAuth } from "@/auth/guards";
import { SiteLayout } from "@/components/layout/SiteLayout";

export function ProfilPage() {
  return (
    <RequireAuth>
      <ProfileContent />
    </RequireAuth>
  );
}

function ProfileContent() {
  const auth = useAuth();
  const [displayName, setDisplayName] = useState(auth.user?.display_name ?? "");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string[]>>({});
  const [message, setMessage] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Revalide la session en entrant sur la page : un jeton expire depuis
  // l'hydratation doit deconnecter ici, et non au prochain enregistrement.
  // Le tableau de dependances etait vide alors que l'effet lisait `auth` ;
  // `setSession` et `clearSession` sont stables, donc exprimables ici.
  const accessToken = auth.tokens?.access;
  const { setSession, clearSession } = auth;
  useEffect(() => {
    if (!accessToken) return;
    getCurrentUser(accessToken)
      .then((user) => {
        setDisplayName(user.display_name);
        const stored = tokenStore.get();
        if (stored) {
          setSession({ user, tokens: stored });
        }
      })
      .catch((error: unknown) => {
        if (error instanceof ApiError && error.status === 401) {
          clearSession();
        }
      });
  }, [accessToken, setSession, clearSession]);

  function handleError(error: unknown, fallbackMessage: string) {
    if (error instanceof ApiError) {
      setFieldErrors(error.fieldErrors);
      setMessage(error.message || fallbackMessage);
      if (error.status === 401) {
        auth.clearSession();
      }
      return;
    }
    setFieldErrors({});
    setMessage(fallbackMessage);
  }

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!auth.tokens || !auth.user) return;
    setMessage("");
    setFieldErrors({});
    setIsSubmitting(true);
    try {
      const user = await updateCurrentUser(auth.tokens.access, { display_name: displayName });
      auth.setSession({ user, tokens: auth.tokens });
      setMessage("Profil mis a jour.");
    } catch (error: unknown) {
      handleError(error, "La mise a jour a echoue. Reessayez.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <SiteLayout>
      <main className="container-editorial py-10 sm:py-16">
        <div className="max-w-2xl">
          <p className="text-sm font-semibold uppercase tracking-[0.18em] text-[var(--green)]">
            Mon compte
          </p>
          <h1 className="mt-3 font-display text-4xl font-semibold text-[var(--navy)]">
            Profil
          </h1>
          <form
            className="mt-8 space-y-5 border border-border bg-white p-6 shadow-editorial sm:p-8"
            onSubmit={onSubmit}
          >
            <label className="block text-sm font-semibold text-[var(--navy)]">
              Nom affiche
              <input
                required
                value={displayName}
                onChange={(event) => setDisplayName(event.target.value)}
                className="mt-2 w-full rounded-lg border border-border px-3 py-2.5 font-normal outline-none focus:border-[var(--green)] focus:ring-2 focus:ring-[var(--green)]/20"
              />
              {fieldErrors.display_name?.map((error) => (
                <span key={error} className="mt-2 block text-sm text-red-700">
                  {error}
                </span>
              ))}
            </label>
            <label className="block text-sm font-semibold text-[var(--navy)]">
              Email
              <input
                readOnly
                value={auth.user?.email ?? ""}
                className="mt-2 w-full rounded-lg border border-border bg-[var(--navy-soft)] px-3 py-2.5 font-normal text-muted-foreground"
              />
              {fieldErrors.email?.map((error) => (
                <span key={error} className="mt-2 block text-sm text-red-700">
                  {error}
                </span>
              ))}
            </label>
            <label className="block text-sm font-semibold text-[var(--navy)]">
              Type de compte
              <input
                readOnly
                value={auth.user?.account_type === "individual" ? "Lecteur individuel" : ""}
                className="mt-2 w-full rounded-lg border border-border bg-[var(--navy-soft)] px-3 py-2.5 font-normal text-muted-foreground"
              />
            </label>
            {message ? (
              <p role="status" className="text-sm text-[var(--green)]">
                {message}
              </p>
            ) : null}
            <button
              disabled={isSubmitting}
              className="rounded-lg bg-[var(--navy)] px-4 py-3 text-sm font-semibold text-white transition hover:bg-[var(--navy-deep)] disabled:opacity-60"
            >
              {isSubmitting ? "Enregistrement..." : "Enregistrer"}
            </button>
          </form>
        </div>
      </main>
    </SiteLayout>
  );
}
