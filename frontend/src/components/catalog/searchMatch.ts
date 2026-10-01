/**
 * Pourquoi ce résultat est là.
 *
 * Le serveur nomme les champs qui ont répondu ; l'écran les dit au lecteur.
 * Sans cela, un document dont le mot cherché n'apparaît qu'une fois au détour
 * d'une page avait exactement l'allure d'une correspondance de titre — et la
 * liste semblait ramener n'importe quoi.
 *
 * Seule la provenance **la plus forte** est annoncée : égrener « titre,
 * auteurs, résumé, texte » sur chaque ligne ferait du bruit là où une phrase
 * suffit. L'ordre suit celui du barème du serveur.
 */
const ORDRE: Array<[string, string]> = [
  ["title", "Le titre correspond"],
  ["authors", "Un auteur correspond"],
  ["domain", "Le domaine correspond"],
  ["type", "La nature du document correspond"],
  ["abstract", "Le résumé correspond"],
  ["text", "Trouvé dans le texte du document"]
];

export function searchMatchLabel(matchedIn: string[] | undefined): string | null {
  // Tolérant à l'absence : un frontend déployé devant un serveur plus ancien
  // est une situation ordinaire, et une page de résultats entière ne doit pas
  // disparaître parce qu'un champ est arrivé après elle. Le contrat reste tenu
  // côté serveur par le test de parité des types.
  if (!matchedIn || matchedIn.length === 0) return null;
  for (const [champ, phrase] of ORDRE) {
    if (matchedIn.includes(champ)) return phrase;
  }
  return null;
}

/**
 * Le résultat ne doit-il sa présence qu'au texte du document ?
 *
 * C'est le cas qui mérite d'être distingué : la pertinence y est faible, et
 * l'afficher comme les autres faisait croire à une recherche qui ratisse.
 */
export function matchedOnlyInText(matchedIn: string[] | undefined): boolean {
  return matchedIn?.length === 1 && matchedIn[0] === "text";
}
