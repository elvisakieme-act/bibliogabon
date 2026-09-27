import { useCallback, useEffect, useMemo, useState } from "react";

import { getCurrentUser, logout as logoutRequest } from "@/api/auth";
import { UNAUTHORIZED_EVENT } from "@/api/client";
import type { ApiUser, AuthTokens } from "@/api/types";
import { AuthContext, type AuthContextValue } from "@/auth/authContext";
import { tokenStore } from "@/auth/tokenStore";

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<ApiUser | null>(null);
  const [tokens, setTokens] = useState<AuthTokens | null>(null);
  const [isHydrating, setIsHydrating] = useState(true);

  const clearSession = useCallback(() => {
    tokenStore.clear();
    setUser(null);
    setTokens(null);
    setIsHydrating(false);
  }, []);

  useEffect(() => {
    const handleUnauthorized = () => clearSession();
    window.addEventListener(UNAUTHORIZED_EVENT, handleUnauthorized);
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, handleUnauthorized);
  }, [clearSession]);

  useEffect(() => {
    const storedTokens = tokenStore.get();

    if (!storedTokens) {
      setIsHydrating(false);
      return;
    }

    setTokens(storedTokens);
    getCurrentUser(storedTokens.access)
      .then(setUser)
      .catch(clearSession)
      .finally(() => setIsHydrating(false));
  }, [clearSession]);

  // Stable : un consommateur doit pouvoir mettre `setSession` dans les
  // dependances d'un effet sans provoquer de boucle. Recree a chaque
  // recalcul du memo, il rendait toute dependance correcte impossible.
  const setSession = useCallback((session: { user: ApiUser; tokens: AuthTokens }) => {
    tokenStore.set(session.tokens);
    setTokens(session.tokens);
    setUser(session.user);
    setIsHydrating(false);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      tokens,
      isHydrating,
      setSession,
      clearSession,
      async logout() {
        try {
          if (tokens) {
            await logoutRequest(tokens.refresh, tokens.access);
          }
        } finally {
          clearSession();
        }
      }
    }),
    [clearSession, isHydrating, setSession, tokens, user]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
