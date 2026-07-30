import { Logo } from "@/components/brand/Logo";

const FOOTER_LINKS = [
  { href: "/catalogue", label: "Catalogue" },
  { href: "/domaines", label: "Domaines" },
  { href: "/recherche", label: "Recherche" },
  { href: "/bibliotheque", label: "Bibliotheque" }
];

export function Footer() {
  return (
    <footer className="mt-auto bg-[var(--navy-deep)] text-white/80">
      <div className="gabon-rule" aria-hidden="true" />
      <div className="container-editorial grid gap-10 py-12 md:grid-cols-[1.5fr_1fr]">
        <div>
          <div className="inline-flex rounded-xl bg-white px-3 py-2"><Logo /></div>
          <p className="mt-4 max-w-md text-sm">La bibliotheque numerique des universites et grandes ecoles de la Republique Gabonaise.</p>
        </div>
        <div>
          <h2 className="font-display text-lg text-white">Explorer</h2>
          <ul className="mt-3 grid grid-cols-2 gap-2 text-sm">{FOOTER_LINKS.map((link) => <li key={link.href}><a href={link.href} className="transition hover:text-[var(--gold)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--gold)]">{link.label}</a></li>)}</ul>
        </div>
      </div>
      <div className="border-t border-white/15"><div className="container-editorial py-4 text-xs text-white/60">Copyright 2026 BiblioGABON. Republique Gabonaise.</div></div>
    </footer>
  );
}
