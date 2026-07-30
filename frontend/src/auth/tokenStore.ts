import type { AuthTokens } from "@/api/types";

const STORAGE_KEY = "bibliogabon.tokens";

export const tokenStore = {
  get(): AuthTokens | null {
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY);
      return raw ? (JSON.parse(raw) as AuthTokens) : null;
    } catch {
      return null;
    }
  },
  set(tokens: AuthTokens) {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(tokens));
  },
  clear() {
    window.localStorage.removeItem(STORAGE_KEY);
  }
};
