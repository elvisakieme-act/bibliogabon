import type { DocumentMetadata } from "@/api/types";

/**
 * La référence à recopier dans une bibliographie.
 *
 * Une bibliothèque académique qui ne dit pas comment la citer oblige chaque
 * lecteur à reconstituer la référence de mémoire — et c'est ainsi qu'un
 * mémoire gabonais finit cité sans son établissement.
 *
 * Rien n'est inventé : chaque élément absent est **omis**, jamais remplacé par
 * un « s.d. » ou un « anonyme » qui aurait l'air d'une donnée. Les noms sont
 * recopiés tels qu'ils sont enregistrés, sans tenter de deviner lequel est le
 * patronyme : « Levis ANDONGUI » ne se réordonne pas sans risquer de se
 * tromper, et une référence fausse est pire qu'une référence plate.
 */
export function documentCitation(document: DocumentMetadata, url: string): string {
  const parties: string[] = [];

  const auteurs = document.authors.map((auteur) => auteur.display_name).filter(Boolean);
  if (auteurs.length > 0) parties.push(`${auteurs.join(" ; ")}.`);

  parties.push(`${document.title}.`);

  // Nature, établissement et année forment une seule mention, séparée par des
  // virgules : c'est la forme d'une notice, et elle se lit même amputée.
  const mention = [
    document.document_type?.name,
    document.owner,
    document.publication_year?.toString()
  ].filter((element): element is string => Boolean(element));
  if (mention.length > 0) parties.push(`${mention.join(", ")}.`);

  parties.push("BiblioGABON.");
  parties.push(`Disponible sur : ${url}`);

  return parties.join(" ");
}
