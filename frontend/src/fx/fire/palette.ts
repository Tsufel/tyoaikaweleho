// Colour-ramp helpers for the Lulz fire (no DOM).

export type Rgb = [r: number, g: number, b: number];

const cache = new Map<string, Readonly<Rgb>>();

/** Cached parse; callers must not mutate the result. */
function parse(hex: string): Readonly<Rgb> {
  const hit = cache.get(hex);
  if (hit) return hit;
  const s = hex.trim();
  let m = /^#([0-9a-f]{3})$/i.exec(s);
  let rgb: Rgb;
  if (m) {
    const [r, g, b] = m[1].split('').map((x) => parseInt(x + x, 16));
    rgb = [r, g, b];
  } else {
    m = /^#([0-9a-f]{6})$/i.exec(s);
    if (!m) throw new Error(`Not a hex colour: ${hex}`);
    const n = parseInt(m[1], 16);
    rgb = [(n >> 16) & 255, (n >> 8) & 255, n & 255];
  }
  cache.set(hex, rgb);
  return rgb;
}

/** '#rgb' | '#rrggbb' → [r, g, b] (0–255). Throws on anything else. */
export function hexToRgb(hex: string): Rgb {
  const c = parse(hex);
  return [c[0], c[1], c[2]];
}

const clamp01 = (t: number) => (t > 0 ? (t < 1 ? t : 1) : 0);

/** Linear mix of two RGB triples, t clamped 0…1 (unrounded). */
export function mixRgb(a: readonly number[], b: readonly number[], t: number): Rgb {
  const k = clamp01(t);
  return [a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k, a[2] + (b[2] - a[2]) * k];
}

/**
 * Colour at t (0…1, clamped; NaN → 0) across evenly spaced hex stops → 'rgb(r,g,b)'. Allocates a string per call:
 * for per-particle use precompute a table with paletteSteps().
 */
export function lerpPalette(stops: readonly string[], t: number): string {
  if (!stops.length) throw new Error('lerpPalette: no stops');
  const last = stops.length - 1;
  const seg = clamp01(t) * last;
  const i = Math.min(Math.floor(seg), Math.max(0, last - 1));
  const a = parse(stops[i]);
  const b = last ? parse(stops[i + 1]) : a;
  const k = seg - i;
  const ch = (j: number) => Math.round(a[j] + (b[j] - a[j]) * k);
  return `rgb(${ch(0)},${ch(1)},${ch(2)})`;
}

/** Max table size paletteSteps() will build. */
const MAX_STEPS = 4096;

/** `n` (2…4096) evenly sampled colours from the stops; first/last equal the end stops. */
export function paletteSteps(stops: readonly string[], n: number): string[] {
  const k = Math.min(MAX_STEPS, Math.max(2, Math.floor(n) || 2));
  const out: string[] = [];
  for (let i = 0; i < k; i++) out.push(lerpPalette(stops, i / (k - 1)));
  return out;
}
