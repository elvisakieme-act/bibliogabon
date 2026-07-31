import { Navigate } from "@tanstack/react-router";

import { useAuth } from "@/auth/AuthProvider";
import { Skeleton } from "@/components/ui/Skeleton";

export function RequireAuth({ children }: { children: React.ReactNode }) {
  const auth = useAuth();

  if (auth.isHydrating) {
    return <Skeleton label="Chargement de la session" />;
  }
  if (!auth.user) {
    return (
      <Navigate
        to="/connexion"
        search={{ next: `${window.location.pathname}${window.location.search}` }}
      />
    );
  }
  return children;
}
