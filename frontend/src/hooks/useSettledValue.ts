import { useEffect, useState } from "react";

/**
 * La valeur une fois qu'elle a cessé de bouger.
 *
 * Elle sert à distinguer *traverser* de *s'arrêter*. La progression de lecture
 * s'écrivait à chaque page vue — douze pages parcourues au clavier
 * déclenchaient seize écritures — et ce n'était pas qu'une dépense : reprendre
 * une lecture à la dernière page *aperçue* en cherchant un passage ramène le
 * lecteur là où il n'a jamais lu.
 *
 * `null` tant que rien ne s'est posé : l'absence de valeur stable est un état,
 * pas la valeur initiale. Renvoyer celle-ci ferait enregistrer, à l'ouverture,
 * une page que personne n'a encore regardée.
 */
export function useSettledValue<T>(value: T, delay: number): T | null {
  const [settled, setSettled] = useState<T | null>(null);

  useEffect(() => {
    // L'annulation est le mécanisme même : sans elle, chaque valeur traversée
    // finit par se poser à son tour, avec un simple retard.
    const timer = window.setTimeout(() => setSettled(value), delay);
    return () => window.clearTimeout(timer);
  }, [delay, value]);

  return settled;
}
