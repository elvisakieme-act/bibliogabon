import { useState } from "react";
import { Link, useNavigate } from "@tanstack/react-router";

import { registerIndividual } from "@/api/auth";
import { useAuth } from "@/auth/AuthProvider";
import { Logo } from "@/components/brand/Logo";

export function InscriptionPage() {
  const auth = useAuth();
  const navigate = useNavigate();
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setIsSubmitting(true);
    try {
      const session = await registerIndividual({ email, password, display_name: displayName });
      auth.setSession(session);
      await navigate({ to: "/profil" });
    } catch {
      setError("Inscription impossible. Verifiez les informations saisies.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return <main className="min-h-screen bg-background px-5 py-10 sm:py-16"><div className="mx-auto w-full max-w-md"><Logo /><section className="mt-10 border border-border bg-white p-6 shadow-editorial sm:p-8"><p className="text-sm font-semibold uppercase tracking-[0.18em] text-[var(--green)]">Creer un compte</p><h1 className="mt-3 font-display text-3xl font-semibold text-[var(--navy)]">Rejoindre BiblioGABON</h1><form className="mt-7 space-y-5" onSubmit={onSubmit}>{error ? <p role="alert" className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">{error}</p> : null}<label className="block text-sm font-semibold text-[var(--navy)]">Nom affiche<input required value={displayName} onChange={(event) => setDisplayName(event.target.value)} className="mt-2 w-full rounded-lg border border-border px-3 py-2.5 font-normal outline-none focus:border-[var(--green)] focus:ring-2 focus:ring-[var(--green)]/20" /></label><label className="block text-sm font-semibold text-[var(--navy)]">Email<input required type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} className="mt-2 w-full rounded-lg border border-border px-3 py-2.5 font-normal outline-none focus:border-[var(--green)] focus:ring-2 focus:ring-[var(--green)]/20" /></label><label className="block text-sm font-semibold text-[var(--navy)]">Mot de passe<input required type="password" autoComplete="new-password" value={password} onChange={(event) => setPassword(event.target.value)} className="mt-2 w-full rounded-lg border border-border px-3 py-2.5 font-normal outline-none focus:border-[var(--green)] focus:ring-2 focus:ring-[var(--green)]/20" /></label><button disabled={isSubmitting} className="w-full rounded-lg bg-[var(--navy)] px-4 py-3 text-sm font-semibold text-white transition hover:bg-[var(--navy-deep)] disabled:opacity-60">{isSubmitting ? "Creation..." : "Creer mon compte"}</button></form><p className="mt-6 text-sm text-muted-foreground">Deja inscrit ? <Link to="/connexion" className="font-semibold text-[var(--green)] hover:underline">Se connecter</Link></p></section></div></main>;
}
