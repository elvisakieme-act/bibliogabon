import { Link, Outlet } from "@tanstack/react-router";

import { useAuth } from "@/auth/useAuth";
import { RequireRole } from "@/auth/guards";

const NAVIGATION = [
  { to: "/gestion", label: "Tableau de bord", exact: true },
  { to: "/gestion/documents", label: "Documents", exact: false },
  { to: "/gestion/revues", label: "Revue", exact: false },
  { to: "/gestion/organisations", label: "Organisations", exact: false },
  { to: "/gestion/support", label: "Support", exact: false }
] as const;

export function GestionLayout() {
  const auth = useAuth();

  return (
    <RequireRole>
      <div className="min-h-screen bg-[var(--muted)] text-[var(--ink)]">
        {/* Bande gabonaise : la continuite visuelle avec l'espace lecture,
            sans en reprendre la grille éditoriale, qui sert la découverte
            et non la saisie. */}
        <div aria-hidden className="flex h-1">
          <span className="flex-1 bg-[#009E49]" />
          <span className="flex-1 bg-[#FCD116]" />
          <span className="flex-1 bg-[#3A75C4]" />
        </div>
        <header className="border-b border-[var(--border)] bg-white/90 backdrop-blur-sm">
          <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-5 px-4 py-4">
            <h1 className="font-display text-xl text-[var(--navy)]">Espace de gestion</h1>
            <nav aria-label="Espace de gestion" className="flex gap-1 text-sm">
              {NAVIGATION.map((item) => (
                <Link
                  key={item.to}
                  to={item.to}
                  activeOptions={{ exact: item.exact }}
                  className="rounded-[var(--radius)] px-3 py-2 font-semibold text-[var(--navy)] transition hover:bg-[var(--navy-soft)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--gold)]"
                  activeProps={{
                    className:
                      "bg-[var(--navy)] text-white shadow-editorial hover:bg-[var(--navy-deep)]"
                  }}
                >
                  {item.label}
                </Link>
              ))}
            </nav>
            <p className="ms-auto text-sm text-[var(--muted-foreground)]">
              {auth.user?.display_name}
            </p>
          </div>
        </header>
        <main className="mx-auto max-w-6xl px-4 py-8">
          <Outlet />
        </main>
      </div>
    </RequireRole>
  );
}
