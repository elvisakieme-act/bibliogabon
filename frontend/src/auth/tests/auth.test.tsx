import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, RouterProvider } from "@tanstack/react-router";
import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/auth", () => ({
  getCurrentUser: vi.fn(),
  logout: vi.fn().mockResolvedValue(undefined),
  updateCurrentUser: vi.fn()
}));

import { getCurrentUser, updateCurrentUser } from "@/api/auth";
import { ApiError } from "@/api/client";
import { AuthProvider, useAuth } from "@/auth/AuthProvider";
import { tokenStore } from "@/auth/tokenStore";
import { createAppRouter } from "@/router";

const reader = {
  id: 1,
  email: "reader@example.ga",
  display_name: "Reader",
  account_type: "individual" as const
};

afterEach(() => {
  cleanup();
  tokenStore.clear();
  window.history.replaceState({}, "", "/");
  vi.resetAllMocks();
});

function Probe() {
  const auth = useAuth();
  return (
    <div>
      <span>{auth.user?.email ?? "anonymous"}</span>
      <button
        onClick={() => auth.setSession({
          user: { id: 1, email: "reader@example.ga", display_name: "Reader", account_type: "individual" },
          tokens: { access: "access", refresh: "refresh" }
        })}
      >
        set session
      </button>
      <button onClick={() => auth.logout()}>logout</button>
    </div>
  );
}

function renderAuth() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <Probe />
      </AuthProvider>
    </QueryClientProvider>
  );
}

function renderAt(path: string) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createAppRouter({ history: createMemoryHistory({ initialEntries: [path] }) });
  const view = render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  );
  return { router, view };
}

describe("AuthProvider", () => {
  it("stores and clears JWT session through tokenStore", async () => {
    tokenStore.clear();
    renderAuth();

    await userEvent.click(screen.getByRole("button", { name: "set session" }));
    expect(tokenStore.get()).toEqual({ access: "access", refresh: "refresh" });
    expect(screen.getByText("reader@example.ga")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "logout" }));
    await waitFor(() => expect(tokenStore.get()).toBeNull());
    expect(screen.getByText("anonymous")).toBeInTheDocument();
  });

  it("clears the stored session after a global unauthorized event", async () => {
    renderAuth();
    await userEvent.click(screen.getByRole("button", { name: "set session" }));

    act(() => {
      window.dispatchEvent(new Event("bibliogabon:unauthorized"));
    });

    await waitFor(() => expect(tokenStore.get()).toBeNull());
    expect(screen.getByText("anonymous")).toBeInTheDocument();
  });

  it("preserves the protected route query after an unauthorized event", async () => {
    window.history.replaceState({}, "", "/profil?tab=securite");
    tokenStore.set({ access: "access", refresh: "refresh" });
    vi.mocked(getCurrentUser).mockResolvedValue(reader);
    const { router } = renderAt("/profil?tab=securite");

    expect(await screen.findByRole("heading", { name: "Profil" })).toBeInTheDocument();

    act(() => {
      window.dispatchEvent(new Event("bibliogabon:unauthorized"));
    });

    await waitFor(() => expect(router.state.location.pathname).toBe("/connexion"));
    expect(router.state.location.search).toEqual({
      next: "/profil?tab=securite"
    });
  });

  it("shows normalized profile field errors after a failed update", async () => {
    tokenStore.set({ access: "access", refresh: "refresh" });
    vi.mocked(getCurrentUser).mockResolvedValue(reader);
    vi.mocked(updateCurrentUser).mockRejectedValue(new ApiError(
      400,
      "invalid_profile",
      "Profile data is invalid.",
      { display_name: ["Le nom affiche est obligatoire."] }
    ));

    renderAt("/profil");

    await userEvent.click(await screen.findByRole("button", { name: "Enregistrer" }));

    expect(await screen.findByText("Le nom affiche est obligatoire.")).toBeInTheDocument();
  });

  it("clears the session and redirects after a profile refresh 401", async () => {
    tokenStore.set({ access: "access", refresh: "refresh" });
    vi.mocked(getCurrentUser)
      .mockResolvedValueOnce(reader)
      .mockRejectedValueOnce(new ApiError(401, "token_not_valid", "Token is invalid."));

    renderAt("/profil");

    expect(await screen.findByRole("heading", { name: "Bienvenue" })).toBeInTheDocument();
    expect(tokenStore.get()).toBeNull();
  });

  it("clears the session and redirects after a profile update 401", async () => {
    tokenStore.set({ access: "access", refresh: "refresh" });
    vi.mocked(getCurrentUser).mockResolvedValue(reader);
    vi.mocked(updateCurrentUser).mockRejectedValue(new ApiError(401, "token_not_valid", "Token is invalid."));

    renderAt("/profil");

    await userEvent.click(await screen.findByRole("button", { name: "Enregistrer" }));

    expect(await screen.findByRole("heading", { name: "Bienvenue" })).toBeInTheDocument();
    expect(tokenStore.get()).toBeNull();
  });
});
