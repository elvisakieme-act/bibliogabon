/**
 * Préférences d'affichage du lecteur.
 *
 * Elles appartiennent au lecteur, pas au document : quelqu'un qui lit en mode
 * livre à 120 % veut retrouver ce réglage au document suivant. Elles vivent
 * donc dans le navigateur, et leur absence n'est jamais une erreur — un
 * navigateur en navigation privée, ou qui refuse le stockage, doit ouvrir le
 * lecteur normalement.
 */

export const SCROLL_MODES = ["vertical", "horizontal", "livre"] as const;
export type ScrollMode = (typeof SCROLL_MODES)[number];

export const MODE_LABELS: Record<ScrollMode, string> = {
  vertical: "Défilement vertical",
  horizontal: "Défilement horizontal",
  livre: "Double page"
};

export const ZOOM_STEPS = [0.6, 0.75, 0.9, 1, 1.25, 1.5, 2] as const;
export const DEFAULT_ZOOM = 1;
export const DEFAULT_MODE: ScrollMode = "vertical";

const STORAGE_KEY = "bibliogabon.lecteur";

interface StoredPreferences {
  mode: ScrollMode;
  zoom: number;
}

function isMode(value: unknown): value is ScrollMode {
  return SCROLL_MODES.includes(value as ScrollMode);
}

export function readPreferences(): StoredPreferences {
  const fallback: StoredPreferences = { mode: DEFAULT_MODE, zoom: DEFAULT_ZOOM };
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return fallback;
    const parsed: unknown = JSON.parse(raw);
    if (typeof parsed !== "object" || parsed === null) return fallback;
    const { mode, zoom } = parsed as Partial<StoredPreferences>;
    return {
      mode: isMode(mode) ? mode : DEFAULT_MODE,
      // Une valeur hors de l'échelle rendrait la page illisible ou
      // invisible : on ne la reprend pas, même si elle est bien un nombre.
      zoom: typeof zoom === "number" && ZOOM_STEPS.includes(zoom as never) ? zoom : DEFAULT_ZOOM
    };
  } catch {
    return fallback;
  }
}

export function writePreferences(preferences: StoredPreferences): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(preferences));
  } catch {
    // Stockage refusé : le lecteur fonctionne, il n'a simplement pas de mémoire.
  }
}

export function nextZoom(current: number, direction: 1 | -1): number {
  const index = ZOOM_STEPS.indexOf(current as never);
  const from = index === -1 ? ZOOM_STEPS.indexOf(DEFAULT_ZOOM as never) : index;
  const target = Math.min(Math.max(from + direction, 0), ZOOM_STEPS.length - 1);
  return ZOOM_STEPS[target];
}
