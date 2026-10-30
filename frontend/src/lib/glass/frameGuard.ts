// Liquid glass frame guard: if refraction makes the window drop frames,
// fall back to the CSS tier for the rest of the session.

/** Median frame time over 24ms (well under 50fps) means the GPU is struggling. */
export function shouldDowngrade(deltas: number[], limitMs = 24, minSamples = 20): boolean {
  if (deltas.length < minSamples) return false;
  const s = [...deltas].sort((a, b) => a - b);
  const mid = s.length >> 1;
  const median = s.length % 2 ? s[mid] : (s[mid - 1] + s[mid]) / 2;
  return median > limitMs;
}

/** Rough GPU weight of the live lenses: the transient Segmented thumb
 *  ('full' mask) is ignored, a dispersion lens (three displacement passes)
 *  counts three. The guard samples again when this climbs to a new peak. */
export function lensLoad(lenses: readonly { mask: 'rim' | 'full'; dispersion: boolean }[]): number {
  let n = 0;
  for (const l of lenses) if (l.mask !== 'full') n += l.dispersion ? 3 : 1;
  return n;
}

const paused = () => document.documentElement.dataset.paused === 'true' || document.visibilityState !== 'visible';

/** 1 s after start, sample 2 s of rAF deltas (skipping paused time) and call
 *  `onTrip` once if they're too slow. Returns a stop function. */
export function startFrameGuard(onTrip: () => void, delayMs = 1000, sampleMs = 2000): () => void {
  let raf = 0;
  let last = 0;
  let sampled = 0;
  let stopped = false;
  const deltas: number[] = [];

  const frame = (t: number) => {
    if (stopped) return;
    if (paused()) {
      last = 0;
    } else {
      if (last) {
        const d = t - last;
        // a long gap is a stall (window hidden, dragged), not a slow frame
        if (d < 250) {
          deltas.push(d);
          sampled += d;
        }
      }
      last = t;
    }
    if (sampled >= sampleMs) {
      stopped = true;
      if (shouldDowngrade(deltas)) onTrip();
      return;
    }
    raf = requestAnimationFrame(frame);
  };

  const timer = setTimeout(() => (raf = requestAnimationFrame(frame)), delayMs);
  return () => {
    stopped = true;
    clearTimeout(timer);
    cancelAnimationFrame(raf);
  };
}
