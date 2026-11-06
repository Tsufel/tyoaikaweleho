// ── In-app UI zoom ──────────────────────────────────────────────
// WebView zoom is blocked (platform/harden.ts), so the app zooms itself:
// CSS `zoom` on <html>, saved as ui_prefs.zoom (percent). Code that places
// fixed elements from getBoundingClientRect (Popover, tooltips) works in
// visual px and divides by uiScale() to get layout px.

/** The allowed zoom levels, percent (storage.ZOOM_LEVELS). */
export const ZOOM_LEVELS: readonly number[] = [80, 90, 100, 110, 120, 130, 140, 150];
export const ZOOM_DEFAULT = 100;

/** A stored value as a known level (anything else is 100 %). */
export function cleanZoom(z: unknown): number {
  return typeof z === 'number' && ZOOM_LEVELS.includes(z) ? z : ZOOM_DEFAULT;
}

/** The next level up (dir 1) or down (dir -1); stays put at the ends. */
export function stepZoom(z: number, dir: 1 | -1): number {
  const i = ZOOM_LEVELS.indexOf(cleanZoom(z));
  return ZOOM_LEVELS[Math.min(ZOOM_LEVELS.length - 1, Math.max(0, i + dir))];
}

let scale = 1;

/** The zoom applied to <html> as a factor (1 = 100 %). */
export function uiScale(): number {
  return scale;
}

/** A getBoundingClientRect() result (visual px) in layout px, for placing
 *  fixed elements with left/top under the zoom. */
export function layoutRect(r: DOMRectReadOnly): { left: number; top: number; right: number; bottom: number; width: number; height: number } {
  const s = scale;
  return { left: r.left / s, top: r.top / s, right: r.right / s, bottom: r.bottom / s, width: r.width / s, height: r.height / s };
}

/** Apply a zoom level to the page. */
export function applyZoom(z: number, root: HTMLElement = document.documentElement): void {
  const pct = cleanZoom(z);
  scale = pct / 100;
  root.style.zoom = pct === ZOOM_DEFAULT ? '' : String(scale);
}
