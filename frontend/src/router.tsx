import {
  Outlet,
  createRootRoute,
  createRoute,
  createRouter
} from "@tanstack/react-router";

import { AuthProvider } from "@/auth/AuthProvider";
import { HomePage } from "@/routes/HomePage";
import { ConnexionPage } from "@/routes/ConnexionPage";
import { InscriptionPage } from "@/routes/InscriptionPage";
import { ProfilPage } from "@/routes/ProfilPage";

const rootRoute = createRootRoute({
  component: () => <AuthProvider><Outlet /></AuthProvider>
});

const homeRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  component: HomePage
});

const connexionRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/connexion",
  validateSearch: (search: Record<string, unknown>) => ({
    next: typeof search.next === "string" ? search.next : "/"
  }),
  component: ConnexionPage
});

const inscriptionRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/inscription",
  component: InscriptionPage
});

const profilRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/profil",
  component: ProfilPage
});

const routeTree = rootRoute.addChildren([homeRoute, connexionRoute, inscriptionRoute, profilRoute]);

export function createAppRouter(
  options: Partial<Parameters<typeof createRouter>[0]> = {}
) {
  return createRouter({
    routeTree,
    defaultPreload: "intent",
    scrollRestoration: true,
    defaultPendingMs: 0,
    ...options
  });
}

export type AppRouter = ReturnType<typeof createAppRouter>;

declare module "@tanstack/react-router" {
  interface Register {
    router: AppRouter;
  }
}
