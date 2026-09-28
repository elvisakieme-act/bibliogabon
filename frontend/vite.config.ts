/// <reference types="vitest/config" />

import path from "node:path";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

// Vite's Host header check rejects cloud dev proxies (Lightning AI,
// Codespaces, etc.) by default. Allow known proxy domains by suffix instead
// of listing individual session hostnames, which change per workspace.
const DEFAULT_ALLOWED_HOSTS = [".cloudspaces.litng.ai"];

export default defineConfig(({ mode }) => {
  // Read .env / .env.<mode> so a remote workspace can set its own host and
  // port without hard-coding this machine's values in the repository.
  const env = loadEnv(mode, process.cwd(), "");
  const extraAllowedHosts = (env.VITE_DEV_ALLOWED_HOSTS || "")
    .split(",")
    .map((host) => host.trim())
    .filter(Boolean);

  return {
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        "@": path.resolve(import.meta.dirname, "src")
      }
    },
    server: {
      host: env.VITE_DEV_HOST || "127.0.0.1",
      port: Number(env.VITE_DEV_PORT || 5173),
      allowedHosts: [...DEFAULT_ALLOWED_HOSTS, ...extraAllowedHosts],
      // Relais de l'API, quand VITE_DEV_API_PROXY est renseigné.
      //
      // Derrière un proxy de développement en nuage, le navigateur parle à un
      // hôte et l'API à un autre : chaque écriture déclenche donc un
      // préliminaire CORS. Le proxy Lightning réécrit les en-têtes avec les
      // siens, et sa liste de méthodes **ne contient pas PATCH** — toute
      // modification de métadonnées était bloquée avant d'être envoyée.
      //
      // Relayer /api depuis Vite rend les requêtes de même origine : plus de
      // préliminaire, donc plus de liste de méthodes imposée par un tiers. Le
      // contrat de l'API ne bouge pas pour s'accommoder d'un outil de
      // développement.
      proxy: env.VITE_DEV_API_PROXY
        ? {
            "/api": {
              target: env.VITE_DEV_API_PROXY,
              changeOrigin: true
            }
          }
        : undefined
    },
    // Vitest adds this property to the Vite config at runtime.
    test: {
      environment: "jsdom",
      setupFiles: "./src/setupTests.ts",
      css: true
    }
  };
});
