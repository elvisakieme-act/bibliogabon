import {
  Outlet,
  createRootRoute,
  createRoute,
  createRouter,
  lazyRouteComponent
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
import { BibliothequePage } from "@/routes/BibliothequePage";
import { NotFoundPage } from "@/routes/NotFoundPage";

const rootRoute = createRootRoute({
  component: () => (
    <AuthProvider>
      <Outlet />
    </AuthProvider>
  ),
  notFoundComponent: NotFoundPage
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

const bibliothequeRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/bibliotheque",
  component: BibliothequePage
});

const catalogueRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/catalogue",
  component: CatalogPage
});
const rechercheRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/recherche",
  component: RecherchePage
});
const domainesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/domaines",
  component: DomainesPage
});
const domainDetailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/domaines/$slug",
  component: DomainDetailPage
});
const documentDetailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/documents/$id",
  component: DocumentDetailPage
});
const lectureRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/lecture/$documentId",
  component: LecturePage
});

// L'espace de gestion est la premiere partie chargee a la demande : un
// lecteur ne doit pas telecharger les ecrans de depot. `staff-bundle.test`
// verifie que le fragment d'entree n'en contient rien, sinon un import
// statique ajoute plus tard annulerait la coupure sans que rien ne le dise.
const gestionRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/gestion",
  component: lazyRouteComponent(() => import("@/routes/gestion/GestionLayout"), "GestionLayout")
});
const gestionIndexRoute = createRoute({
  getParentRoute: () => gestionRoute,
  path: "/",
  component: lazyRouteComponent(() => import("@/routes/gestion/DashboardPage"), "DashboardPage")
});
const gestionOrganizationsRoute = createRoute({
  getParentRoute: () => gestionRoute,
  path: "organisations",
  component: lazyRouteComponent(
    () => import("@/routes/gestion/OrganizationsPage"),
    "OrganizationsPage"
  )
});
const gestionOrganizationDetailRoute = createRoute({
  getParentRoute: () => gestionRoute,
  path: "organisations/$organizationId",
  component: lazyRouteComponent(
    () => import("@/routes/gestion/OrganizationDetailPage"),
    "OrganizationDetailPage"
  )
});
const gestionReviewsRoute = createRoute({
  getParentRoute: () => gestionRoute,
  path: "revues",
  component: lazyRouteComponent(() => import("@/routes/gestion/ReviewsPage"), "ReviewsPage")
});
const gestionReviewDetailRoute = createRoute({
  getParentRoute: () => gestionRoute,
  path: "revues/$reviewId",
  component: lazyRouteComponent(
    () => import("@/routes/gestion/ReviewDetailPage"),
    "ReviewDetailPage"
  )
});
const gestionDocumentCreateRoute = createRoute({
  getParentRoute: () => gestionRoute,
  // Statique avant dynamique : « nouveau » ne doit jamais etre lu comme un
  // identifiant de document.
  path: "documents/nouveau",
  component: lazyRouteComponent(
    () => import("@/routes/gestion/DocumentCreatePage"),
    "DocumentCreatePage"
  )
});
const gestionDocumentDetailRoute = createRoute({
  getParentRoute: () => gestionRoute,
  path: "documents/$documentId",
  component: lazyRouteComponent(
    () => import("@/routes/gestion/DocumentDetailPage"),
    "DocumentDetailPage"
  )
});
const gestionDocumentsRoute = createRoute({
  getParentRoute: () => gestionRoute,
  path: "documents",
  component: lazyRouteComponent(() => import("@/routes/gestion/DocumentsPage"), "DocumentsPage")
});

const routeTree = rootRoute.addChildren([
  homeRoute,
  connexionRoute,
  inscriptionRoute,
  profilRoute,
  bibliothequeRoute,
  catalogueRoute,
  rechercheRoute,
  domainesRoute,
  domainDetailRoute,
  documentDetailRoute,
  lectureRoute,
  gestionRoute.addChildren([
    gestionIndexRoute,
    gestionDocumentsRoute,
    gestionDocumentCreateRoute,
    gestionDocumentDetailRoute,
    gestionReviewsRoute,
    gestionReviewDetailRoute,
    gestionOrganizationsRoute,
    gestionOrganizationDetailRoute
  ])
]);

export function createAppRouter(options: Partial<Parameters<typeof createRouter>[0]> = {}) {
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
