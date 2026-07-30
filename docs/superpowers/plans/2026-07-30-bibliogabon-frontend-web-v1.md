# BiblioGABON Frontend Web V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first real reader-facing BiblioGABON web frontend in a clean `frontend/` app connected to `/api/v1/`.

**Architecture:** Create a new React/Vite app instead of modifying `maquette-bibliogabon/`. Preserve the maquette's visual DNA through migrated tokens, assets, and components, while rebuilding routing, API state, authentication, reader sessions, and library flows around the public API V1 contract.

**Tech Stack:** React, TypeScript, Vite, TanStack Router, TanStack Query, Tailwind CSS, Radix/shadcn-style primitives, lucide-react, Vitest, Testing Library.

## Global Constraints

- Create and modify code only under `frontend/` for the application implementation.
- Do not mutate `maquette-bibliogabon/`; it is the UI/UX reference project.
- Runtime data must come from `/api/v1/`, not `src/data/*` mock files.
- Preserve the maquette visual DNA documented in `docs/product/03-frontend-maquette-ui-audit.md`.
- Use `VITE_API_BASE_URL` for the backend base URL, defaulting to `http://127.0.0.1:8000`.
- The client must send JSON request bodies only.
- Use JWT access and refresh tokens for authenticated API requests.
- Registration creates only individual reader accounts; do not expose teacher, staff, or institution role selection.
- Free or open-access documents can open the reader anonymously.
- Restricted documents show login or entitlement-required states.
- Never expose raw files, storage keys, signed URLs, OCR full text, payment metadata, detailed reading logs, or download links.
- Keep the UI mobile-first and low-bandwidth aware.
- Use TDD: write failing tests first, run red, implement, run green, then commit.

---

## File Structure

```text
frontend/
  .env.example
  index.html
  package.json
  tsconfig.json
  vite.config.ts
  src/
    main.tsx
    router.tsx
    setupTests.ts
    styles/
      globals.css
    api/
      auth.ts
      catalog.ts
      client.ts
      library.ts
      reader.ts
      types.ts
      tests/
        client.test.ts
    auth/
      AuthProvider.tsx
      guards.tsx
      tokenStore.ts
      tests/
        auth.test.tsx
    components/
      brand/
        Logo.tsx
      catalog/
        CatalogFilters.tsx
        DocumentCard.tsx
        DocumentCover.tsx
        DomainBadge.tsx
        PaginationControls.tsx
      layout/
        Footer.tsx
        Navbar.tsx
        SiteLayout.tsx
      reader/
        ReaderControls.tsx
        ReaderPage.tsx
      ui/
        Button.tsx
        EmptyState.tsx
        Reveal.tsx
        Skeleton.tsx
    features/
      catalog/
        hooks.ts
      library/
        hooks.ts
      reader/
        hooks.ts
    routes/
      BibliothequePage.tsx
      CatalogPage.tsx
      ConnexionPage.tsx
      DocumentDetailPage.tsx
      DomainDetailPage.tsx
      DomainesPage.tsx
      HomePage.tsx
      InscriptionPage.tsx
      LecturePage.tsx
      ProfilPage.tsx
      RecherchePage.tsx
    tests/
      catalog-routes.test.tsx
      reader-route.test.tsx
```

Responsibilities:

- `src/api/*`: typed HTTP calls, error parsing, JSON-only requests, JWT headers.
- `src/auth/*`: token storage, session hydration, route guards.
- `src/components/*`: maquette-derived visual components and small UI primitives.
- `src/features/*`: query and mutation hooks by product domain.
- `src/routes/*`: route-level composition, URL query parsing, page states.

---

### Task 1: Frontend App Foundation

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/index.html`
- Create: `frontend/tsconfig.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/eslint.config.js`
- Create: `frontend/.env.example`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/router.tsx`
- Create: `frontend/src/setupTests.ts`
- Create: `frontend/src/styles/globals.css`
- Create: `frontend/src/routes/HomePage.tsx`
- Create: `frontend/src/tests/app-foundation.test.tsx`

**Interfaces:**
- Produces `createAppRouter()`.
- Produces `HomePage`.
- Produces npm scripts: `dev`, `build`, `lint`, `test`, `test:watch`.

- [ ] **Step 1: Create package and config files**

Create `frontend/package.json`:

```json
{
  "name": "bibliogabon-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite --host 127.0.0.1",
    "build": "tsc --noEmit && vite build",
    "lint": "eslint .",
    "test": "vitest run",
    "test:watch": "vitest"
  },
  "dependencies": {
    "@radix-ui/react-dialog": "^1.1.15",
    "@radix-ui/react-dropdown-menu": "^2.1.16",
    "@radix-ui/react-navigation-menu": "^1.2.14",
    "@radix-ui/react-slot": "^1.2.4",
    "@radix-ui/react-tooltip": "^1.2.8",
    "@tanstack/react-query": "^5.101.1",
    "@tanstack/react-router": "^1.170.16",
    "@tailwindcss/vite": "^4.2.1",
    "class-variance-authority": "^0.7.1",
    "clsx": "^2.1.1",
    "lucide-react": "^0.575.0",
    "react": "^19.2.0",
    "react-dom": "^19.2.0",
    "tailwind-merge": "^3.5.0",
    "tailwindcss": "^4.2.1"
  },
  "devDependencies": {
    "@eslint/js": "^9.32.0",
    "@testing-library/jest-dom": "^6.6.3",
    "@testing-library/react": "^16.2.0",
    "@testing-library/user-event": "^14.6.1",
    "@types/node": "^22.16.5",
    "@types/react": "^19.2.0",
    "@types/react-dom": "^19.2.0",
    "@vitejs/plugin-react": "^5.2.0",
    "eslint": "^9.32.0",
    "eslint-config-prettier": "^10.1.1",
    "eslint-plugin-react-hooks": "^5.2.0",
    "eslint-plugin-react-refresh": "^0.4.20",
    "globals": "^15.15.0",
    "jsdom": "^26.1.0",
    "typescript": "^5.8.3",
    "typescript-eslint": "^8.56.1",
    "vite": "^8.0.16",
    "vitest": "^3.2.4"
  }
}
```

Create `frontend/.env.example`:

```text
VITE_API_BASE_URL=http://127.0.0.1:8000
```

- [ ] **Step 2: Add TypeScript, Vite, and test setup**

Create `frontend/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "useDefineForClassFields": true,
    "lib": ["DOM", "DOM.Iterable", "ES2022"],
    "allowJs": false,
    "skipLibCheck": true,
    "esModuleInterop": true,
    "allowSyntheticDefaultImports": true,
    "strict": true,
    "forceConsistentCasingInFileNames": true,
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "types": ["vitest/globals", "@testing-library/jest-dom"]
  },
  "include": ["src", "vite.config.ts"]
}
```

Create `frontend/vite.config.ts`:

```ts
import path from "node:path";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src")
    }
  },
  test: {
    environment: "jsdom",
    setupFiles: "./src/setupTests.ts",
    css: true
  }
});
```

Create `frontend/src/setupTests.ts`:

```ts
import "@testing-library/jest-dom/vitest";
```

Create `frontend/eslint.config.js`:

```js
import js from "@eslint/js";
import globals from "globals";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import tseslint from "typescript-eslint";
import prettier from "eslint-config-prettier";

export default tseslint.config(
  { ignores: ["dist"] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ["**/*.{ts,tsx}"],
    languageOptions: {
      ecmaVersion: 2022,
      globals: globals.browser
    },
    plugins: {
      "react-hooks": reactHooks,
      "react-refresh": reactRefresh
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      "react-refresh/only-export-components": [
        "warn",
        { allowConstantExport: true }
      ]
    }
  },
  prettier
);
```

- [ ] **Step 3: Write failing router smoke test**

Create `frontend/src/tests/app-foundation.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, RouterProvider } from "@tanstack/react-router";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { createAppRouter } from "@/router";

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
});
```

- [ ] **Step 4: Run the test red**

Run from `frontend/`:

```powershell
npm install
npm run test -- src/tests/app-foundation.test.tsx
```

Expected: FAIL because `src/router.tsx` and `HomePage` do not exist.

- [ ] **Step 5: Implement the minimal app shell**

Create `frontend/index.html`:

```html
<!doctype html>
<html lang="fr">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>BiblioGABON</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

Create `frontend/src/routes/HomePage.tsx`:

```tsx
export function HomePage() {
  return (
    <main>
      <h1>BiblioGABON</h1>
      <p>Bibliotheque numerique academique nationale du Gabon.</p>
    </main>
  );
}
```

Create `frontend/src/styles/globals.css`:

```css
@import "tailwindcss";

body {
  margin: 0;
  font-family: system-ui, sans-serif;
}
```

Create `frontend/src/router.tsx`:

```tsx
import {
  Outlet,
  createRootRoute,
  createRoute,
  createRouter,
  type RouterOptions
} from "@tanstack/react-router";

import { HomePage } from "@/routes/HomePage";

const rootRoute = createRootRoute({
  component: () => <Outlet />
});

const homeRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  component: HomePage
});

const routeTree = rootRoute.addChildren([homeRoute]);

export function createAppRouter(
  options: Partial<RouterOptions<typeof routeTree>> = {}
) {
  return createRouter({
    routeTree,
    defaultPreload: "intent",
    scrollRestoration: true,
    ...options
  });
}

export type AppRouter = ReturnType<typeof createAppRouter>;

declare module "@tanstack/react-router" {
  interface Register {
    router: AppRouter;
  }
}
```

Create `frontend/src/main.tsx`:

```tsx
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "@tanstack/react-router";

import { createAppRouter } from "@/router";

import "@/styles/globals.css";

const queryClient = new QueryClient();
const router = createAppRouter();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </StrictMode>
);
```

- [ ] **Step 6: Run tests and build**

Run from `frontend/`:

```powershell
npm run test -- src/tests/app-foundation.test.tsx
npm run build
```

Expected: tests pass and build succeeds.

- [ ] **Step 7: Commit**

```powershell
git add frontend
git commit -m "feat: scaffold frontend app"
```

---

### Task 2: Maquette Visual System And Layout Components

**Files:**
- Create: `frontend/public/bibliogabon-logo.png`
- Create: `frontend/public/favicon.ico`
- Modify: `frontend/src/styles/globals.css`
- Create: `frontend/src/components/brand/Logo.tsx`
- Create: `frontend/src/components/ui/Button.tsx`
- Create: `frontend/src/components/ui/EmptyState.tsx`
- Create: `frontend/src/components/ui/Reveal.tsx`
- Create: `frontend/src/components/ui/Skeleton.tsx`
- Create: `frontend/src/components/layout/Navbar.tsx`
- Create: `frontend/src/components/layout/Footer.tsx`
- Create: `frontend/src/components/layout/SiteLayout.tsx`
- Modify: `frontend/src/routes/HomePage.tsx`
- Modify: `frontend/src/router.tsx`
- Test: `frontend/src/tests/visual-system.test.tsx`

**Interfaces:**
- Consumes `createAppRouter()`.
- Produces `SiteLayout`, `Navbar`, `Footer`, `Button`, `EmptyState`, `Reveal`, `Skeleton`, `Logo`.

- [ ] **Step 1: Write failing visual system tests**

Create `frontend/src/tests/visual-system.test.tsx`:

```tsx
import fs from "node:fs";
import path from "node:path";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { EmptyState } from "@/components/ui/EmptyState";
import { Logo } from "@/components/brand/Logo";

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
    render(<EmptyState title="Aucun document" description="Essayez un autre filtre." />);

    expect(screen.getByText("Aucun document")).toBeInTheDocument();
    expect(screen.getByText("Essayez un autre filtre.")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run tests red**

Run from `frontend/`:

```powershell
npm run test -- src/tests/visual-system.test.tsx
```

Expected: FAIL because visual components and tokens do not exist.

- [ ] **Step 3: Copy approved brand assets**

Copy these files without modifying `maquette-bibliogabon/`:

```text
maquette-bibliogabon/public/bibliogabon-logo.png -> frontend/public/bibliogabon-logo.png
maquette-bibliogabon/public/favicon.ico -> frontend/public/favicon.ico
```

Do not copy `public/docs/` or demo EPUB files.

- [ ] **Step 4: Replace global CSS with visual tokens**

Replace `frontend/src/styles/globals.css` with the maquette token subset:

```css
@import "tailwindcss";

@theme inline {
  --font-display: "Fraunces", ui-serif, Georgia, serif;
  --font-sans: "Space Grotesk", ui-sans-serif, system-ui, sans-serif;
  --color-background: var(--background);
  --color-foreground: var(--foreground);
  --color-navy: var(--navy);
  --color-navy-deep: var(--navy-deep);
  --color-navy-soft: var(--navy-soft);
  --color-green: var(--green);
  --color-green-soft: var(--green-soft);
  --color-gold: var(--gold);
  --color-gold-soft: var(--gold-soft);
  --color-muted: var(--muted);
  --color-muted-foreground: var(--muted-foreground);
  --color-border: var(--border);
  --color-card: var(--card);
  --shadow-editorial:
    0 1px 2px rgba(6, 39, 81, 0.04),
    0 8px 24px -12px rgba(6, 39, 81, 0.12),
    0 24px 48px -32px rgba(6, 39, 81, 0.18);
  --shadow-editorial-lg:
    0 2px 4px rgba(6, 39, 81, 0.06),
    0 16px 40px -16px rgba(6, 39, 81, 0.18),
    0 40px 80px -40px rgba(6, 39, 81, 0.28);
}

:root {
  --radius: 0.875rem;
  --navy: oklch(0.28 0.09 258);
  --navy-deep: oklch(0.18 0.06 258);
  --navy-soft: oklch(0.96 0.015 250);
  --green: oklch(0.5 0.13 152);
  --green-soft: oklch(0.96 0.03 152);
  --gold: oklch(0.78 0.15 82);
  --gold-soft: oklch(0.9 0.11 88);
  --ink: oklch(0.18 0.03 258);
  --surface-alt: oklch(0.98 0.006 250);
  --background: oklch(1 0 0);
  --foreground: var(--ink);
  --card: oklch(1 0 0);
  --muted: var(--surface-alt);
  --muted-foreground: oklch(0.5 0.02 250);
  --border: oklch(0.92 0.01 250);
}

html {
  font-family: var(--font-sans);
  -webkit-font-smoothing: antialiased;
  text-rendering: optimizeLegibility;
}

body {
  margin: 0;
  background: var(--background);
  color: var(--foreground);
  font-family: var(--font-sans);
  line-height: 1.7;
}

h1,
h2,
h3,
.font-display {
  font-family: var(--font-display);
}

.container-editorial {
  width: 100%;
  max-width: 1200px;
  margin-inline: auto;
  padding-inline: 1.25rem;
}

@media (min-width: 768px) {
  .container-editorial {
    padding-inline: 2rem;
  }
}

.gabon-stripe {
  background: linear-gradient(
    90deg,
    var(--green) 0 33.33%,
    var(--gold) 33.33% 66.66%,
    var(--navy) 66.66% 100%
  );
}

.gabon-rule {
  height: 3px;
  background: linear-gradient(90deg, var(--green), var(--gold), var(--navy));
  border-radius: 999px;
}

.glass-surface {
  background: color-mix(in oklch, var(--card) 80%, transparent);
  backdrop-filter: blur(12px) saturate(140%);
}

.shadow-editorial {
  box-shadow: var(--shadow-editorial);
}

.shadow-editorial-lg {
  box-shadow: var(--shadow-editorial-lg);
}

@keyframes ken-burns {
  0% { transform: scale(1.05) translate3d(0, 0, 0); }
  50% { transform: scale(1.16) translate3d(-2%, -1.5%, 0); }
  100% { transform: scale(1.05) translate3d(0, 0, 0); }
}

.animate-ken-burns {
  animation: ken-burns 26s ease-in-out infinite;
  transform-origin: center;
}

@keyframes caret-blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

.animate-caret {
  animation: caret-blink 1s step-end infinite;
}

@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.001ms !important;
    transition-duration: 0.001ms !important;
  }
}
```

- [ ] **Step 5: Implement shared components**

Implement `Logo`, `Button`, `EmptyState`, `Reveal`, `Skeleton`, `Navbar`, `Footer`, and `SiteLayout`. Preserve:

- top `gabon-stripe` on nav/footer surfaces;
- glass navbar scroll state;
- mobile menu;
- gold focus ring;
- maquette rounded card language.

`Navbar` V1 links must be:

```ts
const NAV_ITEMS = [
  { to: "/", label: "Accueil" },
  { to: "/catalogue", label: "Catalogue" },
  { to: "/domaines", label: "Domaines" },
  { to: "/recherche", label: "Recherche" },
  { to: "/bibliotheque", label: "Bibliotheque" }
];
```

Use these exported component contracts:

```tsx
// components/brand/Logo.tsx
interface LogoProps {
  withWordmark?: boolean;
  className?: string;
}
export function Logo({ withWordmark = true, className }: LogoProps) {
  return (
    <a href="/" aria-label="BiblioGABON" className={className}>
      <img src="/bibliogabon-logo.png" alt="" className="h-10 w-10" />
      {withWordmark ? <span className="font-display text-xl">BiblioGABON</span> : null}
    </a>
  );
}

// components/ui/Button.tsx
import type React from "react";

type ButtonVariant = "primary" | "outline" | "ghost";
export type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
};
export function Button({ variant = "primary", className, ...props }: ButtonProps) {
  const variants = {
    primary: "bg-[var(--navy)] text-white hover:bg-[var(--navy-deep)]",
    outline: "border border-border bg-white text-[var(--navy)]",
    ghost: "bg-transparent text-[var(--navy)] hover:bg-[var(--navy-soft)]"
  };
  return (
    <button
      className={`rounded-xl px-4 py-2 font-semibold ring-[var(--gold)] focus-visible:outline-none focus-visible:ring-2 ${variants[variant]} ${className ?? ""}`}
      {...props}
    />
  );
}

// components/ui/EmptyState.tsx
export function EmptyState({ title, description }: { title: string; description: string }) {
  return (
    <section className="rounded-2xl border border-border bg-white p-8 text-center shadow-editorial">
      <div className="mx-auto mb-4 h-1 w-20 gabon-rule" aria-hidden="true" />
      <h2 className="font-display text-2xl text-[var(--navy)]">{title}</h2>
      <p className="mt-2 text-sm text-muted-foreground">{description}</p>
    </section>
  );
}

// components/layout/SiteLayout.tsx
export function SiteLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <Navbar />
      {children}
      <Footer />
    </div>
  );
}
```

`Skeleton` must accept `{ label?: string }` and render an animated loading block with an `aria-label`. `Reveal` must accept `{ children: React.ReactNode; className?: string }` and use the maquette fade-in class while respecting reduced-motion. `Navbar` must use `Menu`, `Search`, `User`, and `LogOut` icons from `lucide-react`, keep the sticky glass state on scroll, and expose the mobile menu button with `aria-expanded`.

- [ ] **Step 6: Wrap Home in SiteLayout**

Update `HomePage` to render through `SiteLayout` and include:

```tsx
<section className="relative overflow-hidden border-b border-border bg-[var(--navy)] text-white">
  <div className="h-1 gabon-stripe" aria-hidden="true" />
  <div className="container-editorial py-20">
    <p className="text-sm font-semibold uppercase tracking-[0.18em] text-[var(--gold)]">
      Bibliotheque academique nationale
    </p>
    <h1 className="mt-4 max-w-3xl font-display text-5xl font-semibold leading-tight">
      BiblioGABON
    </h1>
    <p className="mt-5 max-w-2xl text-white/80">
      Decouvrez, recherchez et lisez les ressources academiques du Gabon.
    </p>
  </div>
</section>
```

- [ ] **Step 7: Run tests and build**

Run from `frontend/`:

```powershell
npm run test -- src/tests/visual-system.test.tsx src/tests/app-foundation.test.tsx
npm run build
```

Expected: tests pass and build succeeds.

- [ ] **Step 8: Commit**

```powershell
git add frontend
git commit -m "feat: add frontend visual system"
```

---

### Task 3: API Client And Typed Contracts

**Files:**
- Create: `frontend/src/api/types.ts`
- Create: `frontend/src/api/client.ts`
- Create: `frontend/src/api/auth.ts`
- Create: `frontend/src/api/catalog.ts`
- Create: `frontend/src/api/reader.ts`
- Create: `frontend/src/api/library.ts`
- Create: `frontend/src/api/tests/client.test.ts`

**Interfaces:**
- Produces `ApiError`.
- Produces `apiRequest<T>(path: string, options?: ApiRequestOptions): Promise<T>`.
- Produces typed API functions consumed by auth, catalog, reader, and library hooks.

- [ ] **Step 1: Write failing API client tests**

Create `frontend/src/api/tests/client.test.ts`:

```ts
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, apiRequest } from "@/api/client";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("apiRequest", () => {
  it("sends JSON headers and bearer token", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "Content-Type": "application/json" }
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    await apiRequest("/api/v1/me/", {
      token: "abc123",
      method: "PATCH",
      body: { display_name: "Lecteur" }
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/v1/me/",
      expect.objectContaining({
        method: "PATCH",
        headers: expect.objectContaining({
          Authorization: "Bearer abc123",
          "Content-Type": "application/json",
          Accept: "application/json"
        }),
        body: JSON.stringify({ display_name: "Lecteur" })
      })
    );
  });

  it("raises ApiError from normalized error envelope", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            error: {
              code: "entitlement_required",
              message: "An active read entitlement is required.",
              field_errors: {}
            }
          }),
          { status: 403, headers: { "Content-Type": "application/json" } }
        )
      )
    );

    await expect(apiRequest("/api/v1/reader/sessions/", { method: "POST" }))
      .rejects.toMatchObject({
        code: "entitlement_required",
        status: 403
      });
  });

  it("returns undefined for 204 responses", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 204 })));

    await expect(apiRequest("/api/v1/auth/logout/", { method: "POST" })).resolves.toBeUndefined();
  });
});
```

- [ ] **Step 2: Run tests red**

Run from `frontend/`:

```powershell
npm run test -- src/api/tests/client.test.ts
```

Expected: FAIL because API client files do not exist.

- [ ] **Step 3: Implement API types**

Create `frontend/src/api/types.ts` with these exported interfaces:

```ts
export interface ApiErrorEnvelope {
  error: {
    code: string;
    message: string;
    field_errors: Record<string, string[]>;
  };
}

export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface ApiUser {
  id: number;
  email: string;
  display_name: string;
  account_type: "individual";
}

export interface AuthTokens {
  access: string;
  refresh: string;
}

export interface DomainSummary {
  id: number;
  name: string;
  slug: string;
}

export interface SearchDomainSummary {
  name: string;
  slug: string;
}

export interface DocumentMetadata {
  id: number;
  slug: string;
  title: string;
  abstract: string;
  language_code: string;
  publication_year: number | null;
  document_type: string;
  access_model: string;
  domain: DomainSummary | null;
  authors: Array<{ id: number; display_name: string; role: string }>;
  owner: string | null;
  page_count: number | null;
  cover: string | null;
  access: {
    can_read: boolean;
    access_model: string;
    reason: string;
  };
}

export interface ReaderSession {
  session_key: string;
  document_id: number;
  version_id: number;
  expires_at: string;
}

export interface ReaderPage {
  session_key: string;
  document_id: number;
  version_id: number;
  page_number: number;
  page_count: number;
  language_code: string;
  text: string;
}

export interface SearchResult {
  id: number;
  title: string;
  slug: string;
  abstract: string;
  language_code: string;
  publication_year: number | null;
  domain: SearchDomainSummary | null;
  authors: string[];
  access_model: string;
  indexed_page_count: number;
  score: number;
  text_match: boolean;
}

export interface FavoriteItem {
  document: DocumentMetadata;
  created_at: string;
}

export interface ReadingProgressItem {
  document: DocumentMetadata;
  last_page_number: number;
  updated_at: string;
}
```

- [ ] **Step 4: Implement `ApiError` and `apiRequest`**

Create `frontend/src/api/client.ts`:

```ts
import type { ApiErrorEnvelope } from "@/api/types";

const DEFAULT_API_BASE_URL = "http://127.0.0.1:8000";

export interface ApiRequestOptions {
  method?: string;
  token?: string | null;
  body?: unknown;
  signal?: AbortSignal;
}

export class ApiError extends Error {
  code: string;
  status: number;
  fieldErrors: Record<string, string[]>;

  constructor(status: number, code: string, message: string, fieldErrors = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.fieldErrors = fieldErrors;
  }
}

export function apiBaseUrl() {
  return import.meta.env.VITE_API_BASE_URL || DEFAULT_API_BASE_URL;
}

function urlFor(path: string) {
  if (path.startsWith("http")) return path;
  return `${apiBaseUrl()}${path.startsWith("/") ? path : `/${path}`}`;
}

async function parseError(response: Response): Promise<ApiError> {
  try {
    const payload = (await response.json()) as ApiErrorEnvelope;
    if (payload.error) {
      return new ApiError(
        response.status,
        payload.error.code,
        payload.error.message,
        payload.error.field_errors
      );
    }
  } catch {
    return new ApiError(response.status, "invalid_response", "The API response is invalid.");
  }
  return new ApiError(response.status, "request_failed", response.statusText);
}

export async function apiRequest<T>(
  path: string,
  options: ApiRequestOptions = {}
): Promise<T> {
  const headers: Record<string, string> = {
    Accept: "application/json"
  };
  if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
  }
  if (options.token) {
    headers.Authorization = `Bearer ${options.token}`;
  }

  const response = await fetch(urlFor(path), {
    method: options.method ?? "GET",
    headers,
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
    signal: options.signal
  });

  if (!response.ok) {
    throw await parseError(response);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}
```

- [ ] **Step 5: Implement endpoint modules**

Create `frontend/src/api/auth.ts`:

```ts
import { apiRequest } from "@/api/client";
import type { ApiUser, AuthTokens } from "@/api/types";

export interface RegisterInput {
  email: string;
  password: string;
  display_name?: string;
}

export interface ProfileUpdateInput {
  display_name?: string;
}

export function registerIndividual(input: RegisterInput) {
  return apiRequest<{ user: ApiUser; tokens: AuthTokens }>("/api/v1/auth/register/", {
    method: "POST",
    body: input
  });
}

export function login(email: string, password: string) {
  return apiRequest<AuthTokens>("/api/v1/auth/token/", {
    method: "POST",
    body: { email, password }
  });
}

export function refreshToken(refresh: string) {
  return apiRequest<AuthTokens>("/api/v1/auth/token/refresh/", {
    method: "POST",
    body: { refresh }
  });
}

export function logout(refresh: string, access: string) {
  return apiRequest<void>("/api/v1/auth/logout/", {
    method: "POST",
    token: access,
    body: { refresh }
  });
}

export function getCurrentUser(access: string) {
  return apiRequest<ApiUser>("/api/v1/me/", { token: access });
}

export function updateCurrentUser(access: string, input: ProfileUpdateInput) {
  return apiRequest<ApiUser>("/api/v1/me/", {
    method: "PATCH",
    token: access,
    body: input
  });
}
```

Create `frontend/src/api/catalog.ts`:

```ts
import { apiRequest } from "@/api/client";
import type {
  DocumentMetadata,
  DomainSummary,
  PaginatedResponse,
  SearchResult
} from "@/api/types";

type QueryValue = string | number | boolean | null | undefined;

function withQuery(path: string, params: Record<string, QueryValue> = {}) {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      query.set(key, String(value));
    }
  });
  const serialized = query.toString();
  return serialized ? `${path}?${serialized}` : path;
}

export function listDocuments(
  params: Record<string, QueryValue> = {},
  token?: string | null
) {
  return apiRequest<PaginatedResponse<DocumentMetadata>>(
    withQuery("/api/v1/catalog/documents/", params),
    { token }
  );
}

export function getDocument(documentId: number | string, token?: string | null) {
  return apiRequest<DocumentMetadata>(`/api/v1/catalog/documents/${documentId}/`, {
    token
  });
}

export function listDomains(params: Record<string, QueryValue> = {}) {
  return apiRequest<PaginatedResponse<DomainSummary>>(
    withQuery("/api/v1/catalog/domains/", params)
  );
}

export function searchDocuments(
  params: Record<string, QueryValue> = {},
  token?: string | null
) {
  return apiRequest<PaginatedResponse<SearchResult>>(
    withQuery("/api/v1/search/", params),
    { token }
  );
}
```

Create `frontend/src/api/reader.ts`:

```ts
import { apiRequest } from "@/api/client";
import type { ReaderPage, ReaderSession } from "@/api/types";

export function createReaderSession(documentId: number | string, access?: string | null) {
  return apiRequest<ReaderSession>("/api/v1/reader/sessions/", {
    method: "POST",
    token: access,
    body: { document_id: Number(documentId) }
  });
}

export function getReaderPage(
  sessionKey: string,
  pageNumber: number,
  access?: string | null
) {
  return apiRequest<ReaderPage>(
    `/api/v1/reader/sessions/${sessionKey}/pages/${pageNumber}/`,
    { token: access }
  );
}

export function closeReaderSession(sessionKey: string, access?: string | null) {
  return apiRequest<void>(`/api/v1/reader/sessions/${sessionKey}/`, {
    method: "DELETE",
    token: access
  });
}
```

Create `frontend/src/api/library.ts`:

```ts
import { apiRequest } from "@/api/client";
import type {
  FavoriteItem,
  PaginatedResponse,
  ReadingProgressItem
} from "@/api/types";

export function listFavorites(access: string) {
  return apiRequest<PaginatedResponse<FavoriteItem>>("/api/v1/me/favorites/", {
    token: access
  });
}

export function addFavorite(access: string, documentId: number | string) {
  return apiRequest<FavoriteItem>("/api/v1/me/favorites/", {
    method: "POST",
    token: access,
    body: { document_id: Number(documentId) }
  });
}

export function removeFavorite(access: string, documentId: number | string) {
  return apiRequest<void>(`/api/v1/me/favorites/${documentId}/`, {
    method: "DELETE",
    token: access
  });
}

export function listReadingProgress(access: string) {
  return apiRequest<PaginatedResponse<ReadingProgressItem>>(
    "/api/v1/me/reading-progress/",
    { token: access }
  );
}

export function updateReadingProgress(
  access: string,
  documentId: number | string,
  lastPageNumber: number
) {
  return apiRequest<ReadingProgressItem>(
    `/api/v1/me/reading-progress/${documentId}/`,
    {
      method: "PATCH",
      token: access,
      body: { last_page_number: lastPageNumber }
    }
  );
}
```

- [ ] **Step 6: Run tests**

Run from `frontend/`:

```powershell
npm run test -- src/api/tests/client.test.ts
npm run build
```

Expected: tests pass and build succeeds.

- [ ] **Step 7: Commit**

```powershell
git add frontend/src/api
git commit -m "feat: add frontend api client"
```

---

### Task 4: Authentication And User Session UI

**Files:**
- Create: `frontend/src/auth/tokenStore.ts`
- Create: `frontend/src/auth/AuthProvider.tsx`
- Create: `frontend/src/auth/guards.tsx`
- Create: `frontend/src/auth/tests/auth.test.tsx`
- Create: `frontend/src/routes/ConnexionPage.tsx`
- Create: `frontend/src/routes/InscriptionPage.tsx`
- Create: `frontend/src/routes/ProfilPage.tsx`
- Modify: `frontend/src/router.tsx`
- Modify: `frontend/src/components/layout/Navbar.tsx`

**Interfaces:**
- Consumes API auth functions from Task 3.
- Produces `useAuth()`.
- Produces `RequireAuth`.
- Produces `/connexion`, `/inscription`, `/profil`.

- [ ] **Step 1: Write failing auth tests**

Create `frontend/src/auth/tests/auth.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { AuthProvider, useAuth } from "@/auth/AuthProvider";
import { tokenStore } from "@/auth/tokenStore";

function Probe() {
  const auth = useAuth();
  return (
    <div>
      <span>{auth.user?.email ?? "anonymous"}</span>
      <button onClick={() => auth.setSession({
        user: { id: 1, email: "reader@example.ga", display_name: "Reader", account_type: "individual" },
        tokens: { access: "access", refresh: "refresh" }
      })}>
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
```

- [ ] **Step 2: Run auth tests red**

Run from `frontend/`:

```powershell
npm run test -- src/auth/tests/auth.test.tsx
```

Expected: FAIL because auth provider and token store do not exist.

- [ ] **Step 3: Implement token store**

Create `frontend/src/auth/tokenStore.ts`:

```ts
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
```

- [ ] **Step 4: Implement `AuthProvider` and `RequireAuth`**

Create `AuthProvider` with:

```ts
interface AuthContextValue {
  user: ApiUser | null;
  tokens: AuthTokens | null;
  isHydrating: boolean;
  setSession(session: { user: ApiUser; tokens: AuthTokens }): void;
  logout(): Promise<void>;
}
```

On mount, read `tokenStore.get()` and call `getCurrentUser(access)` when tokens exist. On 401 or failed hydration, clear tokens.

`logout` must use this control flow:

```ts
async function logoutCurrentSession(tokens: AuthTokens | null) {
  try {
    if (tokens) {
      await logout(tokens.refresh, tokens.access);
    }
  } finally {
    tokenStore.clear();
    setUser(null);
    setTokens(null);
  }
}
```

Create `RequireAuth`:

```tsx
export function RequireAuth({ children }: { children: React.ReactNode }) {
  const auth = useAuth();
  if (auth.isHydrating) return <Skeleton label="Chargement de la session" />;
  if (!auth.user) return <Navigate to="/connexion" search={{ next: window.location.pathname }} />;
  return children;
}
```

- [ ] **Step 5: Implement auth pages**

`ConnexionPage` must preserve the maquette split-screen login style without demo accounts. It submits:

```ts
const response = await login(email, password);
const user = await getCurrentUser(response.access);
auth.setSession({ user, tokens: response });
```

`InscriptionPage` must preserve the centered registration card style without role selection. Fields:

- display name;
- email;
- password.

It calls `registerIndividual`, then stores returned session.

`ProfilPage` uses `RequireAuth`, `GET /api/v1/me/`, and `PATCH /api/v1/me/` for `display_name`. Show `email` and `account_type` read-only because the current API response does not expose `phone_number`.

- [ ] **Step 6: Route auth pages and update nav**

Add routes:

```text
/connexion
/inscription
/profil
```

Update `Navbar`:

- anonymous: `Connexion`, `S'inscrire`;
- authenticated: user initials, `Bibliotheque`, `Profil`, logout icon.

- [ ] **Step 7: Run tests and build**

Run from `frontend/`:

```powershell
npm run test -- src/auth/tests/auth.test.tsx
npm run build
```

Expected: tests pass and build succeeds.

- [ ] **Step 8: Commit**

```powershell
git add frontend/src/auth frontend/src/routes frontend/src/components/layout/Navbar.tsx frontend/src/router.tsx
git commit -m "feat: add frontend auth session"
```

---

### Task 5: Catalog, Search, Domains, And Document Detail

**Files:**
- Create: `frontend/src/components/catalog/DocumentCard.tsx`
- Create: `frontend/src/components/catalog/DocumentCover.tsx`
- Create: `frontend/src/components/catalog/DomainBadge.tsx`
- Create: `frontend/src/components/catalog/SearchResultCard.tsx`
- Create: `frontend/src/components/catalog/CatalogFilters.tsx`
- Create: `frontend/src/components/catalog/PaginationControls.tsx`
- Create: `frontend/src/features/catalog/hooks.ts`
- Create: `frontend/src/routes/CatalogPage.tsx`
- Create: `frontend/src/routes/RecherchePage.tsx`
- Create: `frontend/src/routes/DomainesPage.tsx`
- Create: `frontend/src/routes/DomainDetailPage.tsx`
- Create: `frontend/src/routes/DocumentDetailPage.tsx`
- Create: `frontend/src/tests/catalog-routes.test.tsx`
- Modify: `frontend/src/router.tsx`
- Modify: `frontend/src/routes/HomePage.tsx`

**Interfaces:**
- Consumes API catalog/search functions from Task 3.
- Consumes visual components from Task 2.
- Produces public catalog routes and document detail route.

- [ ] **Step 1: Write failing catalog component tests**

Create `frontend/src/tests/catalog-routes.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { DocumentCard } from "@/components/catalog/DocumentCard";
import type { DocumentMetadata } from "@/api/types";

const document: DocumentMetadata = {
  id: 10,
  slug: "droit-public",
  title: "Droit public gabonais",
  abstract: "Resume public.",
  language_code: "fr",
  publication_year: 2026,
  document_type: "open_resource",
  access_model: "free",
  domain: { id: 1, name: "Droit", slug: "droit" },
  authors: [{ id: 1, display_name: "Auteur Test", role: "author" }],
  owner: null,
  page_count: 12,
  cover: null,
  access: { can_read: true, access_model: "free", reason: "free" }
};

describe("DocumentCard", () => {
  it("renders public metadata and a read CTA without download links", () => {
    render(<DocumentCard document={document} />);

    expect(screen.getByText("Droit public gabonais")).toBeInTheDocument();
    expect(screen.getByText("Droit")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Lire/i })).toHaveAttribute(
      "href",
      "/lecture/10"
    );
    expect(screen.queryByText(/Telecharger/i)).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test red**

Run from `frontend/`:

```powershell
npm run test -- src/tests/catalog-routes.test.tsx
```

Expected: FAIL because `DocumentCard` does not exist.

- [ ] **Step 3: Implement maquette-derived catalog components**

Implement:

- `DomainBadge`: rounded domain pill with colored dot.
- `DocumentCover`: image if `document.cover`, otherwise gradient fallback by domain/type.
- `DocumentCard`: maquette card language with cover, `gabon-stripe`, domain badge, language chip, year, authors, access status, bottom gold hover rule.
- `SearchResultCard`: compact metadata card for `/api/v1/search/` results, linking to `/documents/:id` without guessing read access.
- `CatalogFilters`: query/domain/language/access/year controls.
- `PaginationControls`: previous/next/page-size controls using API `count`, `next`, `previous`.

Rules:

- Render no download button.
- Link document titles to `/documents/:id`.
- Link read CTA to `/lecture/:id` only when `access.can_read` is true.
- Show `Connexion requise` for `authentication_required`.
- Show `Acces requis` for `entitlement_required`.

Use these props and CTA helpers:

```tsx
import type { DocumentMetadata, SearchResult } from "@/api/types";

export function documentReadLabel(document: DocumentMetadata) {
  if (document.access.can_read) return "Lire";
  if (document.access.reason === "authentication_required") return "Connexion requise";
  if (document.access.reason === "entitlement_required") return "Acces requis";
  return "Indisponible";
}

export function DocumentCard({ document }: { document: DocumentMetadata }) {
  const readLabel = documentReadLabel(document);
  return (
    <article className="group overflow-hidden rounded-2xl border border-border bg-white shadow-editorial">
      <div className="h-1 gabon-stripe" aria-hidden="true" />
      <DocumentCover document={document} />
      <div className="p-5">
        {document.domain ? <DomainBadge domain={document.domain} /> : null}
        <a href={`/documents/${document.id}`} className="mt-3 block font-display text-xl text-[var(--navy)]">
          {document.title}
        </a>
        <p className="mt-2 line-clamp-3 text-sm text-muted-foreground">{document.abstract}</p>
        {document.access.can_read ? (
          <a href={`/lecture/${document.id}`} className="mt-4 inline-flex text-sm font-semibold text-[var(--navy)]">
            {readLabel}
          </a>
        ) : (
          <span className="mt-4 inline-flex text-sm font-semibold text-muted-foreground">{readLabel}</span>
        )}
      </div>
    </article>
  );
}

export function SearchResultCard({ result }: { result: SearchResult }) {
  return (
    <article className="rounded-2xl border border-border bg-white p-5 shadow-editorial">
      <a href={`/documents/${result.id}`} className="font-display text-xl text-[var(--navy)]">
        {result.title}
      </a>
      <p className="mt-2 text-sm text-muted-foreground">{result.abstract}</p>
      <p className="mt-3 text-xs font-semibold uppercase tracking-[0.14em] text-[var(--green)]">
        {result.domain?.name ?? "Domaine non renseigne"}
      </p>
    </article>
  );
}
```

- [ ] **Step 4: Implement catalog query hooks**

Create `frontend/src/features/catalog/hooks.ts`:

```ts
import { useQuery } from "@tanstack/react-query";
import { getDocument, listDocuments, listDomains, searchDocuments } from "@/api/catalog";
import { useAuth } from "@/auth/AuthProvider";

export function useDocuments(params: Record<string, string | number | undefined>) {
  const { tokens } = useAuth();
  return useQuery({
    queryKey: ["documents", params, tokens?.access ?? null],
    queryFn: () => listDocuments(params, tokens?.access)
  });
}

export function useDocument(documentId: string | number) {
  const { tokens } = useAuth();
  return useQuery({
    queryKey: ["document", documentId, tokens?.access ?? null],
    queryFn: () => getDocument(documentId, tokens?.access)
  });
}

export function useDomains() {
  return useQuery({
    queryKey: ["domains"],
    queryFn: () => listDomains()
  });
}

export function useSearch(params: Record<string, string | number | undefined>) {
  const { tokens } = useAuth();
  return useQuery({
    queryKey: ["search", params, tokens?.access ?? null],
    queryFn: () => searchDocuments(params, tokens?.access)
  });
}
```

- [ ] **Step 5: Implement routes**

Routes:

- `/catalogue`: public document grid from `useDocuments({ page, page_size })` plus pagination; the filter panel submits to `/recherche` because document-list filtering is not in the current API contract.
- `/recherche`: search input and `SearchResultCard` results from `/api/v1/search/` using `q`, `domain`, `language`, `access`, `year`, `page`, and `page_size`.
- `/domaines`: domain card grid using API domains.
- `/domaines/:slug`: domain-filtered `SearchResultCard` grid from `useSearch({ domain: slug, page, page_size })`.
- `/documents/:id`: maquette-style detail page with cover-left/content-right hero.

`DocumentDetailPage` CTA behavior:

```ts
if (document.access.can_read) show "Lire maintenant";
if (document.access.reason === "authentication_required") show "Se connecter pour lire";
if (document.access.reason === "entitlement_required") show "Acces requis";
```

- [ ] **Step 6: Update home**

Update home to preserve maquette visual language:

- strong hero;
- visible search;
- domain bento;
- featured documents from `listDocuments({ page_size: 4 })`;
- no "100 % gratuit" claim.

- [ ] **Step 7: Run tests and build**

Run from `frontend/`:

```powershell
npm run test -- src/tests/catalog-routes.test.tsx
npm run build
```

Expected: tests pass and build succeeds.

- [ ] **Step 8: Commit**

```powershell
git add frontend/src/components/catalog frontend/src/features/catalog frontend/src/routes frontend/src/router.tsx
git commit -m "feat: add frontend catalog discovery"
```

---

### Task 6: Secure Reader Route

**Files:**
- Create: `frontend/src/components/reader/ReaderControls.tsx`
- Create: `frontend/src/components/reader/ReaderPage.tsx`
- Create: `frontend/src/features/reader/hooks.ts`
- Create: `frontend/src/routes/LecturePage.tsx`
- Create: `frontend/src/tests/reader-route.test.tsx`
- Modify: `frontend/src/router.tsx`

**Interfaces:**
- Consumes reader API functions from Task 3.
- Produces `/lecture/:documentId`.

- [ ] **Step 1: Write failing reader tests**

Create `frontend/src/tests/reader-route.test.tsx`:

```tsx
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
```

- [ ] **Step 2: Run tests red**

Run from `frontend/`:

```powershell
npm run test -- src/tests/reader-route.test.tsx
```

Expected: FAIL because reader components do not exist.

- [ ] **Step 3: Implement reader components**

`ReaderControls` props:

```ts
interface ReaderControlsProps {
  pageNumber: number;
  pageCount: number;
  onPrevious(): void;
  onNext(): void;
}
```

Disable previous on page `1`; disable next on `pageNumber === pageCount`.

`ReaderPage` props:

```ts
import type { ReaderPage as ReaderPagePayload } from "@/api/types";

interface ReaderPageProps {
  title: string;
  page: ReaderPagePayload;
}
```

Render page text in a calm reading surface with maquette typography. Do not render download controls.

- [ ] **Step 4: Implement reader hooks**

Create `frontend/src/features/reader/hooks.ts`:

```ts
import { useMutation, useQuery } from "@tanstack/react-query";

import {
  closeReaderSession,
  createReaderSession,
  getReaderPage
} from "@/api/reader";
import { useAuth } from "@/auth/AuthProvider";

export function useCreateReaderSession() {
  const { tokens } = useAuth();
  return useMutation({
    mutationFn: (documentId: number | string) =>
      createReaderSession(documentId, tokens?.access)
  });
}

export function useReaderPage(sessionKey: string | null, pageNumber: number) {
  const { tokens } = useAuth();
  return useQuery({
    queryKey: ["reader-page", sessionKey, pageNumber, tokens?.access ?? null],
    queryFn: () => getReaderPage(sessionKey as string, pageNumber, tokens?.access),
    enabled: Boolean(sessionKey)
  });
}

export function useCloseReaderSession() {
  const { tokens } = useAuth();
  return useMutation({
    mutationFn: (sessionKey: string) => closeReaderSession(sessionKey, tokens?.access)
  });
}
```

Anonymous free reading must not require auth; the token argument stays `undefined` when no user is logged in.

- [ ] **Step 5: Implement `/lecture/:documentId`**

Flow:

1. Create reader session for `documentId`.
2. Store `session_key` in component state.
3. Fetch `getDocument(documentId)` for title and public metadata.
4. Fetch page `1`.
5. Previous/next changes page number and fetches that page.
6. Close session on explicit return or component unmount when a session exists.

Error mapping:

- 401: show login CTA;
- 403: show entitlement-required state;
- 404: show generic not-found state;
- network error: show retry.

- [ ] **Step 6: Run tests and build**

Run from `frontend/`:

```powershell
npm run test -- src/tests/reader-route.test.tsx
npm run build
```

Expected: tests pass and build succeeds.

- [ ] **Step 7: Commit**

```powershell
git add frontend/src/components/reader frontend/src/features/reader frontend/src/routes/LecturePage.tsx frontend/src/router.tsx frontend/src/tests/reader-route.test.tsx
git commit -m "feat: add secure reader frontend"
```

---

### Task 7: Personal Library And Profile

**Files:**
- Create: `frontend/src/features/library/hooks.ts`
- Create: `frontend/src/routes/BibliothequePage.tsx`
- Modify: `frontend/src/routes/ProfilPage.tsx`
- Modify: `frontend/src/components/catalog/DocumentCard.tsx`
- Modify: `frontend/src/router.tsx`
- Test: `frontend/src/tests/library-route.test.tsx`

**Interfaces:**
- Consumes library API functions from Task 3.
- Consumes auth route guard from Task 4.
- Produces `/bibliotheque` and favorite/progress UI.

- [ ] **Step 1: Write failing library tests**

Create `frontend/src/tests/library-route.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { LibrarySection } from "@/routes/BibliothequePage";

describe("LibrarySection", () => {
  it("renders favorites and progress without reading logs", () => {
    render(
      <LibrarySection
        favorites={[
          {
            document: {
              id: 1,
              slug: "doc",
              title: "Document favori",
              abstract: "Resume",
              language_code: "fr",
              publication_year: 2026,
              document_type: "open_resource",
              access_model: "free",
              domain: { id: 1, name: "Droit", slug: "droit" },
              authors: [],
              owner: null,
              page_count: 3,
              cover: null,
              access: { can_read: true, access_model: "free", reason: "free" }
            },
            created_at: "2026-07-30T10:00:00Z"
          }
        ]}
        progress={[]}
      />
    );

    expect(screen.getByText("Document favori")).toBeInTheDocument();
    expect(screen.queryByText(/historique page par page/i)).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run tests red**

Run from `frontend/`:

```powershell
npm run test -- src/tests/library-route.test.tsx
```

Expected: FAIL because library route exports do not exist.

- [ ] **Step 3: Implement library hooks**

Create `frontend/src/features/library/hooks.ts`:

```ts
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  addFavorite,
  listFavorites,
  listReadingProgress,
  removeFavorite,
  updateReadingProgress
} from "@/api/library";
import { useAuth } from "@/auth/AuthProvider";

function requireAccessToken(access?: string | null) {
  if (!access) throw new Error("Authentication is required.");
  return access;
}

export function useFavorites() {
  const { tokens } = useAuth();
  return useQuery({
    queryKey: ["favorites", tokens?.access ?? null],
    queryFn: () => listFavorites(requireAccessToken(tokens?.access)),
    enabled: Boolean(tokens?.access)
  });
}

export function useAddFavorite() {
  const { tokens } = useAuth();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (documentId: number | string) =>
      addFavorite(requireAccessToken(tokens?.access), documentId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["favorites"] })
  });
}

export function useRemoveFavorite() {
  const { tokens } = useAuth();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (documentId: number | string) =>
      removeFavorite(requireAccessToken(tokens?.access), documentId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["favorites"] })
  });
}

export function useReadingProgress() {
  const { tokens } = useAuth();
  return useQuery({
    queryKey: ["reading-progress", tokens?.access ?? null],
    queryFn: () => listReadingProgress(requireAccessToken(tokens?.access)),
    enabled: Boolean(tokens?.access)
  });
}

export function useUpdateReadingProgress() {
  const { tokens } = useAuth();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { documentId: number | string; lastPageNumber: number }) =>
      updateReadingProgress(
        requireAccessToken(tokens?.access),
        input.documentId,
        input.lastPageNumber
      ),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["reading-progress"] })
  });
}
```

- [ ] **Step 4: Implement `/bibliotheque`**

Use `RequireAuth`. Render maquette dashboard-inspired sections:

- hero/header with user name;
- stats cards for favorites and in-progress documents;
- "Reprendre la lecture" from reading progress;
- "Mes favoris" from favorites.

Do not show detailed page access logs, download history, or fake demo data.

- [ ] **Step 5: Add favorite action to document cards**

Add an optional favorite button to `DocumentCard` when authenticated:

- heart outline if not known favorite;
- filled heart if favorite;
- call add/remove mutations;
- keep the main card click target accessible.

If favorite state is unknown on catalog pages, hide the button rather than guessing.

- [ ] **Step 6: Complete profile**

`ProfilPage` must:

- require auth;
- show email and account type read-only;
- allow `display_name` updates only;
- show normalized API field errors.

- [ ] **Step 7: Run tests and build**

Run from `frontend/`:

```powershell
npm run test -- src/tests/library-route.test.tsx src/auth/tests/auth.test.tsx
npm run build
```

Expected: tests pass and build succeeds.

- [ ] **Step 8: Commit**

```powershell
git add frontend/src/features/library frontend/src/routes/BibliothequePage.tsx frontend/src/routes/ProfilPage.tsx frontend/src/components/catalog/DocumentCard.tsx frontend/src/router.tsx frontend/src/tests/library-route.test.tsx
git commit -m "feat: add personal library frontend"
```

---

### Task 8: Frontend Verification, Documentation, And Local Run

**Files:**
- Create: `frontend/README.md`
- Modify: `AGENTS.md`
- Modify: `frontend/package.json`
- Modify: `frontend/src/router.tsx`

**Interfaces:**
- Consumes all frontend routes and tests.
- Produces contributor commands and final runnable app.

- [ ] **Step 1: Write or update frontend README**

Create `frontend/README.md`:

```markdown
# BiblioGABON Frontend

Reader-facing web frontend for BiblioGABON.

## Commands

- `npm install`: install frontend dependencies.
- `npm run dev`: start the Vite development server.
- `npm run build`: type-check and build production assets.
- `npm run lint`: run ESLint.
- `npm run test`: run Vitest tests.

## Configuration

Copy `.env.example` to `.env.local` and set:

```text
VITE_API_BASE_URL=http://127.0.0.1:8000
```

The frontend consumes the Django API under `/api/v1/`.
```

- [ ] **Step 2: Update root contributor guide**

Update `AGENTS.md` command section with:

```markdown
- `cd frontend && npm install`: install frontend dependencies.
- `cd frontend && npm run dev`: start the reader-facing web app.
- `cd frontend && npm run build`: type-check and build the frontend.
- `cd frontend && npm run test`: run frontend tests.
```

Do not rewrite unrelated AGENTS sections.

- [ ] **Step 3: Add not-found route**

Add a maquette-style not-found component to `router.tsx`:

```tsx
function NotFoundPage() {
  return (
    <SiteLayout>
      <EmptyState
        title="Page introuvable"
        description="Cette adresse ne correspond a aucune page publique de BiblioGABON."
      />
    </SiteLayout>
  );
}
```

- [ ] **Step 4: Run full frontend verification**

Run from `frontend/`:

```powershell
npm run lint
npm run test
npm run build
```

Expected: all commands exit 0.

- [ ] **Step 5: Run backend smoke verification**

Run from `backend/`:

```powershell
.\.venv\Scripts\python.exe -m pytest api/v1/tests -q
```

Expected: API V1 tests pass.

- [ ] **Step 6: Start local dev server**

Run from `frontend/`:

```powershell
npm run dev
```

Expected: Vite prints a local URL such as `http://127.0.0.1:5173/`. Leave the server running only if the user wants to try it immediately.

- [ ] **Step 7: Commit**

```powershell
git add frontend AGENTS.md
git commit -m "docs: verify frontend web app"
```

---

## Final Verification

After all tasks complete, run from `frontend/`:

```powershell
npm run lint
npm run test
npm run build
```

Run from `backend/`:

```powershell
.\.venv\Scripts\python.exe -m pytest api/v1/tests -q
```

Run from repo root:

```powershell
git diff --check
```

Expected: every command exits 0.
