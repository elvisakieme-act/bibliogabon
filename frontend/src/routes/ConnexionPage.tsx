import { useState } from "react";
import { Link, useNavigate, useSearch } from "@tanstack/react-router";

import { getCurrentUser, login } from "@/api/auth";
import { useAuth } from "@/auth/AuthProvider";
import { Logo } from "@/components/brand/Logo";

export function ConnexionPage() {
  const auth = useAuth();
  const navigate = useNavigate();
  const search = useSearch({ from: "/connexion" });
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setIsSubmitting(true);
    try {
      const tokens = await login(email, password);
      const user = await getCurrentUser(tokens.access);
      auth.setSession({ user, tokens });
      await navigate({ to: search.next || "/" });
    } catch {
      setError("Connexion impossible. Verifiez vos identifiants et recommencez.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return <main className="grid min-h-screen lg:grid-cols-2"><section className="hidden bg-[var(--navy)] p-12 text-white lg:flex lg:flex-col lg:justify-between"><Logo className="text-white" /><div><p className="text-sm font-semibold uppercase tracking-[0.18em] text-[var(--gold)]">Espace lecteur</p><h1 className="mt-5 max-w-md font-display text-5xl font-semibold leading-tight">Retrouvez vos lectures.</h1><p className="mt-5 max-w-md text-white/75">Accedez a votre bibliotheque et poursuivez vos recherches.</p></div><p className="text-sm text-white/60">BiblioGABON</p></section><section className="flex items-center justify-center bg-background px-5 py-12"><div className="w-full max-w-md"><div className="mb-10 lg:hidden"><Logo /></div><p className="text-sm font-semibold uppercase tracking-[0.18em] text-[var(--green)]">Connexion</p><h1 className="mt-3 font-display text-4xl font-semibold text-[var(--navy)]">Bienvenue</h1><form className="mt-8 space-y-5" onSubmit={onSubmit}>{error ? <p role="alert" className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">{error}</p> : null}<label className="block text-sm font-semibold text-[var(--navy)]">Email<input required type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} className="mt-2 w-full rounded-lg border border-border bg-white px-3 py-2.5 font-normal outline-none focus:border-[var(--green)] focus:ring-2 focus:ring-[var(--green)]/20" /></label><label className="block text-sm font-semibold text-[var(--navy)]">Mot de passe<input required type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} className="mt-2 w-full rounded-lg border border-border bg-white px-3 py-2.5 font-normal outline-none focus:border-[var(--green)] focus:ring-2 focus:ring-[var(--green)]/20" /></label><button disabled={isSubmitting} className="w-full rounded-lg bg-[var(--navy)] px-4 py-3 text-sm font-semibold text-white transition hover:bg-[var(--navy-deep)] disabled:opacity-60">{isSubmitting ? "Connexion..." : "Se connecter"}</button></form><p className="mt-6 text-sm text-muted-foreground">Pas encore de compte ? <Link to="/inscription" className="font-semibold text-[var(--green)] hover:underline">S'inscrire</Link></p></div></section></main>;
}
