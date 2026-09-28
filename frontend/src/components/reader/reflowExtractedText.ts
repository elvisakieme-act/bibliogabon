/**
 * Rend un texte extrait lisible à l'écran.
 *
 * Un PDF ne stocke pas de paragraphes : il stocke des lignes, coupées à la
 * largeur de sa mise en page. Les afficher telles quelles fait replier le
 * texte deux fois sur un téléphone — au gabarit du document, puis à l'écran.
 *
 * Ce n'est pas une reconstruction de structure : c'est une heuristique, et
 * elle est délibérément timide. Une ligne est rattachée à la suivante
 * seulement quand elle ne se termine pas par une ponctuation de fin de phrase
 * et que la suivante ne commence pas par une majuscule ou une puce. Un titre,
 * une entrée de liste ou une ligne de tableau restent donc séparés.
 *
 * Le numéro de page isolé en fin de page est retiré : c'est un artefact de la
 * mise en page du document, pas une phrase à lire.
 */

const ENDS_A_SENTENCE = /[.!?:;»"')\]]\s*$/;
const STARTS_A_NEW_BLOCK = /^[\s]*([A-ZÀ-ÖØ-Þ0-9]|[-•–—*·])/;

export function reflowExtractedText(text: string, pageNumber?: number): string[] {
  const lines = text
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line.length > 0);

  if (pageNumber !== undefined && lines[lines.length - 1] === String(pageNumber)) {
    lines.pop();
  }

  const paragraphs: string[] = [];
  let current = "";

  for (const line of lines) {
    if (current === "") {
      current = line;
      continue;
    }
    const continues = !ENDS_A_SENTENCE.test(current) && !STARTS_A_NEW_BLOCK.test(line);
    if (continues) {
      current = `${current} ${line}`;
    } else {
      paragraphs.push(current);
      current = line;
    }
  }
  if (current !== "") paragraphs.push(current);

  return paragraphs;
}
