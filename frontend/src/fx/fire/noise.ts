// Seeded value noise + curl for the fire turbulence (no DOM, deterministic).

export interface Noise {
  /** 1D noise, -1…1. */
  n1(x: number): number;
  /** 3D noise, -1…1. */
  n3(x: number, y: number, z: number): number;
  /** Divergence-free 2D flow at (x, y) and time z; writes into `out` (≈ -1…1 each). */
  curl(x: number, y: number, z: number, out: { x: number; y: number }): void;
}

/** Lehmer / Park–Miller RNG in 0…1 (same generator the fire tests use). */
export function lehmer(seed: number): () => number {
  let s = Math.abs(Math.floor(seed)) % 2147483647 || 1;
  return () => {
    s = (s * 48271) % 2147483647;
    return (s - 1) / 2147483646;
  };
}

const fade = (t: number) => t * t * t * (t * (t * 6 - 15) + 10);

export function createNoise(seed = 1): Noise {
  const rand = lehmer(seed);
  const perm = new Uint8Array(512);
  const vals = new Float32Array(256);
  const p = new Uint8Array(256);
  for (let i = 0; i < 256; i++) {
    p[i] = i;
    vals[i] = rand() * 2 - 1;
  }
  for (let i = 255; i > 0; i--) {
    const j = Math.floor(rand() * (i + 1));
    const t = p[i];
    p[i] = p[j];
    p[j] = t;
  }
  for (let i = 0; i < 512; i++) perm[i] = p[i & 255];

  const v3 = (x: number, y: number, z: number) => vals[perm[perm[perm[x & 255] + (y & 255)] + (z & 255)]];

  function n3(x: number, y: number, z: number): number {
    const xi = Math.floor(x);
    const yi = Math.floor(y);
    const zi = Math.floor(z);
    const u = fade(x - xi);
    const v = fade(y - yi);
    const w = fade(z - zi);
    const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
    const x00 = lerp(v3(xi, yi, zi), v3(xi + 1, yi, zi), u);
    const x10 = lerp(v3(xi, yi + 1, zi), v3(xi + 1, yi + 1, zi), u);
    const x01 = lerp(v3(xi, yi, zi + 1), v3(xi + 1, yi, zi + 1), u);
    const x11 = lerp(v3(xi, yi + 1, zi + 1), v3(xi + 1, yi + 1, zi + 1), u);
    return lerp(lerp(x00, x10, v), lerp(x01, x11, v), w);
  }

  function n1(x: number): number {
    const xi = Math.floor(x);
    const u = fade(x - xi);
    const a = vals[perm[xi & 255]];
    const b = vals[perm[(xi + 1) & 255]];
    return a + (b - a) * u;
  }

  const EPS = 0.01;
  function curl(x: number, y: number, z: number, out: { x: number; y: number }): void {
    // curl of a scalar potential: (dψ/dy, -dψ/dx)
    const dy = (n3(x, y + EPS, z) - n3(x, y - EPS, z)) / (2 * EPS);
    const dx = (n3(x + EPS, y, z) - n3(x - EPS, y, z)) / (2 * EPS);
    // value-noise gradients peak around ~2; scale to roughly -1…1
    out.x = Math.max(-1, Math.min(1, dy * 0.5));
    out.y = Math.max(-1, Math.min(1, -dx * 0.5));
  }

  return { n1, n3, curl };
}
