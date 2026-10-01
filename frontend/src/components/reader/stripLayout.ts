/**
 * L'arithmétique du défilement horizontal, hors du DOM pour être éprouvable.
 *
 * jsdom ne mesure rien : une page y a toujours zéro de large. Laissés dans le
 * composant, ces calculs n'auraient eu pour témoin qu'une capture d'écran — or
 * c'est précisément là qu'étaient les deux défauts du premier jet.
 */

/**
 * La hauteur d'une page, pour qu'elle tienne **entière** à l'écran.
 *
 * C'est la promesse du mode : une page, en entier, comme une diapositive. La
 * hauteur commande presque toujours — une page A4 est plus haute que large —
 * mais pas sur un téléphone tenu droit : ajustée à la seule hauteur, la page y
 * devenait plus large que l'écran, et il fallait défiler de côté à l'intérieur
 * d'une page pour en lire une ligne. C'est donc la plus contraignante des deux
 * mesures qui décide.
 *
 * `null` quand le conteneur n'est pas encore mesuré : une page de hauteur nulle
 * ne s'affiche pas, et une page sans hauteur du tout garde au moins celle que
 * la feuille de style lui donne.
 */
export function pageHeightInStrip(
  box: { width: number; height: number },
  canvas: { width: number; height: number },
  zoom: number
): number | null {
  if (box.width <= 0 || box.height <= 0 || canvas.height <= 0) return null;
  const ratio = canvas.width / canvas.height;
  // Vers le bas, et non au plus près : arrondie au plus près, une page large de
  // 342,16 px dans 342 px disponibles dépassait — et la promesse du mode est
  // qu'elle tienne.
  return Math.floor(Math.min(box.height, box.width / ratio) * zoom);
}

/**
 * L'espace à réserver au début et à la fin de la bande.
 *
 * Sans lui, la première et la dernière page ne peuvent pas venir au centre :
 * le défilement s'arrête avant. À l'ouverture d'un cours de 157 pages, la page
 * la plus centrée était alors la **deuxième**, et la barre annonçait « Page 2
 * sur 157 » d'un document qu'on venait d'ouvrir.
 *
 * Avec lui, chaque page peut occuper le milieu de l'écran : c'est ce que
 * promet un mode qui montre une page à la fois, et la page lue redevient sans
 * ambiguïté celle du centre.
 */
export function stripSidePadding(
  box: { width: number; height: number },
  canvas: { width: number; height: number } | undefined,
  zoom: number
): number {
  if (!canvas) return 0;
  const height = pageHeightInStrip(box, canvas, zoom);
  if (height === null) return 0;
  const width = height * (canvas.width / canvas.height);
  // Rien à réserver quand la page est déjà plus large que la fenêtre : elle
  // déborde, et le défilement la parcourt d'un bord à l'autre.
  return Math.max(0, Math.round((box.width - width) / 2));
}

/**
 * La page qu'on lit : celle dont le centre est le plus près du centre de la
 * fenêtre.
 *
 * Le défilement vertical retient la page la plus visible, et c'est juste
 * là-bas. Ici plusieurs pages entières tiennent côte à côte sur un écran
 * large : à égalité de visibilité, « la plus visible » retenait toujours la
 * première de la liste, donc la page de gauche — le lecteur voyait la page 7 et
 * lisait « Page 6 sur 157 ».
 */
export function centredPage(
  middle: number,
  boxes: Array<{ page: number; left: number; width: number }>
): number | null {
  let nearest: number | null = null;
  let best = Infinity;
  for (const box of boxes) {
    const distance = Math.abs(box.left + box.width / 2 - middle);
    // `<` et non `<=` : à égalité, la page la plus proche du début l'emporte,
    // puisque c'est elle qu'on lit en premier.
    if (distance < best) {
      best = distance;
      nearest = box.page;
    }
  }
  return nearest;
}
