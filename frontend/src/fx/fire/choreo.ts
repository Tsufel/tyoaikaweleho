// Timing / choreography curves for the Lulz fire (no DOM; Keyframe is a type only).

/** Ignite fuse duration: the flame front runs once around the ring. */
export const IGNITE_MS = 800;

/** Shake presets: [amplitude px, duration ms]. */
export const SHAKE: Record<'blast' | 'tier1' | 'tier2' | 'tier3' | 'tier4', readonly [amp: number, ms: number]> = {
  blast: [12, 650],
  tier1: [4, 350],
  tier2: [6, 420],
  tier3: [9, 550],
  tier4: [10, 600],
};

const clamp = (v: number, lo: number, hi: number) => (v < lo ? lo : v > hi ? hi : v);

/**
 * Ignite fuse position 0…1 at `ms` since ignition (easeInOutCubic over IGNITE_MS, clamped).
 * Same convention as ringPoint() in views/timer/timerLogic.ts: 0 at 12 o'clock, growing clockwise.
 */
export function fuseProgress(ms: number): number {
  const t = clamp(ms / IGNITE_MS, 0, 1) || 0;
  return t < 0.5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2;
}

/** Peak hold before the decay starts. */
const BOOST_HOLD_MS = 60;
/** Decay steepness (normalised so the curve lands exactly on 1 at decayMs). */
const BOOST_K = 4;
const BOOST_E = Math.exp(-BOOST_K);

/**
 * Intensity multiplier after a blast: `peak` for the first ~60 ms, then an exponential-shaped decay that reaches
 * exactly 1 at `decayMs` and stays there. Monotone, never below 1; ms < 0 → 1.
 */
export function boostEnvelope(ms: number, peak = 2.2, decayMs = 1200): number {
  if (!(ms >= 0 && ms < decayMs && peak > 1)) return 1; // also catches NaN in any argument
  const hold = Math.min(BOOST_HOLD_MS, decayMs / 4);
  if (ms <= hold) return peak;
  const u = (ms - hold) / (decayMs - hold);
  const k = (Math.exp(-BOOST_K * u) - BOOST_E) / (1 - BOOST_E);
  return Math.max(1, 1 + (peak - 1) * k);
}

/** Wind "breathing" multiplier 0.88…1.12 at `t` seconds from two octaves of 1D noise (-1…1); NaN → 1. */
export function gust(t: number, n1: (x: number) => number): number {
  const v = 0.65 * n1(t * 0.7) + 0.35 * n1(t * 2.3 + 17.1);
  return clamp(1 + 0.12 * v, 0.88, 1.12) || 1;
}

const px = (v: number) => {
  const r = Math.round(v * 100) / 100;
  return r === 0 ? 0 : r; // no '-0'
};

/**
 * Screen-shake keyframes for Element.animate(): ≈ durMs/1000·hz + 2 frames, amplitude decaying as amp·(1−t)²
 * (x alternates sign so it reads as a shake, y is random), rotation amp·0.04°. Starts and ends at rest.
 */
export function shakeKeyframes(ampPx: number, durMs: number, rand: () => number, hz = 28): Keyframe[] {
  const n = Math.max(2, Math.round((Math.max(0, durMs) / 1000) * hz) + 2);
  const rest = 'translate(0px, 0px) rotate(0deg)';
  const frames: Keyframe[] = [{ transform: rest, offset: 0 }];
  for (let i = 1; i < n - 1; i++) {
    const t = i / (n - 1);
    const a = ampPx * (1 - t) ** 2;
    const x = a * (0.5 + 0.5 * rand()) * (i % 2 ? 1 : -1);
    const y = a * (rand() * 2 - 1);
    const z = a * 0.04 * (rand() * 2 - 1);
    frames.push({ transform: `translate(${px(x)}px, ${px(y)}px) rotate(${px(z)}deg)`, offset: t });
  }
  frames.push({ transform: rest, offset: 1 });
  return frames;
}
