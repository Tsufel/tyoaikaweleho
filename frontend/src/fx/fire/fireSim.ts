// Pooled particle sim for the Lulz fire (no DOM; FireLayer draws it).

export const KIND_FLAME = 0;
export const KIND_EMBER = 1;

export interface FireSim {
  readonly capacity: number;
  /** Live particle count. */
  readonly alive: number;
  x: Float32Array;
  y: Float32Array;
  vx: Float32Array;
  vy: Float32Array;
  /** Seconds left. */
  life: Float32Array;
  maxLife: Float32Array;
  size: Float32Array;
  kind: Uint8Array;
  /** Emit flames along a ring for `dt` seconds at `intensity` (0…1.4). */
  emitRing(cx: number, cy: number, r: number, intensity: number, dt: number): number;
  /** Clock-out flourish: flames shoot outward from the ring plus an ember shower. */
  burst(cx: number, cy: number, r: number, count?: number): number;
  /** Advance by dt seconds (clamped); dead particles return to the pool. */
  step(dt: number): void;
  /** 0 (hot, white-yellow) … 1 (cool, deep red) for particle i. */
  heat(i: number): number;
  /** Opacity 0…1 for particle i. */
  alpha(i: number): number;
  clear(): void;
}

/** Flames per second along the ring at intensity 1. */
export const FLAME_RATE = 140;

export function createFire(capacity = 700, rand: () => number = Math.random): FireSim {
  const x = new Float32Array(capacity);
  const y = new Float32Array(capacity);
  const vx = new Float32Array(capacity);
  const vy = new Float32Array(capacity);
  const life = new Float32Array(capacity);
  const maxLife = new Float32Array(capacity);
  const size = new Float32Array(capacity);
  const kind = new Uint8Array(capacity);
  let alive = 0;
  let carry = 0;

  function spawn(px: number, py: number, pvx: number, pvy: number, l: number, s: number, k: number): boolean {
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
  }

  const sim: FireSim = {
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
    kind,

    emitRing(cx, cy, r, intensity, dt) {
      if (intensity <= 0 || dt <= 0) return 0;
      carry += FLAME_RATE * Math.min(1.4, intensity) * Math.min(dt, 0.1);
      let n = 0;
      while (carry >= 1) {
        carry -= 1;
        const a = rand() * Math.PI * 2;
        const ca = Math.cos(a);
        const sa = Math.sin(a);
        const rr = r + (rand() - 0.5) * r * 0.08;
        // flames lean upward; the top of the ring burns a bit taller
        const lift = 0.75 + 0.5 * Math.max(0, -sa);
        const speed = (28 + rand() * 34) * (0.6 + 0.5 * intensity);
        const ok = spawn(
          cx + ca * rr,
          cy + sa * rr,
          ca * speed * 0.35 + (rand() - 0.5) * 10,
          -speed * lift,
          (0.45 + rand() * 0.55) * (0.75 + 0.35 * intensity),
          r * (0.1 + rand() * 0.08) * (0.7 + 0.4 * intensity),
          KIND_FLAME,
        );
        if (!ok) break;
        n++;
        if (rand() < 0.05 * intensity) {
          spawn(cx + ca * rr, cy + sa * rr, (rand() - 0.5) * 30, -(50 + rand() * 60), 1 + rand() * 0.8, 1.2 + rand() * 1.4, KIND_EMBER);
        }
      }
      return n;
    },

    burst(cx, cy, r, count = 160) {
      let n = 0;
      for (let k = 0; k < count; k++) {
        const a = (k / count) * Math.PI * 2 + rand() * 0.2;
        const ca = Math.cos(a);
        const sa = Math.sin(a);
        const ember = k % 3 === 0;
        const speed = ember ? 120 + rand() * 160 : 70 + rand() * 120;
        const ok = spawn(
          cx + ca * r,
          cy + sa * r,
          ca * speed,
          sa * speed - (ember ? 40 : 20),
          ember ? 0.9 + rand() * 0.9 : 0.5 + rand() * 0.5,
          ember ? 1.4 + rand() * 1.8 : r * (0.12 + rand() * 0.1),
          ember ? KIND_EMBER : KIND_FLAME,
        );
        if (!ok) break;
        n++;
      }
      return n;
    },

    step(dt) {
      const d = Math.min(Math.max(dt, 0), 0.1);
      if (!d) return;
      const drag = Math.pow(0.18, d);
      for (let i = alive - 1; i >= 0; i--) {
        life[i] -= d;
        if (life[i] <= 0) {
          kill(i);
          continue;
        }
        if (kind[i] === KIND_FLAME) {
          vx[i] *= drag;
          vy[i] = vy[i] * drag - 90 * d; // buoyancy
          size[i] *= Math.pow(0.55, d);
        } else {
          vx[i] *= Math.pow(0.6, d);
          vy[i] += 30 * d; // embers arc back down a little
        }
        x[i] += vx[i] * d;
        y[i] += vy[i] * d;
      }
    },

    heat(i) {
      const t = 1 - life[i] / maxLife[i];
      return kind[i] === KIND_EMBER ? 0.15 + t * 0.6 : Math.min(1, t * 1.15);
    },

    alpha(i) {
      const t = life[i] / maxLife[i];
      if (kind[i] === KIND_EMBER) return Math.min(1, t * 1.6);
      // quick fade-in, long fade-out
      return Math.min(1, (1 - t) * 8) * Math.pow(t, 0.8);
    },

    clear() {
      alive = 0;
      carry = 0;
    },
  };
  return sim;
}
