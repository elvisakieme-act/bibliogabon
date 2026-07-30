import fs from "node:fs";
import path from "node:path";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Logo } from "@/components/brand/Logo";
import { EmptyState } from "@/components/ui/EmptyState";

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
});
