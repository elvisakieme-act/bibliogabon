import { ApiError, apiBaseUrl } from "@/api/client";

/**
 * Manifeste IIIF de la session de lecture.
 *
 * Une requête donne tout ce qu'il faut pour ouvrir le document : le nombre de
 * pages, les dimensions de chacune, et la description complète de son service
 * d'images.
 *
 * C'est ce qui rend l'architecture tenable. Sans lui, un visualiseur qui met
 * 157 pages en page lit 157 `info.json` à l'ouverture — donc demande 157 fois
 * l'autorisation, et fait journaliser le document entier comme lu avant que
 * le lecteur ait tourné une page.
 */

export interface IiifImageService {
  id: string;
  type: string;
  profile: string;
  width: number;
  height: number;
  tiles: Array<{ width: number; scaleFactors: number[] }>;
  sizes: Array<{ width: number; height: number }>;
}

export interface IiifCanvas {
  id: string;
  width: number;
  height: number;
  items: Array<{
    items: Array<{ body: { service: IiifImageService[] } }>;
  }>;
}

export interface IiifManifest {
  id: string;
  label: Record<string, string[]>;
  items: IiifCanvas[];
}

export async function fetchReaderManifest(
  sessionKey: string,
  token?: string | null
): Promise<IiifManifest> {
  const response = await fetch(
    `${apiBaseUrl()}/api/v1/reader/sessions/${sessionKey}/manifest`,
    { headers: token ? { Authorization: `Bearer ${token}` } : {} }
  );
  if (!response.ok) {
    throw new ApiError(
      response.status,
      "manifest_unavailable",
      "Ce document n'a pas pu être ouvert."
    );
  }
  return response.json();
}

/**
 * Numéro de page d'un canevas.
 *
 * Le manifeste omet les pages non tuilées plutôt que d'inventer leurs
 * dimensions : la position dans la liste n'est donc pas le numéro de page, et
 * s'en servir désignerait la mauvaise page dès qu'un rendu a échoué.
 */
export function canvasPageNumber(canvas: IiifCanvas): number {
  return Number(canvas.id.split("/").pop());
}

/** Service d'images d'un canevas, tel qu'OpenSeadragon l'attend. */
export function canvasTileSource(canvas: IiifCanvas) {
  const service = canvas.items[0].items[0].body.service[0];
  return { "@context": "http://iiif.io/api/image/3/context.json", ...service };
}
