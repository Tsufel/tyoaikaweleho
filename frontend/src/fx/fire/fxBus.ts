// Tiny synchronous event bus for the Lulz effects. Lives in the main bundle so
// timer actions can fire events while the lazy fx chunk (or TimerView) is not
// mounted; listeners that are not there simply miss them.

export type Tier = 1 | 2 | 3 | 4;

export interface Milestone {
  /** Stable id, e.g. 'hour1', 'half', 'target', 'over2'. */
  id: string;
  /** Elapsed seconds at which it fires. */
  at: number;
  tier: Tier;
  /** Banner text. */
  label: string;
  /** Overtime: white-hot blue palette. */
  blue: boolean;
  /** Overtime hour count (0 before the target). */
  level: number;
}

export type FxEvent =
  | { kind: 'ignite' }
  | { kind: 'blast'; minutes: number | null }
  | { kind: 'fizzle' }
  | { kind: 'milestone'; m: Milestone }
  | { kind: 'soundcheck' };

/** Hero ring position in client px, refreshed by FireLayer while visible. */
export interface RingAnchor {
  x: number;
  y: number;
  r: number;
  /** performance.now() of the last refresh. */
  at: number;
}

const listeners = new Set<(e: FxEvent) => void>();
let anchor: RingAnchor | null = null;

export function onFx(fn: (e: FxEvent) => void): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

export function emitFx(e: FxEvent): void {
  for (const fn of [...listeners]) {
    try {
      fn(e);
    } catch (err) {
      console.error('fx listener failed', err);
    }
  }
}

export function setRingAnchor(a: RingAnchor | null): void {
  anchor = a;
}

export function getRingAnchor(): RingAnchor | null {
  return anchor;
}
