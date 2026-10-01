/**
 * Préférences d'affichage du lecteur.
 *
 * Elles appartiennent au lecteur, pas au document : quelqu'un qui lit à 125 %
 * veut retrouver ce réglage au document suivant. Elles vivent donc dans le
 * navigateur, et leur absence n'est jamais une erreur — un navigateur en
 * navigation privée, ou qui refuse le stockage, doit ouvrir le lecteur
 * normalement.
 *
 * Deux sens de lecture, et chacun a **sa** mécanique. Trois avaient été
 * livrés en partageant la même — déplacer et agrandir une image — et aucun
 * des trois n'était servi : la molette zoomait au lieu de faire défiler, et
 * « horizontal » ne différait de « vertical » que par l'endroit où les pages
 * étaient posées. Trois noms, un comportement. Le défilement a donc son
 * conteneur qui défile, et le livre son état de double page qu'on tourne ;
 * rien n'est partagé que la surface d'une page.
 */

export const READING_MODES = ["defilement", "livre"] as const;
export type ReadingMode = (typeof READING_MODES)[number];

export const MODE_LABELS: Record<ReadingMode, string> = {
  defilement: "Défilement",
  livre: "Double page"
};

export const MODE_HINTS: Record<ReadingMode, string> = {
  defilement: "Les pages s'enchaînent : faites défiler pour avancer.",
  livre: "Deux pages côte à côte, que l'on tourne. Une seule sur un écran étroit."
};

export const DEFAULT_MODE: ReadingMode = "defilement";

/**
 * L'échelle du zoom.
 *
 * Elle descend à 50 % : s'arrêter à 75 % interdisait la vue d'ensemble d'une
 * page — repérer un tableau, situer une figure, juger la mise en page avant
 * de lire. Et elle monte à 300 %, parce qu'un plan ou une note de bas de page
 * se lisent au-delà de la taille d'origine.
 *
 * Les paliers se resserrent autour de 100 % : c'est là qu'on ajuste, alors
 * qu'aux extrémités on cherche un ordre de grandeur.
 */
export const ZOOM_STEPS = [0.5, 0.6, 0.75, 0.9, 1, 1.25, 1.5, 2, 2.5, 3] as const;
export const DEFAULT_ZOOM = 1;

const STORAGE_KEY = "bibliogabon.lecteur";

export function readZoom(): number {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULT_ZOOM;
    const parsed: unknown = JSON.parse(raw);
    const zoom = (parsed as { zoom?: unknown })?.zoom;
    // Une valeur hors de l'échelle rendrait la page illisible ou invisible :
    // on ne la reprend pas, même si elle est bien un nombre.
    return typeof zoom === "number" && ZOOM_STEPS.includes(zoom as never) ? zoom : DEFAULT_ZOOM;
  } catch {
    return DEFAULT_ZOOM;
  }
}

export function readMode(): ReadingMode {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULT_MODE;
    const mode = (JSON.parse(raw) as { mode?: unknown })?.mode;
    return READING_MODES.includes(mode as ReadingMode) ? (mode as ReadingMode) : DEFAULT_MODE;
  } catch {
    return DEFAULT_MODE;
  }
}

/**
 * Enregistre les préférences sans écraser celle qu'on ne change pas.
 *
 * Écrire `{ zoom }` seul effacerait le sens de lecture, et inversement : le
 * lecteur retrouverait un réglage sur deux.
 */
function write(patch: { zoom?: number; mode?: ReadingMode }): void {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    const existing = raw ? (JSON.parse(raw) as object) : {};
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify({ ...existing, ...patch }));
  } catch {
    // Stockage refusé : le lecteur fonctionne, il n'a simplement pas de mémoire.
  }
}

export function writeZoom(zoom: number): void {
  write({ zoom });
}

export function writeMode(mode: ReadingMode): void {
  write({ mode });
}

export function nextZoom(current: number, direction: 1 | -1): number {
  const index = ZOOM_STEPS.indexOf(current as never);
  const from = index === -1 ? ZOOM_STEPS.indexOf(DEFAULT_ZOOM as never) : index;
  const target = Math.min(Math.max(from + direction, 0), ZOOM_STEPS.length - 1);
  return ZOOM_STEPS[target];
}
