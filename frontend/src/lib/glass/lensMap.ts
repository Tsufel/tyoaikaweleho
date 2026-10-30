// Liquid glass displacement maps: pure, no DOM (tests/lensMap.test.ts).
//
// A map is an RGBA image read by <feDisplacementMap>: R/G hold the x/y
// sampling offset (128 = none), B is the rim mask (255 = sharp lens,
// 0 = frosted interior), A is always 255 so canvas never premultiplies.
// Vectors always point inward, so the lens never samples outside its box.

/** Refraction profile across the bezel, from the outer edge (index 0) to
 *  its inner end. Squircle height h(t) = (1 − (1−t)^4)^(1/4); the bend at
 *  each step follows Snell's law through that surface. Max 1, monotone
 *  non-increasing, ends at about 0. */
export function bezelLut(n = 128, ior = 1.5): Float32Array {
  const h = (t: number) => Math.pow(1 - Math.pow(1 - t, 4), 0.25);
  const out = new Float32Array(n);
  const e = 0.5 / n;
  let max = 0;
  for (let i = 0; i < n; i++) {
    const t = (i + 0.5) / n;
    const t0 = Math.max(0, t - e);
    const t1 = Math.min(1, t + e);
    const s = (h(t1) - h(t0)) / (t1 - t0);
    const th = Math.atan(s);
    const thr = Math.asin(Math.sin(th) / ior);
    const d = Math.tan(th - thr);
    out[i] = Number.isFinite(d) ? d : 0;
    if (out[i] > max) max = out[i];
  }
  for (let i = 0; i < n; i++) {
    out[i] = max > 0 ? out[i] / max : 0;
    // guard against float noise breaking monotonicity
    if (i > 0 && out[i] > out[i - 1]) out[i] = out[i - 1];
  }
  return out;
}

export type FieldSpec = {
  /** Logical (CSS px) size of the element's border box. */
  w: number;
  h: number;
  /** Corner radius (clamped to w/2, h/2). */
  r: number;
  /** Bezel width: the band that bends. */
  b: number;
  lut: Float32Array;
  /** Magnification of the whole lens (> 1 samples toward the centre). */
  zoom?: number;
  /** Max displacement in px; the filter's scale is 2·shift. */
  shift: number;
  /** 'rim': only the bezel is sharp (B mask); 'full': the whole lens is. */
  mask?: 'rim' | 'full';
};

export type LensField = { data: Uint8ClampedArray; ow: number; oh: number };

const LITTLE_ENDIAN = new Uint8Array(new Uint32Array([0x01020304]).buffer)[0] === 0x04;

function packRGBA(r: number, g: number, b: number, a: number): number {
  return LITTLE_ENDIAN ? ((a << 24) | (b << 16) | (g << 8) | r) >>> 0 : ((r << 24) | (g << 16) | (b << 8) | a) >>> 0;
}

function lutAt(lut: Float32Array, f: number): number {
  const n = lut.length;
  if (n === 1) return lut[0];
  const x = Math.min(Math.max(f, 0), 1) * (n - 1);
  const i = Math.floor(x);
  if (i >= n - 1) return lut[n - 1];
  const u = x - i;
  return lut[i] * (1 - u) + lut[i + 1] * u;
}

const smoothstep = (x: number) => {
  const t = Math.min(Math.max(x, 0), 1);
  return t * t * (3 - 2 * t);
};

const clamp1 = (v: number) => (v < -1 ? -1 : v > 1 ? 1 : v);

/** Displacement field for a rounded rectangle, sampled at k output px per
 *  CSS px. Only the bezel band is computed unless the lens zooms. */
export function lensField(spec: FieldSpec, k = 1): LensField {
  const w = Math.max(1, spec.w);
  const h = Math.max(1, spec.h);
  const ow = Math.max(1, Math.ceil(w * k));
  const oh = Math.max(1, Math.ceil(h * k));
  const r = Math.max(0, Math.min(spec.r, w / 2, h / 2));
  const b = Math.max(1, Math.min(spec.b, r));
  const full = spec.mask === 'full';
  const zoom = spec.zoom && spec.zoom > 1 ? spec.zoom : 1;
  const zk = zoom > 1 ? (1 - 1 / zoom) / Math.max(1, spec.shift) : 0;
  const lut = spec.lut;

  const data = new Uint8ClampedArray(ow * oh * 4);
  new Uint32Array(data.buffer).fill(packRGBA(128, 128, full ? 255 : 0, 255));

  const cx = w / 2;
  const cy = h / 2;
  const hw = w / 2 - r;
  const hh = h / 2 - r;
  const rowBand = Math.max(r, b);

  const pixel = (x: number, y: number) => {
    const lx = (x + 0.5) / k;
    const ly = (y + 0.5) / k;
    const dx = lx - cx;
    const dy = ly - cy;
    const px = Math.abs(dx);
    const py = Math.abs(dy);
    const qx = px - hw;
    const qy = py - hh;
    let depth: number;
    let nx: number;
    let ny: number;
    if (qx > 0 && qy > 0) {
      const d = Math.hypot(qx, qy);
      depth = r - d;
      nx = d > 0 ? qx / d : Math.SQRT1_2;
      ny = d > 0 ? qy / d : Math.SQRT1_2;
    } else {
      const ex = w / 2 - px;
      const ey = h / 2 - py;
      depth = Math.min(ex, ey);
      if (ex < ey) {
        nx = 1;
        ny = 0;
      } else {
        nx = 0;
        ny = 1;
      }
    }
    if (depth < 0) return;
    let vx = 0;
    let vy = 0;
    let rim = 0;
    if (depth < b) {
      const f = depth / b;
      const m = lutAt(lut, f);
      // inward: against the outward normal, signs restored from the quadrant
      vx = -nx * m * (dx < 0 ? -1 : 1);
      vy = -ny * m * (dy < 0 ? -1 : 1);
      rim = smoothstep(1 - f);
    }
    if (zk) {
      vx -= zk * dx;
      vy -= zk * dy;
    }
    if (!vx && !vy && !rim) return;
    const o = (y * ow + x) * 4;
    data[o] = Math.round(128 + 127 * clamp1(vx));
    data[o + 1] = Math.round(128 + 127 * clamp1(vy));
    data[o + 2] = full ? 255 : Math.round(255 * rim);
  };

  const bandCols = Math.min(ow, Math.ceil(b * k) + 1);
  for (let y = 0; y < oh; y++) {
    const ly = (y + 0.5) / k;
    if (zk || ly < rowBand || ly > h - rowBand) {
      for (let x = 0; x < ow; x++) pixel(x, y);
    } else {
      for (let x = 0; x < bandCols; x++) pixel(x, y);
      for (let x = Math.max(bandCols, ow - bandCols); x < ow; x++) pixel(x, y);
    }
  }
  return { data, ow, oh };
}

/** Big surfaces get a half-resolution map (the filter stretches it). */
export function mapScale(w: number, h: number, zoom?: number): 1 | 0.5 {
  return !(zoom && zoom > 1) && w * h > 300_000 ? 0.5 : 1;
}

const num = (v: number) => String(Math.round(v * 100) / 100);

/** Cache key; w and h are exact px because the filter region is. */
export function mapKey(spec: Omit<FieldSpec, 'lut'>, k: number): string {
  const z = spec.zoom && spec.zoom > 1 ? spec.zoom : 1;
  return `lg-${Math.round(spec.w)}x${Math.round(spec.h)}-r${num(spec.r)}-b${num(spec.b)}-s${num(spec.shift)}-z${num(z)}-${spec.mask ?? 'rim'}-k${num(k)}`;
}
