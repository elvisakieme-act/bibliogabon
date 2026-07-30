import {
  Outlet,
  createRootRoute,
  createRoute,
  createRouter
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
