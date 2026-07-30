import { createContext, useContext, useEffect, useMemo, useState } from "react";

import { getCurrentUser, logout as logoutRequest } from "@/api/auth";
import type { ApiUser, AuthTokens } from "@/api/types";
import { tokenStore } from "@/auth/tokenStore";

interface AuthContextValue {
  user: ApiUser | null;
  tokens: AuthTokens | null;
  isHydrating: boolean;
  setSession(session: { user: ApiUser; tokens: AuthTokens }): void;
  logout(): Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<ApiUser | null>(null);
  const [tokens, setTokens] = useState<AuthTokens | null>(null);
  const [isHydrating, setIsHydrating] = useState(true);

  useEffect(() => {
    const storedTokens = tokenStore.get();

    if (!storedTokens) {
      setIsHydrating(false);
      return;
    }

    setTokens(storedTokens);
    getCurrentUser(storedTokens.access)
      .then(setUser)
      .catch(() => {
        tokenStore.clear();
        setTokens(null);
      })
      .finally(() => setIsHydrating(false));
  }, []);

  const value = useMemo<AuthContextValue>(() => ({
    user,
    tokens,
    isHydrating,
    setSession(session) {
      tokenStore.set(session.tokens);
      setTokens(session.tokens);
      setUser(session.user);
      setIsHydrating(false);
    },
    async logout() {
      try {
        if (tokens) {
          await logoutRequest(tokens.refresh, tokens.access);
        }
      } finally {
        tokenStore.clear();
        setUser(null);
        setTokens(null);
      }
    }
  }), [isHydrating, tokens, user]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
