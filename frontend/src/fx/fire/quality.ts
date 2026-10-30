// Adaptive quality governor for the Lulz fire (no DOM; FireLayer feeds it frame timings).

export interface QualityLevel {
  fps: 60 | 30;
  /** Multiplier on particle emission / pool use. */
  particleScale: number;
  /** 0 none, 1 cheap, 2 full additive glow. */
  glow: 0 | 1 | 2;
  smoke: boolean;
  /** Upper bound on devicePixelRatio for the canvas backing store. */
  dprCap: number;
}

/** Best (0) → cheapest (3). */
export const LEVELS: readonly QualityLevel[] = [
  { fps: 60, particleScale: 1, glow: 2, smoke: true, dprCap: 2 },
  { fps: 60, particleScale: 0.7, glow: 1, smoke: true, dprCap: 1.5 },
  { fps: 30, particleScale: 0.5, glow: 1, smoke: false, dprCap: 1.25 },
  { fps: 30, particleScale: 0.35, glow: 0, smoke: false, dprCap: 1 },
];

export interface GovernorOptions {
  /** Initial level index (default 0). */
  start?: number;
  /** Work-time EMA (ms) above which a frame counts as slow (default 7). */
  downMs?: number;
  /** Work-time EMA (ms) below which a frame counts as calm (default 3.5). */
  upMs?: number;
  /** Consecutive slow frames before stepping down (default 20). */
  downFrames?: number;
  /** Consecutive calm frames before stepping up (default 180). */
  upFrames?: number;
  /** Cheapest level allowed (default LEVELS.length - 1). */
  maxLevel?: number;
}

export interface Governor {
  /** Feed one frame: work time and time since the previous frame (ms). Returns the level index. */
  sample(workMs: number, intervalMs: number): number;
  readonly level: number;
  readonly config: QualityLevel;
  /** Back to `level` (default: start) with fresh counters. */
  reset(level?: number): void;
}

const ALPHA = 0.1;
/** Samples beyond this are tab stalls / wake-ups, not real frames. */
const STALL_MS = 250;
/** Clamp single work spikes so one GC pause can't drag the EMA for seconds. */
const WORK_CAP_MS = 100;
/** Max doublings of upFrames after quick re-downgrades (flap backoff). */
const MAX_STRIKES = 4;

/** Finite option or its default (NaN / ±Infinity would poison the counters). */
const opt = (v: number | undefined, d: number) => (v !== undefined && Number.isFinite(v) ? v : d);

const slowInterval = (fps: number) => (fps === 60 ? 24 : 48);
const calmInterval = (fps: number) => (fps === 60 ? 20 : 40);

export interface FramePacer {
  /**
   * Feed every rAF timestamp (ms). Returns the interval to draw with (ms since the last drawn frame, 0 on the first),
   * or -1 to skip this vsync.
   */
  tick(t: number, fps: number): number;
  /** Forget the cadence (loop stopped / restarted). */
  reset(): void;
  /** Current refresh-period estimate (ms). */
  readonly vsync: number;
}

/** Bounds for the refresh estimate: 250 Hz … 20 Hz. */
const VSYNC_MIN = 4;
const VSYNC_MAX = 50;

/**
 * Paces frames against a deadline instead of a minimum gap, so on any display at or above the target rate the drawn
 * intervals average exactly 1000/fps (75 Hz at fps 60 draws 4 of 5 vsyncs, not every other one). A frame is drawn
 * once the deadline is within half a vsync; falling a whole period behind resyncs rather than bursting to catch up.
 */
export function createFramePacer(): FramePacer {
  let next = 0;
  let last = 0;
  let prev = 0;
  /** Shortest recent rAF delta: drops at once, creeps back up slowly (dropped frames shouldn't inflate it). */
  let vsync = 1000 / 60;

  return {
    tick(t, fps) {
      const period = 1000 / fps;
      if (prev) {
        const d = Math.min(VSYNC_MAX, Math.max(VSYNC_MIN, t - prev));
        vsync = d < vsync ? d : vsync + 0.02 * (d - vsync);
      }
      prev = t;
      if (next && t < next - vsync / 2) return -1;
      next = next && t - next < period ? next + period : t + period;
      const interval = last ? t - last : 0;
      last = t;
      return interval;
    },
    reset() {
      next = last = prev = 0;
    },
    get vsync() {
      return vsync;
    },
  };
}

/**
 * Steps down after `downFrames` consecutive slow frames, up after `upFrames` calm ones. Counters and EMAs reset on
 * every change; stepping down again soon after an upgrade doubles the next upgrade's wait (up to 16×).
 */
export function createGovernor(o: GovernorOptions = {}): Governor {
  const downMs = opt(o.downMs, 7);
  const upMs = opt(o.upMs, 3.5);
  const downFrames = Math.max(1, opt(o.downFrames, 20));
  const upFrames = Math.max(1, opt(o.upFrames, 180));
  const maxLevel = Math.max(0, Math.min(LEVELS.length - 1, Math.floor(opt(o.maxLevel, LEVELS.length - 1))));
  const clampLevel = (l: number) => Math.max(0, Math.min(maxLevel, Math.floor(l) || 0));
  const start = clampLevel(opt(o.start, 0));

  let level = start;
  let workEma = 0;
  let intervalEma = 0;
  let slow = 0;
  let calm = 0;
  let strikes = 0;
  /** Calm frames needed for the next upgrade: upFrames · 2^strikes. */
  let upNeed = upFrames;
  /** Frames since the last upgrade (-1 = no recent upgrade). */
  let sinceUp = -1;

  function neutral(): void {
    workEma = 0;
    intervalEma = 1000 / LEVELS[level].fps;
    slow = 0;
    calm = 0;
  }

  function reset(l?: number): void {
    level = l === undefined ? start : clampLevel(l);
    strikes = 0;
    upNeed = upFrames;
    sinceUp = -1;
    neutral();
  }
  reset();

  function sample(workMs: number, intervalMs: number): number {
    if (!(intervalMs > 0 && intervalMs <= STALL_MS) || !Number.isFinite(workMs)) return level;
    workEma += ALPHA * (Math.min(Math.max(workMs, 0), WORK_CAP_MS) - workEma);
    intervalEma += ALPHA * (intervalMs - intervalEma);
    const fps = LEVELS[level].fps;

    if (sinceUp >= 0 && ++sinceUp > upFrames * 4) {
      // survived long after an upgrade: forgive one strike
      sinceUp = -1;
      strikes = Math.max(0, strikes - 1);
      upNeed = upFrames * 2 ** strikes;
    }

    if (workEma > downMs || intervalEma > slowInterval(fps)) {
      calm = 0;
      if (++slow >= downFrames && level < maxLevel) {
        if (sinceUp >= 0) {
          strikes = Math.min(MAX_STRIKES, strikes + 1);
          upNeed = upFrames * 2 ** strikes;
        }
        sinceUp = -1;
        level++;
        neutral();
      }
    } else if (workEma < upMs && intervalEma <= calmInterval(fps)) {
      slow = 0;
      if (++calm >= upNeed && level > 0) {
        level--;
        sinceUp = 0;
        neutral();
      }
    } else {
      slow = 0;
      calm = 0;
    }
    return level;
  }

  return {
    sample,
    reset,
    get level() {
      return level;
    },
    get config() {
      return LEVELS[level];
    },
  };
}
