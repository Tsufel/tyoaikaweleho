// Shift milestones for the Lulz effects (no DOM): the schedule for a daily target and a
// tracker that turns elapsed-time samples into one-shot milestone hits.
import type { Milestone, Tier } from './fxBus';

export type { Milestone, Tier };

/** Overtime hours that get their own milestone. */
export const OVERTIME_STEPS = 16;
/** Milestones closer than this (seconds) are merged, keeping the higher tier. */
export const MERGE_WINDOW = 60;
/** Largest forward step (seconds) still treated as live ticking; bigger jumps rebaseline silently. */
export const MAX_LIVE_JUMP = 5;

/** Non-finite or non-positive targets mean 8 h (like fireIntensity for 0/NaN); clamped to >= 1 h like ringProgress. */
function normTarget(targetHours: number): number {
  const h = Number.isFinite(targetHours) && targetHours > 0 ? targetHours : 8;
  return Math.max(1, h);
}

/** Milestones for a daily target in hours, sorted by `at` (seconds). */
export function milestonesFor(targetHours: number): Milestone[] {
  const target = normTarget(targetHours) * 3600;
  const raw: Milestone[] = [
    { id: 'hour1', at: 3600, tier: 1, label: '1 h 🔥', blue: false, level: 0 },
    { id: 'half', at: target / 2, tier: 2, label: 'Halfway 🔥🔥', blue: false, level: 0 },
    { id: 'target', at: target, tier: 3, label: 'TARGET HIT 🔥🔥🔥', blue: false, level: 0 },
  ];
  for (let k = 1; k <= OVERTIME_STEPS; k++) {
    raw.push({ id: `over${k}`, at: target + k * 3600, tier: 4, label: `+${k} h OVERTIME 💀`, blue: true, level: k });
  }
  const sorted = raw.filter((m) => m.at > 0).sort((a, b) => a.at - b.at || a.tier - b.tier);
  const out: Milestone[] = [];
  for (const m of sorted) {
    const last = out[out.length - 1];
    if (last && m.at - last.at < MERGE_WINDOW) {
      if (m.tier >= last.tier) out[out.length - 1] = m;
    } else {
      out.push(m);
    }
  }
  return out;
}

export interface MilestoneTracker {
  /** Feed one timer sample; returns the milestone crossed live since the last sample, if any. */
  update(elapsed: number, running: boolean, targetHours: number): Milestone | null;
  /** Forget everything; the next sample is a baseline. */
  reset(): void;
}

/**
 * Fires each milestone once per running stretch, only when crossed by a small forward step.
 * The first sample after creation/reset, start or a target change is a silent baseline; so is the sample after
 * a non-finite elapsed. A milestone moved by a target change (same id, new `at`) may fire again.
 * `schedule` is injectable for tests; it must return milestones sorted by `at`.
 */
export function createMilestoneTracker(
  schedule: (targetHours: number) => Milestone[] = milestonesFor,
): MilestoneTracker {
  let prev: number | null = null;
  let target: number | null = null;
  let list: Milestone[] = [];
  // keyed by id@at so a milestone moved by a target change counts as new
  const fired = new Set<string>();

  function reset(): void {
    prev = null;
    target = null;
    list = [];
    fired.clear();
  }

  function update(elapsed: number, running: boolean, targetHours: number): Milestone | null {
    if (!running) {
      reset();
      return null;
    }
    // a glitched sample while running only rebaselines; clearing `fired` here could refire a milestone
    if (!Number.isFinite(elapsed)) {
      prev = null;
      return null;
    }
    if (target === null || !Object.is(targetHours, target)) {
      target = targetHours;
      list = schedule(targetHours);
      prev = null;
    }
    const p = prev;
    prev = elapsed;
    if (p === null || elapsed < p || elapsed - p > MAX_LIVE_JUMP) return null;
    let hit: Milestone | null = null;
    for (const m of list) {
      if (m.at <= p) continue;
      if (m.at > elapsed) break;
      const key = `${m.id}@${m.at}`;
      if (fired.has(key)) continue;
      fired.add(key);
      if (!hit || m.tier >= hit.tier) hit = m;
    }
    return hit;
  }

  return { update, reset };
}
