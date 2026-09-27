import { Link, Outlet } from "@tanstack/react-router";

import { useAuth } from "@/auth/AuthProvider";
import { RequireRole } from "@/auth/guards";

const NAVIGATION = [
  { to: "/gestion", label: "Tableau de bord", exact: true },
  { to: "/gestion/documents", label: "Documents", exact: false }
] as const;

export function GestionLayout() {
  const auth = useAuth();

  return (
    <RequireRole>
      <div className="min-h-screen bg-slate-50 text-slate-900">
        {/* Bande gabonaise : la continuite visuelle avec l'espace lecture,
            sans en reprendre la grille editoriale, qui sert la decouverte
            et non la saisie. */}
        <div aria-hidden className="flex h-1">
          <span className="flex-1 bg-[#009E49]" />
          <span className="flex-1 bg-[#FCD116]" />
          <span className="flex-1 bg-[#3A75C4]" />
        </div>
        <header className="border-b border-slate-200 bg-white">
          <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-4 px-4 py-3">
            <h1 className="text-lg font-semibold">Espace de gestion</h1>
            <nav aria-label="Espace de gestion" className="flex gap-1 text-sm">
              {NAVIGATION.map((item) => (
                <Link
                  key={item.to}
                  to={item.to}
                  activeOptions={{ exact: item.exact }}
                  className="rounded px-3 py-1.5 text-slate-600 hover:bg-slate-100"
                  activeProps={{ className: "bg-slate-900 text-white hover:bg-slate-900" }}
                >
                  {item.label}
                </Link>
              ))}
            </nav>
            <p className="ms-auto text-sm text-slate-500">{auth.user?.display_name}</p>
          </div>
        </header>
        <main className="mx-auto max-w-6xl px-4 py-6">
          <Outlet />
        </main>
      </div>
    </RequireRole>
  );
}
