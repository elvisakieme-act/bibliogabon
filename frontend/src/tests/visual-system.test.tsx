import fs from "node:fs";
import path from "node:path";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Logo } from "@/components/brand/Logo";
import { Footer } from "@/components/layout/Footer";
import { Navbar } from "@/components/layout/Navbar";
import { EmptyState } from "@/components/ui/EmptyState";
import { AuthProvider } from "@/auth/AuthProvider";

describe("maquette visual system", () => {
  it("preserves BiblioGABON brand tokens and motion utilities", () => {
    const css = fs.readFileSync(
      path.resolve(process.cwd(), "src/styles/globals.css"),
      "utf8"
    );

    expect(css).toContain("--navy:");
    expect(css).toContain("--green:");
    expect(css).toContain("--gold:");
    expect(css).toContain(".gabon-stripe");
    expect(css).toContain(".shadow-editorial");
    expect(css).toContain("@keyframes ken-burns");
    expect(css).toContain("@media (prefers-reduced-motion: reduce)");
  });

  it("renders the real logo with accessible text", () => {
    render(<Logo withWordmark={true} />);

    expect(screen.getByLabelText(/BiblioGABON/i)).toBeInTheDocument();
  });

  it("uses the maquette empty state pattern", () => {
    render(
      <EmptyState
        title="Aucun document"
        description="Essayez un autre filtre."
      />
    );

    expect(screen.getByText("Aucun document")).toBeInTheDocument();
    expect(screen.getByText("Essayez un autre filtre.")).toBeInTheDocument();
  });

  it("keeps primary navigation reachable below the large breakpoint", () => {
    const navbarSource = fs.readFileSync(
      path.resolve(process.cwd(), "src/components/layout/Navbar.tsx"),
      "utf8"
    );

    expect(navbarSource).toContain("lg:flex");
    expect(navbarSource).toContain("lg:hidden");
    expect(navbarSource).not.toContain("md:hidden");
  });

  it("shows logged-out account affordances without a logout action", () => {
    render(<AuthProvider><Navbar /></AuthProvider>);

    expect(screen.getByRole("link", { name: "Connexion" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "S'inscrire" })).toBeInTheDocument();
    expect(screen.queryByLabelText("Se deconnecter")).not.toBeInTheDocument();
  });

  it("uses a Gabon stripe and readable logo in the footer", () => {
    const { container } = render(<Footer />);

    expect(container.querySelector("footer > .gabon-stripe")).toBeInTheDocument();
    expect(
      container.querySelector('footer a[aria-label="BiblioGABON"]')
    ).toHaveClass("text-[var(--navy)]");
  });
});
