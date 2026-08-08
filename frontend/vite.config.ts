/// <reference types="vitest/config" />

import path from "node:path";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // Vite's Host header check rejects cloud dev proxies (Lightning AI,
    // Codespaces, etc.) by default. Allow known proxy domains by suffix
    // instead of listing individual session hostnames, which change per
    // workspace.
    allowedHosts: [".cloudspaces.litng.ai"]
  },
  resolve: {
    alias: {
      "@": path.resolve(import.meta.dirname, "src")
    }
  },
  // Vitest adds this property to the Vite config at runtime.
  // @ts-expect-error Vitest config augmentation is not included by Vite 8 types.
  test: {
    environment: "jsdom",
    setupFiles: "./src/setupTests.ts",
    css: true
  }
});
