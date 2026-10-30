// Pre-rendered offscreen sprites for the ring fire (FireLayer). Built lazily,
// once per palette / resolution, and cached; nothing is attached to the DOM.

import { FIRE_BLUE, FIRE_HOT } from '../../lib/theme/tokens';
import { hexToRgb, mixRgb, type Rgb } from './palette';

/** Colour steps per palette: sim heat 0 (white-hot) … 1 (coolest). */
export const STEPS = 16;

/** Tongue sprite proportions (CSS px at res 1): tip at the top, round base at the bottom. */
export const TONGUE_W = 24;
export const TONGUE_H = 64;
/** Distance of the tongue's visual centre from its top edge, as a fraction of TONGUE_H. */
export const TONGUE_PIVOT = 0.62;

export type Sprite = HTMLCanvasElement;

export interface PaletteSprites {
  /** Soft radial discs, one per heat step (glow, cores, embers). */
  glow: Sprite[];
  /** Teardrop flame tongues, one per heat step, pointing up. */
  tongue: Sprite[];
  /** CSS colour per heat step (spark streaks, hot line). */
  color: string[];
}

/** Indexed by sim pal: 0 fire, 1 blue overtime. */
const PALETTES = [FIRE_HOT, FIRE_BLUE] as const;

const paletteCache = new Map<string, PaletteSprites>();
const smokeCache = new Map<string, Sprite>();

/** Snap the resolution so DPR jitter (zoom 110 % etc.) can't fill the cache. */
const snapRes = (res: number) => Math.min(3, Math.max(1, Math.round((res || 1) * 4) / 4));

function canvas(w: number, h: number): [Sprite, CanvasRenderingContext2D | null] {
  const c = document.createElement('canvas');
  c.width = Math.max(1, Math.round(w));
  c.height = Math.max(1, Math.round(h));
  return [c, c.getContext('2d')];
}

function ramp(stops: readonly string[], t: number): Rgb {
  const last = stops.length - 1;
  const seg = Math.min(1, Math.max(0, t)) * last;
  const i = Math.min(Math.floor(seg), last - 1);
  return mixRgb(hexToRgb(stops[i]), hexToRgb(stops[i + 1]), seg - i);
}

const rgba = (c: readonly number[], a: number) =>
  `rgba(${Math.round(c[0])},${Math.round(c[1])},${Math.round(c[2])},${a})`;

function glowSprite(c: Rgb, res: number): Sprite {
  const s = 64 * res;
  const [cv, g] = canvas(s, s);
  if (!g) return cv;
  const h = cv.width / 2;
  const grad = g.createRadialGradient(h, h, 0, h, h, h);
  grad.addColorStop(0, rgba(c, 1));
  grad.addColorStop(0.3, rgba(c, 0.6));
  grad.addColorStop(0.65, rgba(c, 0.15));
  grad.addColorStop(1, rgba(c, 0));
  g.fillStyle = grad;
  g.fillRect(0, 0, cv.width, cv.height);
  return cv;
}

/** Teardrop: a round base with a tip curving up to the top edge, soft-edged,
 *  brighter towards the base so stretched tongues fade into wisps. */
function tongueSprite(c: Rgb, hot: Rgb, res: number): Sprite {
  const [cv, g] = canvas(TONGUE_W * res, TONGUE_H * res);
  if (!g) return cv;
  const w = cv.width;
  const h = cv.height;
  const pad = 2.5 * res;
  const rb = w / 2 - pad;
  const cx = w / 2;
  const by = h - pad - rb;
  g.filter = `blur(${1.5 * res}px)`;
  g.beginPath();
  g.moveTo(cx, pad);
  g.bezierCurveTo(cx + rb * 0.25, by - rb * 1.6, cx + rb * 1.05, by - rb * 0.9, cx + rb, by);
  g.arc(cx, by, rb, 0, Math.PI);
  g.bezierCurveTo(cx - rb * 1.05, by - rb * 0.9, cx - rb * 0.25, by - rb * 1.6, cx, pad);
  g.closePath();
  const grad = g.createRadialGradient(cx, by, 0, cx, by + rb * 0.2, h * 0.95);
  grad.addColorStop(0, rgba(hot, 1));
  grad.addColorStop(0.18, rgba(c, 0.95));
  grad.addColorStop(0.55, rgba(c, 0.55));
  grad.addColorStop(1, rgba(c, 0));
  g.fillStyle = grad;
  g.fill();
  return cv;
}

/** Glow discs, tongues and colours for palette `pal` (0 fire, 1 blue) at `res` (device px per CSS px). */
export function paletteSprites(pal: number, res: number): PaletteSprites {
  const r = snapRes(res);
  const p = pal === 1 ? 1 : 0;
  const key = `${p}|${r}`;
  const hit = paletteCache.get(key);
  if (hit) return hit;
  const stops = PALETTES[p];
  const glow: Sprite[] = [];
  const tongue: Sprite[] = [];
  const color: string[] = [];
  for (let i = 0; i < STEPS; i++) {
    const t = i / (STEPS - 1);
    const c = ramp(stops, t);
    // the tongue base runs a couple of steps hotter than its body
    const hot = ramp(stops, Math.max(0, t - 0.25));
    glow.push(glowSprite(c, r));
    tongue.push(tongueSprite(c, hot, r));
    color.push(rgba(c, 1));
  }
  const out = { glow, tongue, color };
  paletteCache.set(key, out);
  return out;
}

/** Soft smoke puff tinted for the theme: warm grey on dark, sooty on light. */
export function smokeSprite(dark: boolean, res: number): Sprite {
  const r = snapRes(res);
  const key = `${dark ? 'd' : 'l'}|${r}`;
  const hit = smokeCache.get(key);
  if (hit) return hit;
  const s = 64 * r;
  const [cv, g] = canvas(s, s);
  if (g) {
    const h = cv.width / 2;
    const c: Rgb = dark ? [150, 140, 134] : [58, 52, 50];
    const grad = g.createRadialGradient(h, h, 0, h, h, h);
    grad.addColorStop(0, rgba(c, dark ? 0.55 : 0.45));
    grad.addColorStop(0.5, rgba(c, dark ? 0.25 : 0.2));
    grad.addColorStop(1, rgba(c, 0));
    g.fillStyle = grad;
    g.fillRect(0, 0, cv.width, cv.height);
  }
  smokeCache.set(key, cv);
  return cv;
}
