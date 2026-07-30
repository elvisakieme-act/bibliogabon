import { Menu, Search, User } from "lucide-react";
import { useEffect, useState } from "react";

import { Logo } from "@/components/brand/Logo";

const NAV_ITEMS = [
  { to: "/", label: "Accueil" },
  { to: "/catalogue", label: "Catalogue" },
  { to: "/domaines", label: "Domaines" },
  { to: "/recherche", label: "Recherche" },
  { to: "/bibliotheque", label: "Bibliotheque" }
];

export function Navbar() {
  const [isScrolled, setIsScrolled] = useState(false);
  const [isMenuOpen, setIsMenuOpen] = useState(false);

  useEffect(() => {
    const onScroll = () => setIsScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <header className={`sticky top-0 z-40 w-full transition-all duration-200 ${isScrolled ? "glass-surface border-b border-border shadow-editorial" : "bg-white/80 backdrop-blur-sm"}`}>
      <div className="h-1 gabon-stripe" aria-hidden="true" />
      <div className="container-editorial flex h-16 items-center gap-5">
        <Logo />
        <nav aria-label="Navigation principale" className="hidden items-center gap-1 lg:flex">
          {NAV_ITEMS.map((item) => <a key={item.to} href={item.to} className="rounded-lg px-3 py-2 text-sm font-semibold text-[var(--navy)] transition hover:bg-[var(--navy-soft)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--gold)]">{item.label}</a>)}
        </nav>
        <div className="ml-auto hidden items-center gap-2 md:flex">
          <a href="/recherche" aria-label="Recherche" className="rounded-lg p-2 text-[var(--navy)] transition hover:bg-[var(--navy-soft)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--gold)]"><Search className="size-5" /></a>
          <a href="/connexion" className="inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-semibold text-[var(--navy)] transition hover:bg-[var(--navy-soft)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--gold)]"><User className="size-4" />Connexion</a>
          <a href="/inscription" className="rounded-lg bg-[var(--navy)] px-3 py-2 text-sm font-semibold text-white transition hover:bg-[var(--navy-deep)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--gold)]">S'inscrire</a>
        </div>
        <button type="button" className="ml-auto rounded-lg p-2 text-[var(--navy)] transition hover:bg-[var(--navy-soft)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--gold)] lg:hidden" aria-label="Menu" aria-expanded={isMenuOpen} onClick={() => setIsMenuOpen((open) => !open)}><Menu className="size-5" /></button>
      </div>
      {isMenuOpen ? <nav aria-label="Navigation mobile" className="border-t border-border bg-white lg:hidden"><div className="container-editorial py-3">{NAV_ITEMS.map((item) => <a key={item.to} href={item.to} onClick={() => setIsMenuOpen(false)} className="block rounded-lg px-3 py-2.5 text-sm font-semibold text-[var(--navy)] hover:bg-[var(--navy-soft)]">{item.label}</a>)}<div className="mt-3 grid grid-cols-2 gap-2 border-t border-border pt-3"><a href="/connexion" className="rounded-lg border border-border px-3 py-2 text-center text-sm font-semibold text-[var(--navy)]">Connexion</a><a href="/inscription" className="rounded-lg bg-[var(--navy)] px-3 py-2 text-center text-sm font-semibold text-white">S'inscrire</a></div></div></nav> : null}
    </header>
  );
}
