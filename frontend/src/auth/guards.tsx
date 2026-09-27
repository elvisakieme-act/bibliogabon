import { Navigate, useRouter } from "@tanstack/react-router";

import type { AccountType } from "@/api/types";
import { useAuth } from "@/auth/useAuth";
import { BACK_OFFICE_ACCOUNT_TYPES } from "@/auth/roles";
import { EmptyState } from "@/components/ui/EmptyState";
import { Skeleton } from "@/components/ui/Skeleton";

// La cible de retour vient du routeur, pas de `window.location` : les deux
// coincident sous un historique navigateur, mais pas sous un historique
// memoire ni avec un basepath, ou la cible devenait « / ».
//
// Lue de facon reactive, elle s'imbriquait : des la premiere redirection le
// garde se re-affichait avec la nouvelle location — /connexion?next=... —
// et redirigeait a nouveau en l'emboitant, l'URL doublant a chaque tour
// jusqu'a « Maximum update depth exceeded ». Deux precautions, chacune pour
// une raison distincte : `useRouter()` ne s'abonne a rien, et la page de
// connexion n'est jamais sa propre cible.
const SIGN_IN_PATH = "/connexion";

function useSignInRedirect() {
  const router = useRouter();
  const { pathname, searchStr } = router.state.location;

  if (pathname === SIGN_IN_PATH) {
    return null;
  }
  return <Navigate to={SIGN_IN_PATH} search={{ next: `${pathname}${searchStr}` }} />;
}

export function RequireAuth({ children }: { children: React.ReactNode }) {
  const auth = useAuth();
  const signInRedirect = useSignInRedirect();

  if (auth.isHydrating) {
    return <Skeleton label="Chargement de la session" />;
  }
  if (!auth.user) {
    return signInRedirect;
  }
  return children;
}

export function RequireRole({
  allow = BACK_OFFICE_ACCOUNT_TYPES,
  children
}: {
  allow?: readonly AccountType[];
  children: React.ReactNode;
}) {
  const auth = useAuth();
  const signInRedirect = useSignInRedirect();

  if (auth.isHydrating) {
    return <Skeleton label="Chargement de la session" />;
  }
  if (!auth.user) {
    return signInRedirect;
  }
  if (!allow.includes(auth.user.account_type)) {
    // Un refus, pas une redirection : renvoyer vers /connexion un compte
    // deja connecte produirait une boucle, et cacherait la vraie raison.
    return (
      <EmptyState
        title="Vous n'avez pas acces a cet espace"
        description="L'espace de gestion est reserve aux enseignants deposants, aux administrateurs d'organisation et a la moderation BiblioGABON."
      />
    );
  }
  return children;
}
