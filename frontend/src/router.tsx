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
import { CatalogPage } from "@/routes/CatalogPage";
import { RecherchePage } from "@/routes/RecherchePage";
import { DomainesPage } from "@/routes/DomainesPage";
import { DomainDetailPage } from "@/routes/DomainDetailPage";
import { DocumentDetailPage } from "@/routes/DocumentDetailPage";
import { LecturePage } from "@/routes/LecturePage";

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

const catalogueRoute = createRoute({ getParentRoute: () => rootRoute, path: "/catalogue", component: CatalogPage });
const rechercheRoute = createRoute({ getParentRoute: () => rootRoute, path: "/recherche", component: RecherchePage });
const domainesRoute = createRoute({ getParentRoute: () => rootRoute, path: "/domaines", component: DomainesPage });
const domainDetailRoute = createRoute({ getParentRoute: () => rootRoute, path: "/domaines/$slug", component: DomainDetailPage });
const documentDetailRoute = createRoute({ getParentRoute: () => rootRoute, path: "/documents/$id", component: DocumentDetailPage });
const lectureRoute = createRoute({ getParentRoute: () => rootRoute, path: "/lecture/$documentId", component: LecturePage });

const routeTree = rootRoute.addChildren([homeRoute, connexionRoute, inscriptionRoute, profilRoute, catalogueRoute, rechercheRoute, domainesRoute, domainDetailRoute, documentDetailRoute, lectureRoute]);

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
