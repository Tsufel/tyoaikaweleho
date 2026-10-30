// Pooled whole-window effects sim for the Lulz blast/milestone/fizzle (no DOM; FxOverlay draws it).

export const O_SPARK = 0;
export const O_EMBER = 1;
/** Fireball puff. */
export const O_PUFF = 2;
export const O_CONFETTI = 3;
export const O_SMOKE = 4;

/** Px/s² at S = 1 (S = min(W, H) / 700). */
export const GRAVITY = 1400;
/** Floor restitution: vy *= -BOUNCE. */
export const BOUNCE = 0.42;
export const FLOOR_FRICTION = 0.7;
export const WALL_BOUNCE = 0.6;
/** Particles die on this floor hit. */
export const MAX_BOUNCES = 3;
/** Seconds; nothing lives longer. */
export const MAX_LIFE = 4;
export const SHOCK_SLOTS = 6;
/** Particles this far outside the window (left, right, below) are culled. */
export const CULL_MARGIN = 200;
const MAX_DT = 0.05;
const DEFAULT_W = 960;
const DEFAULT_H = 760;

/** Per-tier counts for flare(), index tier - 1. */
export const FLARE_SPARKS = [120, 220, 380, 450];
export const FLARE_FLASH = [0, 0.3, 0.6, 0.75];
export const FLARE_PUFFS = [0, 8, 24, 30];
export const FLARE_CONFETTI = [0, 0, 80, 100];
export const FLARE_SHOCKS = [1, 1, 2, 2];
export const FLARE_LABELS = ['', 'ON FIRE!', 'BLAZING!', 'INFERNO!'];

export interface Shockwave {
  x: number;
  y: number;
  /** Radius px. */
  r: number;
  /** Expansion speed px/s (eases out). */
  v: number;
  /** Seconds left. */
  life: number;
  max: number;
  /** Ring stroke width px at birth (renderer may thin it with life / max). */
  width: number;
  /** 0 fire, 1 blue overtime. */
  pal: 0 | 1;
  alive: boolean;
}

export interface Banner {
  text: string;
  pal: 0 | 1;
  /** Seconds left. */
  life: number;
  max: number;
}

export interface SpawnOpts {
  pal?: 0 | 1;
  /** Window size used for scaling (default 960×760). */
  W?: number;
  H?: number;
  /** Quality particle scale (multiplies counts). */
  scale?: number;
}

export interface OverlaySim {
  readonly capacity: number;
  /** Live particle count; particles 0…alive-1 are valid. */
  readonly alive: number;
  x: Float32Array;
  y: Float32Array;
  vx: Float32Array;
  vy: Float32Array;
  /** Seconds left. */
  life: Float32Array;
  maxLife: Float32Array;
  size: Float32Array;
  /** Radians (confetti, puffs). */
  rot: Float32Array;
  /** Rad/s. */
  spin: Float32Array;
  kind: Uint8Array;
  /** 0 fire, 1 blue. */
  pal: Uint8Array;
  bounces: Uint8Array;
  /** Stable random 0…1 per particle (confetti colour, flicker phase). */
  seed: Float32Array;
  /** Fixed SHOCK_SLOTS slots; check `alive`. */
  shocks: Shockwave[];
  /** Full-window flash 0…1 centred at (flashX, flashY). */
  flash: number;
  flashX: number;
  flashY: number;
  flashPal: 0 | 1;
  banner: Banner | null;
  /** Anything left to draw (particles, flash, shocks or banner). */
  readonly active: boolean;
  /** Clock-out explosion; returns particles spawned. */
  blast(x: number, y: number, opts?: SpawnOpts & { power?: number }): number;
  /** Milestone flare, bigger per tier; tier >= 2 shows a banner. Returns particles spawned. */
  flare(x: number, y: number, tier: 1 | 2 | 3 | 4, opts?: SpawnOpts & { label?: string }): number;
  /** Sad puff of smoke and a few dim sparks. Returns particles spawned. */
  fizzle(x: number, y: number, opts?: { scale?: number; W?: number; H?: number }): number;
  /** Advance by dt seconds (clamped to 0.05) inside a W×H window. */
  step(dt: number, W: number, H: number): void;
  /** 0 (hot, white-yellow) … 1 (cool, deep red / grey) for particle i. */
  heat(i: number): number;
  /** Opacity 0…1 for particle i. */
  alpha(i: number): number;
  clear(): void;
}

const TAU = Math.PI * 2;
// floor of 0.2; written so NaN / 0 sizes fall back to it instead of poisoning every velocity
const scaleOf = (W = DEFAULT_W, H = DEFAULT_H) => {
  const m = Math.min(W, H);
  return m > 140 ? m / 700 : 0.2;
};
const finite = (a: number, b: number) => Number.isFinite(a) && Number.isFinite(b);

export function createOverlaySim(capacity = 3000, rand: () => number = Math.random): OverlaySim {
  const x = new Float32Array(capacity);
  const y = new Float32Array(capacity);
  const vx = new Float32Array(capacity);
  const vy = new Float32Array(capacity);
  const life = new Float32Array(capacity);
  const maxLife = new Float32Array(capacity);
  const size = new Float32Array(capacity);
  const rot = new Float32Array(capacity);
  const spin = new Float32Array(capacity);
  const kind = new Uint8Array(capacity);
  const pal = new Uint8Array(capacity);
  const bounces = new Uint8Array(capacity);
  const seed = new Float32Array(capacity);
  // internal: alpha multiplier and base heat (dim fizzle sparks)
  const gain = new Float32Array(capacity);
  const heat0 = new Float32Array(capacity);
  const shocks: Shockwave[] = [];
  for (let k = 0; k < SHOCK_SLOTS; k++) {
    shocks.push({ x: 0, y: 0, r: 0, v: 0, life: 0, max: 1, width: 0, pal: 0, alive: false });
  }
  const shockSeq = new Float64Array(SHOCK_SLOTS); // spawn order per slot
  let shockClock = 0;
  let alive = 0;

  const between = (a: number, b: number) => a + rand() * (b - a);

  function spawn(px: number, py: number, pvx: number, pvy: number, l: number, s: number, k: number, p: number): number {
    if (alive >= capacity) return -1;
    const i = alive++;
    x[i] = px;
    y[i] = py;
    vx[i] = pvx;
    vy[i] = pvy;
    life[i] = maxLife[i] = Math.min(MAX_LIFE, l);
    size[i] = s;
    rot[i] = rand() * TAU;
    spin[i] = 0;
    kind[i] = k;
    pal[i] = p;
    bounces[i] = 0;
    seed[i] = rand();
    gain[i] = 1;
    heat0[i] = 0;
    return i;
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
    rot[i] = rot[last];
    spin[i] = spin[last];
    kind[i] = kind[last];
    pal[i] = pal[last];
    bounces[i] = bounces[last];
    seed[i] = seed[last];
    gain[i] = gain[last];
    heat0[i] = heat0[last];
  }

  function shock(px: number, py: number, v: number, l: number, width: number, p: 0 | 1) {
    // reuse a dead slot, else the most-spent ring (ties: oldest) so a burst never evicts its own fresh sibling
    let b = 0;
    for (let k = 0; k < SHOCK_SLOTS; k++) {
      const s = shocks[k];
      if (!s.alive) {
        b = k;
        break;
      }
      const f = s.life / s.max;
      const fb = shocks[b].life / shocks[b].max;
      if (f < fb || (f === fb && shockSeq[k] < shockSeq[b])) b = k;
    }
    shockSeq[b] = ++shockClock;
    const best = shocks[b];
    best.x = px;
    best.y = py;
    best.r = 0;
    best.v = v;
    best.life = best.max = l;
    best.width = width;
    best.pal = p;
    best.alive = true;
  }

  function setFlash(px: number, py: number, f: number, p: 0 | 1) {
    if (f <= 0) return;
    if (f >= sim.flash) {
      sim.flashX = px;
      sim.flashY = py;
      sim.flashPal = p;
    }
    sim.flash = Math.min(1, Math.max(sim.flash, f));
  }

  /** Radial burst of `n` particles (spin set per kind). Returns count spawned. */
  function radial(
    n: number,
    px: number,
    py: number,
    vMin: number,
    vMax: number,
    lift: number,
    lMin: number,
    lMax: number,
    sMin: number,
    sMax: number,
    k: number,
    p: number,
    jitter = 0,
  ): number {
    let made = 0;
    for (let c = 0; c < n; c++) {
      const a = rand() * TAU;
      const sp = between(vMin, vMax);
      const ox = jitter ? (rand() - 0.5) * jitter : 0;
      const oy = jitter ? (rand() - 0.5) * jitter : 0;
      const i = spawn(px + ox, py + oy, Math.cos(a) * sp, Math.sin(a) * sp + lift, between(lMin, lMax), between(sMin, sMax), k, p);
      if (i < 0) break;
      if (k === O_CONFETTI) spin[i] = (rand() - 0.5) * 24;
      else if (k === O_PUFF) spin[i] = (rand() - 0.5) * 3;
      made++;
    }
    return made;
  }

  function sparks(n: number, px: number, py: number, S: number, p: number, speed = 1): number {
    return radial(n, px, py, 500 * S * speed, 1500 * S * speed, -300 * S, 1.2, 2.6, 1.4 * S, 3.4 * S, O_SPARK, p);
  }
  function puffs(n: number, px: number, py: number, S: number, p: number): number {
    return radial(n, px, py, 200 * S, 520 * S, -40 * S, 0.5, 0.9, 40 * S, 110 * S, O_PUFF, p, 30 * S);
  }
  function confetti(n: number, px: number, py: number, S: number, p: number): number {
    return radial(n, px, py, 300 * S, 900 * S, -350 * S, 2, 3.5, 6 * S, 12 * S, O_CONFETTI, p);
  }
  function embers(n: number, px: number, py: number, S: number, p: number): number {
    let made = 0;
    for (let c = 0; c < n; c++) {
      const i = spawn(
        px + (rand() - 0.5) * 120 * S,
        py + (rand() - 0.5) * 60 * S,
        (rand() - 0.5) * 60 * S,
        -between(60, 170) * S,
        between(1.5, 3),
        between(1.5, 3.2) * S,
        O_EMBER,
        p,
      );
      if (i < 0) break;
      made++;
    }
    return made;
  }

  const count = (n: number, mul: number) => Math.max(0, Math.round(n * mul));

  const sim: OverlaySim = {
    capacity,
    get alive() {
      return alive;
    },
    x,
    y,
    vx,
    vy,
    life,
    maxLife,
    size,
    rot,
    spin,
    kind,
    pal,
    bounces,
    seed,
    shocks,
    flash: 0,
    flashX: 0,
    flashY: 0,
    flashPal: 0,
    banner: null,
    get active() {
      if (alive > 0 || sim.flash > 0.01 || sim.banner) return true;
      for (const s of shocks) if (s.alive) return true;
      return false;
    },

    blast(px, py, opts = {}) {
      if (!finite(px, py)) return 0; // a NaN origin would poison flashX/Y (canvas gradients throw on it)
      const S = scaleOf(opts.W, opts.H);
      const p = opts.pal ?? 0;
      const mul = (opts.power ?? 1) * (opts.scale ?? 1);
      setFlash(px, py, 0.9, p);
      shock(px, py, 1800 * S, 0.45, 26, p);
      shock(px, py, 900 * S, 0.8, 60, p);
      // puffs first so a near-full pool still gets the fireball
      let n = puffs(count(36, mul), px, py, S, p);
      n += sparks(count(380, mul), px, py, S, p);
      n += confetti(count(110, mul), px, py, S, p);
      n += embers(count(80, mul), px, py, S, p);
      return n;
    },

    flare(px, py, tier, opts = {}) {
      if (!finite(px, py)) return 0;
      const t = Math.min(3, Math.max(0, (tier | 0) - 1)); // NaN / out-of-range tiers clamp
      const S = scaleOf(opts.W, opts.H);
      const p = opts.pal ?? 0;
      const mul = opts.scale ?? 1;
      setFlash(px, py, FLARE_FLASH[t], p);
      shock(px, py, (1100 + 250 * t) * S, 0.5, 20 + 6 * t, p);
      if (FLARE_SHOCKS[t] > 1) shock(px, py, (600 + 120 * t) * S, 0.8, 44, p);
      let n = puffs(count(FLARE_PUFFS[t], mul), px, py, S, p);
      n += sparks(count(FLARE_SPARKS[t], mul), px, py, S, p, 0.7 + 0.1 * t);
      n += confetti(count(FLARE_CONFETTI[t], mul), px, py, S, p);
      if (t >= 1) {
        const l = t === 3 ? 2 : 1.6;
        sim.banner = { text: opts.label ?? FLARE_LABELS[t], pal: p, life: l, max: l };
      }
      return n;
    },

    fizzle(px, py, opts = {}) {
      if (!finite(px, py)) return 0;
      const S = scaleOf(opts.W, opts.H);
      const mul = opts.scale ?? 1;
      let n = 0;
      const smoke = count(20, mul);
      for (let c = 0; c < smoke; c++) {
        const i = spawn(
          px + (rand() - 0.5) * 50 * S,
          py + (rand() - 0.5) * 30 * S,
          (rand() - 0.5) * 60 * S,
          -between(30, 90) * S,
          between(1.4, 2.4),
          between(16, 32) * S,
          O_SMOKE,
          0,
        );
        if (i < 0) return n;
        spin[i] = (rand() - 0.5) * 1.5;
        n++;
      }
      const dim = count(25, mul);
      for (let c = 0; c < dim; c++) {
        const a = -Math.PI / 2 + (rand() - 0.5) * 2.2;
        const sp = between(60, 240) * S;
        const i = spawn(px, py, Math.cos(a) * sp, Math.sin(a) * sp, between(0.6, 1.3), between(1, 2) * S, O_SPARK, 0);
        if (i < 0) break;
        gain[i] = 0.45;
        heat0[i] = 0.45;
        n++;
      }
      return n;
    },

    step(dt, W, H) {
      const d = Math.min(Math.max(dt, 0), MAX_DT);
      if (!d) return;
      const S = scaleOf(W, H);
      const g = GRAVITY * S;
      const puffDrag = Math.pow(0.05, d);
      const sparkDrag = Math.pow(0.7, d);
      const smokeDrag = Math.pow(0.4, d);
      const shockEase = Math.pow(0.08, d);

      if (sim.flash > 0) {
        sim.flash *= Math.pow(0.02, d);
        if (sim.flash < 0.01) sim.flash = 0;
      }
      if (sim.banner) {
        sim.banner.life -= d;
        if (sim.banner.life <= 0) sim.banner = null;
      }
      for (const s of shocks) {
        if (!s.alive) continue;
        s.r += s.v * d;
        s.v *= shockEase;
        s.life -= d;
        if (s.life <= 0) s.alive = false;
      }

      for (let i = alive - 1; i >= 0; i--) {
        life[i] -= d;
        if (life[i] <= 0) {
          kill(i);
          continue;
        }
        const k = kind[i];
        const age = maxLife[i] - life[i];
        if (k === O_SPARK) {
          vx[i] *= sparkDrag;
          vy[i] = vy[i] * sparkDrag + g * d;
        } else if (k === O_PUFF) {
          vx[i] *= puffDrag;
          vy[i] = vy[i] * puffDrag - 120 * S * d; // buoyant fireball
          size[i] *= 1 + 0.9 * d;
        } else if (k === O_CONFETTI) {
          // linear air drag gives a terminal fall speed; flutter sways side to side
          vx[i] += (Math.sin(age * (5 + seed[i] * 4) + seed[i] * TAU) * 260 * S - vx[i] * 1.8) * d;
          vy[i] += (g * 0.35 - vy[i] * 1.8) * d;
        } else if (k === O_EMBER) {
          const wob = Math.sin(age * (2 + seed[i] * 2) + seed[i] * TAU) * 40 * S;
          vx[i] += (wob - vx[i]) * 2 * d;
          vy[i] -= 10 * S * d;
        } else {
          vx[i] *= smokeDrag;
          vy[i] = vy[i] * smokeDrag - 25 * S * d;
          size[i] *= 1 + 0.7 * d;
        }
        x[i] += vx[i] * d;
        y[i] += vy[i] * d;
        rot[i] += spin[i] * d;

        // far outside (e.g. the window shrank): cull before walls/floor can drag it back; never cull above the top
        if (x[i] < -CULL_MARGIN || x[i] > W + CULL_MARGIN || y[i] > H + CULL_MARGIN) {
          kill(i);
          continue;
        }
        if (x[i] < 0 && vx[i] < 0) {
          x[i] = 0;
          vx[i] *= -WALL_BOUNCE;
        } else if (x[i] > W && vx[i] > 0) {
          x[i] = W;
          vx[i] *= -WALL_BOUNCE;
        }
        if (y[i] > H) {
          if (k === O_SPARK || k === O_CONFETTI) {
            if (vy[i] > 0) {
              if (++bounces[i] >= MAX_BOUNCES) {
                kill(i);
                continue;
              }
              vy[i] *= -BOUNCE;
              vx[i] *= FLOOR_FRICTION;
            }
          } else if (vy[i] > 0) vy[i] = 0;
          y[i] = H;
        }
      }
    },

    heat(i) {
      const t = 1 - life[i] / maxLife[i];
      switch (kind[i]) {
        case O_PUFF:
          return Math.min(1, t * 1.7);
        case O_SPARK:
          return Math.min(1, heat0[i] + t * 0.75);
        case O_EMBER:
          return 0.2 + t * 0.6;
        case O_CONFETTI:
          return t;
        default:
          return 1;
      }
    },

    alpha(i) {
      const r = life[i] / maxLife[i]; // 1 at birth … 0 at death
      const t = 1 - r;
      switch (kind[i]) {
        case O_PUFF:
          return Math.min(1, t * 12) * Math.pow(r, 1.4);
        case O_SPARK:
          return gain[i] * Math.min(1, r / 0.3);
        case O_EMBER:
          return Math.min(1, t * 6, r / 0.3);
        case O_CONFETTI: {
          const flick = 0.75 + 0.25 * Math.sin((maxLife[i] - life[i]) * (10 + seed[i] * 8) + seed[i] * 40);
          return flick * Math.min(1, r / 0.2);
        }
        default:
          return 0.4 * Math.min(1, t * 5) * r;
      }
    },

    clear() {
      alive = 0;
      sim.flash = 0;
      sim.banner = null;
      for (const s of shocks) s.alive = false;
    },
  };
  return sim;
}
