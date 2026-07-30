import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/api/auth", () => ({
  getCurrentUser: vi.fn(),
  logout: vi.fn().mockResolvedValue(undefined)
}));

import { AuthProvider, useAuth } from "@/auth/AuthProvider";
import { tokenStore } from "@/auth/tokenStore";

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
});
