// Pooled particle sim for the Lulz fire (no DOM; FireLayer draws it).

import { RING } from '../../views/timer/timerLogic';
import { createNoise } from './noise';

export const KIND_FLAME = 0;
export const KIND_EMBER = 1;
export const KIND_SMOKE = 2;
export const KIND_SPARK = 3;
/** White-hot flame base. */
export const KIND_CORE = 4;

/** Flames per second along the ring at intensity 1 (rate 1). */
export const FLAME_RATE = 200;
/** Max emitRing intensity (overtime runs hotter than 1). */
export const MAX_INTENSITY = 1.6;

/** Options for {@link FireSim.emitRing}. Arc angles: radians, 0 at 12 o'clock, clockwise. */
export interface EmitOpts {
  arcFrom?: number;
  arcTo?: number;
  /** Probability 0…1 that a spawned particle uses the blue (overtime) palette. */
  blue?: number;
  /** Multiplies FLAME_RATE (quality particleScale). */
  rate?: number;
}

export interface FireSim {
  readonly capacity: number;
  /** Live particle count. */
  readonly alive: number;
  /** Sim clock in seconds (drives turbulence and flicker). */
  readonly time: number;
  x: Float32Array;
  y: Float32Array;
  vx: Float32Array;
  vy: Float32Array;
  /** Seconds left. */
  life: Float32Array;
  maxLife: Float32Array;
  size: Float32Array;
  kind: Uint8Array;
  /** Random 0…1 per particle (flicker / noise phase). */
  seed: Float32Array;
  /** Palette: 0 fire, 1 blue overtime. */
  pal: Uint8Array;
  /**
   * Emit flames along the ring's outer edge for `dt` seconds at `intensity` (0…1.6).
   * Returns flames spawned (cores/embers not counted). An arc limits spawn angles (not the rate).
   */
  emitRing(cx: number, cy: number, r: number, intensity: number, dt: number, opts?: EmitOpts): number;
  /** The "whoosh": a ring of tall flames shooting up/outward plus sparks. Returns particles spawned. */
  flare(cx: number, cy: number, r: number, power?: number, blue?: number): number;
  /** Clock-out flourish: flames, embers and sparks shoot outward from the ring. Returns particles spawned. */
  burst(cx: number, cy: number, r: number, count?: number, blue?: number): number;
  /** Fizzle: flames die fast, smoke puffs rise, embers fall. Returns smoke puffs spawned. */
  douse(): number;
  /** Advance by dt seconds (clamped); dead particles return to the pool. */
  step(dt: number): void;
  /** 0 (hot, white-yellow) … 1 (cool, deep red) for particle i. */
  heat(i: number): number;
  /** Opacity 0…1 for particle i. */
  alpha(i: number): number;
  /** Brightness multiplier 0.5…1 for particle i (noise-driven flicker). */
  flicker(i: number): number;
  /** Turbulence field: noise `scale` (1/px, default 1/60) and accel `strength` multiplier (default 1). */
  setField(f: { scale?: number; strength?: number }): void;
  /** Toggle dying flames turning into smoke (default on). */
  setSmoke(on: boolean): void;
  /** Kill everything and reset the clock and emit carry. */
  clear(): void;
}

const TAU = Math.PI * 2;
/** Outer edge of the ring stroke relative to the ring radius. */
const OUTER = 1 + RING.stroke / 2 / RING.r;
// curl accel (px/s²) per kind at strength 1
const TURB_FLAME = 140;
const TURB_SMOKE = 60;
const TURB_EMBER = 220;

const clamp01 = (v: number) => (v > 1 ? 1 : v > 0 ? v : 0);

export function createFire(capacity = 1600, rand: () => number = Math.random, noiseSeed = 7): FireSim {
  const x = new Float32Array(capacity);
  const y = new Float32Array(capacity);
  const vx = new Float32Array(capacity);
  const vy = new Float32Array(capacity);
  const life = new Float32Array(capacity);
  const maxLife = new Float32Array(capacity);
  const size = new Float32Array(capacity);
  const kind = new Uint8Array(capacity);
  const seed = new Float32Array(capacity);
  const pal = new Uint8Array(capacity);
  const noise = createNoise(noiseSeed);
  const flow = { x: 0, y: 0 };
  let alive = 0;
  let carry = 0;
  let t = 0;
  let lastIntensity = 0;
  let fieldScale = 1 / 60;
  let fieldStrength = 1;
  let smokeOn = true;
  let hasLast = false;
  let lastCx = 0;
  let lastCy = 0;
  let lastR = 0;

  function remember(cx: number, cy: number, r: number) {
    hasLast = true;
    lastCx = cx;
    lastCy = cy;
    lastR = r;
  }

  function pickPal(blue: number): number {
    if (blue <= 0) return 0;
    return blue >= 1 || rand() < blue ? 1 : 0;
  }

  function spawn(px: number, py: number, pvx: number, pvy: number, l: number, s: number, k: number, p = 0): boolean {
    if (alive >= capacity) return false;
    const i = alive++;
    x[i] = px;
    y[i] = py;
    vx[i] = pvx;
    vy[i] = pvy;
    life[i] = l;
    maxLife[i] = l;
    size[i] = s;
    kind[i] = k;
    seed[i] = rand();
    pal[i] = p;
    return true;
  }

  function kill(i: number) {
    const last = --alive;
    if (i === last) return;
    x[i] = x[last];
    y[i] = y[last];
    vx[i] = vx[last];
    vy[i] = vy[last];
    life[i] = life[last];
    maxLife[i] = maxLife[last];
    size[i] = size[last];
    kind[i] = kind[last];
    seed[i] = seed[last];
    pal[i] = pal[last];
  }

  function turb(i: number, accel: number, d: number) {
    noise.curl(x[i] * fieldScale, y[i] * fieldScale, t * 0.6, flow);
    const k = accel * fieldStrength * d;
    vx[i] += flow.x * k;
    vy[i] += flow.y * k;
  }

  const sim: FireSim = {
    capacity,
    get alive() {
      return alive;
    },
    get time() {
      return t;
    },
    x,
    y,
    vx,
    vy,
    life,
    maxLife,
    size,
    kind,
    seed,
    pal,

    emitRing(cx, cy, r, intensity, dt, opts) {
      const inten = Math.min(MAX_INTENSITY, Math.max(0, intensity || 0));
      lastIntensity = inten;
      remember(cx, cy, r);
      // `!(x > 0)` style checks also reject NaN, which would otherwise poison `carry` for good
      if (inten <= 0 || !(dt > 0)) return 0;
      const from = opts?.arcFrom ?? 0;
      const to = opts?.arcTo ?? TAU;
      if (!(to >= from) || !Number.isFinite(to - from)) return 0;
      const arc = opts?.arcFrom !== undefined || opts?.arcTo !== undefined;
      const blue = opts?.blue ?? 0;
      const rate = opts?.rate ?? 1;
      if (!(rate > 0) || !Number.isFinite(rate)) return 0;
      carry += FLAME_RATE * rate * inten * Math.min(dt, 0.1);
      const emberP = 0.06 * inten * inten;
      const rOut = r * OUTER;
      let n = 0;
      while (carry >= 1) {
        carry -= 1;
        const a = arc ? from + rand() * (to - from) : rand() * TAU;
        const ox = Math.sin(a);
        const oy = -Math.cos(a);
        // skewed jitter keeps the base just outside the stroke (≥ ~1.05 r)
        const rr = rOut * (1 + (rand() - 0.25) * 0.06);
        const px = cx + ox * rr;
        const py = cy + oy * rr;
        // flames lean upward (taller at the top) and lick outward more on the lower half
        const lift = 0.75 + 0.5 * Math.max(0, -oy);
        const radial = 0.35 + 0.25 * Math.max(0, oy);
        const speed = (32 + rand() * 40) * (0.6 + 0.5 * inten);
        const fvx = ox * speed * radial + (rand() - 0.5) * 10;
        const fvy = oy * speed * radial - speed * lift;
        const ok = spawn(
          px,
          py,
          fvx,
          fvy,
          (0.45 + rand() * 0.55) * (0.75 + 0.35 * inten),
          r * (0.1 + rand() * 0.08) * (0.7 + 0.4 * inten),
          KIND_FLAME,
          pickPal(blue),
        );
        if (!ok) {
          carry = 0; // don't bank a flood while the pool is full
          break;
        }
        n++;
        if (rand() < 0.35) {
          spawn(px, py, fvx * 0.5, fvy * 0.5, 0.18 + rand() * 0.12, r * (0.05 + rand() * 0.03), KIND_CORE, pickPal(blue));
        }
        if (rand() < emberP) {
          const es = 40 + rand() * 60;
          spawn(
            px,
            py,
            ox * es + (rand() - 0.5) * 30,
            oy * es * 0.4 - (80 + rand() * 90),
            1.2 + rand() * 1.2,
            1 + rand() * 1.3,
            KIND_EMBER,
            pickPal(blue),
          );
        }
      }
      return n;
    },

    flare(cx, cy, r, power = 1, blue = 0) {
      const p = Math.min(3, Math.max(0, power));
      remember(cx, cy, r);
      const flames = Math.round(140 * p);
      const sparks = Math.round(40 * p);
      const rOut = r * OUTER;
      let n = 0;
      for (let k = 0; k < flames; k++) {
        const a = (k / flames) * TAU + rand() * 0.15;
        const ox = Math.sin(a);
        const oy = -Math.cos(a);
        const rr = rOut * (1 + (rand() - 0.25) * 0.06);
        const out = 40 + rand() * 80;
        const ok = spawn(
          cx + ox * rr,
          cy + oy * rr,
          ox * out * p + (rand() - 0.5) * 20,
          -(160 + rand() * 100) * p,
          0.5 + rand() * 0.5,
          r * (0.1 + rand() * 0.08) * 1.1 * 1.5,
          KIND_FLAME,
          pickPal(blue),
        );
        if (!ok) return n;
        n++;
      }
      for (let k = 0; k < sparks; k++) {
        const a = rand() * TAU;
        const ox = Math.sin(a);
        const oy = -Math.cos(a);
        const s = 180 + rand() * 200;
        const ok = spawn(
          cx + ox * rOut,
          cy + oy * rOut,
          ox * s,
          oy * s * 0.6 - (120 + rand() * 120) * p,
          0.4 + rand() * 0.5,
          0.8 + rand() * 0.8,
          KIND_SPARK,
          pickPal(blue),
        );
        if (!ok) return n;
        n++;
      }
      return n;
    },

    burst(cx, cy, r, count = 220, blue = 0) {
      remember(cx, cy, r);
      const rOut = r * OUTER;
      let n = 0;
      for (let k = 0; k < count; k++) {
        const a = (k / count) * TAU + rand() * 0.2;
        const ox = Math.sin(a);
        const oy = -Math.cos(a);
        const m = k % 3; // 0 ember, 1 spark, 2 flame
        const speed = m === 0 ? 200 + rand() * 220 : m === 1 ? 240 + rand() * 180 : 160 + rand() * 160;
        const ok = spawn(
          cx + ox * rOut,
          cy + oy * rOut,
          ox * speed,
          oy * speed - (m === 2 ? 20 : 40),
          m === 0 ? 0.9 + rand() * 0.9 : m === 1 ? 0.4 + rand() * 0.5 : 0.5 + rand() * 0.5,
          m === 0 ? 1.4 + rand() * 1.8 : m === 1 ? 0.8 + rand() * 0.9 : r * (0.12 + rand() * 0.1),
          m === 0 ? KIND_EMBER : m === 1 ? KIND_SPARK : KIND_FLAME,
          pickPal(blue),
        );
        if (!ok) break;
        n++;
      }
      return n;
    },

    douse() {
      const flames: number[] = [];
      for (let i = 0; i < alive; i++) {
        const k = kind[i];
        if (k === KIND_FLAME || k === KIND_CORE) {
          if (life[i] > 0.2) {
            maxLife[i] *= 0.2 / life[i]; // keep life/maxLife so alpha doesn't pop
            life[i] = 0.2;
          }
          if (k === KIND_FLAME) flames.push(i);
        } else if (k === KIND_EMBER) {
          vy[i] = Math.abs(vy[i]) * 0.25 + 15;
        }
      }
      if (!flames.length && !hasLast) return 0;
      const rOut = lastR * OUTER;
      let n = 0;
      for (let k = 0; k < 40; k++) {
        let px: number;
        let py: number;
        let s: number;
        if (flames.length) {
          const j = flames[Math.floor(rand() * flames.length) % flames.length];
          px = x[j] + (rand() - 0.5) * 6;
          py = y[j] + (rand() - 0.5) * 6;
          s = size[j] * 1.3 + 2;
        } else {
          const a = rand() * TAU;
          px = lastCx + Math.sin(a) * rOut;
          py = lastCy - Math.cos(a) * rOut;
          s = lastR * (0.1 + rand() * 0.08);
        }
        if (!spawn(px, py, (rand() - 0.5) * 20, -(20 + rand() * 30), 0.9 + rand() * 0.8, s, KIND_SMOKE)) break;
        n++;
      }
      return n;
    },

    step(dt) {
      const d = Math.min(Math.max(dt, 0), 0.1);
      if (!d) return;
      t += d;
      const drag = Math.pow(0.18, d);
      const shrink = Math.pow(0.55, d);
      const shrinkCore = Math.pow(0.2, d);
      const drag5 = Math.pow(0.5, d);
      const dragEmber = Math.pow(0.6, d);
      const grow = Math.pow(1.8, d);
      const smokeP = smokeOn ? Math.min(0.2, Math.max(0, (lastIntensity - 0.5) * 0.25)) : 0;
      for (let i = alive - 1; i >= 0; i--) {
        life[i] -= d;
        const k = kind[i];
        if (life[i] <= 0) {
          if (k === KIND_FLAME && smokeP > 0 && rand() < smokeP) {
            const l = 0.8 + rand() * 0.6;
            kind[i] = KIND_SMOKE;
            life[i] = l;
            maxLife[i] = l;
            size[i] *= 1.2;
            vy[i] = -25;
            continue;
          }
          kill(i);
          continue;
        }
        if (k === KIND_FLAME || k === KIND_CORE) {
          vx[i] *= drag;
          vy[i] = vy[i] * drag - 90 * d; // buoyancy
          turb(i, TURB_FLAME, d);
          size[i] *= k === KIND_CORE ? shrinkCore : shrink;
        } else if (k === KIND_SPARK) {
          vx[i] *= drag5;
          vy[i] = vy[i] * drag5 + 260 * d;
        } else if (k === KIND_SMOKE) {
          vx[i] *= drag5;
          vy[i] = -25 + (vy[i] + 25) * drag5; // settles into a slow rise
          turb(i, TURB_SMOKE, d);
          size[i] *= grow;
        } else {
          vx[i] *= dragEmber;
          vy[i] += 30 * d; // embers arc back down a little
          turb(i, TURB_EMBER, d);
        }
        x[i] += vx[i] * d;
        y[i] += vy[i] * d;
      }
    },

    heat(i) {
      const u = clamp01(1 - life[i] / maxLife[i]);
      switch (kind[i]) {
        case KIND_EMBER:
          return 0.15 + u * 0.6;
        case KIND_CORE:
          return Math.min(1, 0.02 + u * u * u * 1.4);
        case KIND_SPARK:
          return 0.05 + u * 0.35;
        case KIND_SMOKE:
          return 1;
        default:
          return Math.min(1, u * 1.15);
      }
    },

    alpha(i) {
      const u = clamp01(life[i] / maxLife[i]);
      switch (kind[i]) {
        case KIND_EMBER:
        case KIND_SPARK:
          return Math.min(1, u * 1.6);
        case KIND_SMOKE:
          return 0.5 * Math.sin(Math.PI * u);
        case KIND_CORE:
          return Math.min(1, (1 - u) * 12) * Math.sqrt(u);
        default:
          // quick fade-in, long fade-out
          return Math.min(1, (1 - u) * 8) * Math.pow(u, 0.8);
      }
    },

    flicker(i) {
      const f = 0.75 + 0.25 * noise.n1(seed[i] * 97 + t * 14);
      return f < 0.5 ? 0.5 : f > 1 ? 1 : f;
    },

    setField(f) {
      if (f.scale !== undefined && Number.isFinite(f.scale)) fieldScale = f.scale;
      if (f.strength !== undefined && Number.isFinite(f.strength)) fieldStrength = Math.max(0, f.strength);
    },

    setSmoke(on) {
      smokeOn = on;
    },

    clear() {
      alive = 0;
      carry = 0;
      t = 0;
      lastIntensity = 0;
      hasLast = false;
    },
  };
  return sim;
}
