import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ReaderControls } from "@/components/reader/ReaderControls";
import { ReaderPage } from "@/components/reader/ReaderPage";

describe("reader components", () => {
  it("renders page content without raw download controls", () => {
    render(
      <ReaderPage
        title="Droit public"
        page={{ session_key: "550e8400-e29b-41d4-a716-446655440000", document_id: 1, version_id: 1, page_number: 2, page_count: 5, language_code: "fr", text: "Page securisee" }}
      />
    );

    expect(screen.getByText("Page securisee")).toBeInTheDocument();
    expect(screen.queryByText(/Telecharger/i)).not.toBeInTheDocument();
  });

  it("calls previous and next controls", async () => {
    const previous = vi.fn();
    const next = vi.fn();
    render(
      <ReaderControls
        pageNumber={2}
        pageCount={5}
        onPrevious={previous}
        onNext={next}
      />
    );

    await userEvent.click(screen.getByRole("button", { name: /Page precedente/i }));
    await userEvent.click(screen.getByRole("button", { name: /Page suivante/i }));

    expect(previous).toHaveBeenCalledTimes(1);
    expect(next).toHaveBeenCalledTimes(1);
  });
});
