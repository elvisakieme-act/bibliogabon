import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, RouterProvider } from "@tanstack/react-router";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { createAppRouter } from "@/router";

afterEach(cleanup);

function renderAt(path: string) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } }
  });
  const router = createAppRouter({
    history: createMemoryHistory({ initialEntries: [path] })
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  );
}

describe("app foundation", () => {
  it("renders the discovery home route", async () => {
    renderAt("/");

    expect(
      await screen.findByRole("heading", { name: /BiblioGABON/i })
    ).toBeInTheDocument();
  });

  it("renders the route-level not-found state for unknown URLs", async () => {
    renderAt("/adresse-inconnue");

    expect(
      await screen.findByRole("heading", { name: "Page introuvable" })
    ).toBeInTheDocument();
  });
});
