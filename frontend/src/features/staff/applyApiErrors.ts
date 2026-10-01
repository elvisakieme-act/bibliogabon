import type { FieldErrors, FieldValues, Path, UseFormSetError } from "react-hook-form";

import { ApiError } from "@/api/client";

const UNEXPECTED_MESSAGE =
  "Une erreur inattendue s'est produite. Réessayez, et signalez-le si cela persiste.";

/**
 * Pont entre l'enveloppe d'erreur de l'API et react-hook-form.
 *
 * Renvoie le message de niveau formulaire, et place sur leurs champs les
 * erreurs que le serveur a nommees. Deux precautions que `setError` seul ne
 * donne pas :
 *
 * - une erreur portant sur un champ que le formulaire ne possede pas serait
 *   silencieusement avalee — `setError` l'enregistre, mais rien ne l'affiche.
 *   Elle rejoint donc le message de formulaire, pour que l'utilisateur voie
 *   au moins pourquoi son envoi a ete refuse ;
 * - une exception qui n'est pas un refus serveur ne doit pas fuir son texte
 *   dans l'interface : « cannot read properties of undefined » n'aide
 *   personne et expose l'implementation.
 */
export function applyApiErrors<TValues extends FieldValues>(
  error: unknown,
  {
    setError,
    fields
  }: {
    setError: UseFormSetError<TValues>;
    fields: readonly string[];
  }
): string {
  if (!(error instanceof ApiError)) {
    return UNEXPECTED_MESSAGE;
  }

  const owned = new Set(fields);
  const orphanMessages: string[] = [];
  let placed = 0;

  for (const [field, messages] of Object.entries(error.fieldErrors ?? {})) {
    const text = messages.join(" ");
    if (!text) continue;
    if (!owned.has(field)) {
      orphanMessages.push(text);
      continue;
    }
    setError(
      field as Path<TValues>,
      { type: "server", message: text },
      // Le focus ne va qu'au premier : deplacer le focus plusieurs fois
      // ferait sauter la page et laisserait l'utilisateur sur le dernier
      // champ plutot que sur le premier probleme.
      { shouldFocus: placed === 0 }
    );
    placed += 1;
  }

  return [error.message, ...orphanMessages].filter(Boolean).join(" ");
}

/**
 * Traduit les erreurs de react-hook-form vers la forme attendue par
 * `components/ui/FieldErrors`, pour que le contrat d'accessibilite soit
 * ecrit une seule fois et identique des deux cotes de l'application.
 */
export function toFieldErrors(errors: FieldErrors): Record<string, string[]> {
  const result: Record<string, string[]> = {};
  for (const [field, entry] of Object.entries(errors)) {
    const message = entry?.message;
    if (typeof message === "string" && message) {
      result[field] = [message];
    }
  }
  return result;
}
