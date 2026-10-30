import { describe, expect, it } from 'vitest';
import {
  MAX_LIVE_JUMP,
  OVERTIME_STEPS,
  createMilestoneTracker,
  milestonesFor,
  type Milestone,
} from '../src/fx/fire/milestones';

const H = 3600;

describe('milestonesFor', () => {
  it('lists hour1, half, target and 16 overtime hours for an 8 h target', () => {
    const ms = milestonesFor(8);
    expect(ms.map((m) => [m.id, m.at])).toEqual([
      ['hour1', H],
      ['half', 4 * H],
      ['target', 8 * H],
      ...Array.from({ length: OVERTIME_STEPS }, (_, i) => [`over${i + 1}`, (9 + i) * H]),
    ]);
    expect(ms[0]).toMatchObject({ tier: 1, blue: false, level: 0, label: '1 h 🔥' });
    expect(ms[1]).toMatchObject({ tier: 2, blue: false, level: 0, label: 'Halfway 🔥🔥' });
    expect(ms[2]).toMatchObject({ tier: 3, blue: false, level: 0, label: 'TARGET HIT 🔥🔥🔥' });
    expect(ms[3]).toMatchObject({ tier: 4, blue: true, level: 1, label: '+1 h OVERTIME 💀' });
    expect(ms[ms.length - 1]).toMatchObject({ id: 'over16', tier: 4, blue: true, level: 16, label: '+16 h OVERTIME 💀' });
    for (const m of ms.slice(3)) expect(m).toMatchObject({ tier: 4, blue: true, level: m.at / H - 8 });
    for (let i = 1; i < ms.length; i++) expect(ms[i].at).toBeGreaterThan(ms[i - 1].at);
  });

  it('merges milestones under 60 s apart, keeping the higher tier', () => {
    const two = milestonesFor(2);
    expect(two.map((m) => m.id).slice(0, 2)).toEqual(['half', 'target']);
    expect(two[0]).toMatchObject({ at: H, tier: 2 });
    expect(two).toHaveLength(2 + OVERTIME_STEPS);
    const one = milestonesFor(1);
    expect(one.slice(0, 2).map((m) => [m.id, m.at])).toEqual([
      ['half', 1800],
      ['target', H],
    ]);
    // 1 h 30 s target: hour1 and target are 30 s apart
    expect(milestonesFor(1 + 30 / H).map((m) => m.id).slice(0, 2)).toEqual(['half', 'target']);
    // 2 h 2 min: hour1 and half are 60 s apart, both kept
    expect(milestonesFor(2 + 2 / 60).map((m) => m.id).slice(0, 3)).toEqual(['hour1', 'half', 'target']);
  });

  it('falls back to 8 h for bad targets', () => {
    const eight = milestonesFor(8);
    for (const t of [0, -2, NaN, Infinity]) expect(milestonesFor(t)).toEqual(eight);
  });
});

describe('createMilestoneTracker', () => {
  function run(samples: [number, boolean?, number?][], tr = createMilestoneTracker()): (string | null)[] {
    return samples.map(([e, running = true, target = 8]) => tr.update(e, running, target)?.id ?? null);
  }

  it('treats the first sample as a baseline, even exactly on a milestone', () => {
    expect(run([[H], [H + 1]])).toEqual([null, null]);
  });

  it('fires once when stepping 1 s across a milestone', () => {
    expect(run([[H - 2], [H - 1], [H], [H + 1], [H + 2]])).toEqual([null, null, 'hour1', null, null]);
  });

  it('stays silent on jumps larger than MAX_LIVE_JUMP and rebaselines', () => {
    expect(run([[H - 5], [H + 5], [H + 6]])).toEqual([null, null, null]);
    expect(run([[H - 3], [H - 3 + MAX_LIVE_JUMP]])).toEqual([null, 'hour1']);
    expect(run([[H - 3], [H - 2.5 + MAX_LIVE_JUMP]])).toEqual([null, null]);
    expect(run([[H - 30], [H + 29], [4 * H - 1], [4 * H]])).toEqual([null, null, null, 'half']);
  });

  it('rebaselines after a target change', () => {
    const tr = createMilestoneTracker();
    expect(tr.update(2 * H - 1, true, 8)).toBeNull();
    // new 4 h target puts 'half' at 2 h: crossing it right after the change is a baseline
    expect(tr.update(2 * H, true, 4)).toBeNull();
    expect(tr.update(2 * H + 1, true, 4)).toBeNull();
    expect(tr.update(4 * H - 1, true, 4)).toBeNull();
    expect(tr.update(4 * H, true, 4)?.id).toBe('target');
  });

  it('resets on stop; the next running sample is a baseline again', () => {
    const tr = createMilestoneTracker();
    expect(run([[H - 1], [H]], tr)).toEqual([null, 'hour1']);
    expect(tr.update(H, false, 8)).toBeNull();
    expect(run([[H - 1], [H]], tr)).toEqual([null, 'hour1']);
    expect(run([[4 * H - 1], [4 * H, false], [4 * H + 1]], tr)).toEqual([null, null, null]);
    tr.reset();
    expect(run([[8 * H], [8 * H + 1]], tr)).toEqual([null, null]);
  });

  it('returns the highest tier when one step crosses several milestones', () => {
    const fake = (): Milestone[] => [
      { id: 'a', at: 100, tier: 1, label: 'a', blue: false, level: 0 },
      { id: 'b', at: 101, tier: 3, label: 'b', blue: false, level: 0 },
      { id: 'c', at: 102, tier: 2, label: 'c', blue: false, level: 0 },
    ];
    const tr = createMilestoneTracker(fake);
    expect(tr.update(98, true, 8)).toBeNull();
    expect(tr.update(103, true, 8)?.id).toBe('b');
    // all three count as fired
    expect(tr.update(99, true, 8)).toBeNull();
    expect(tr.update(103, true, 8)).toBeNull();
  });

  it('breaks tier ties in favour of the later milestone', () => {
    const fake = (): Milestone[] => [
      { id: 'x', at: 100, tier: 4, label: 'x', blue: true, level: 1 },
      { id: 'y', at: 102, tier: 4, label: 'y', blue: true, level: 2 },
    ];
    const tr = createMilestoneTracker(fake);
    expect(tr.update(99, true, 8)).toBeNull();
    expect(tr.update(103, true, 8)?.id).toBe('y');
  });

  it('fires a real overtime milestone with its level', () => {
    const tr = createMilestoneTracker();
    tr.update(10 * H - 1, true, 8);
    expect(tr.update(10 * H, true, 8)).toMatchObject({ id: 'over2', tier: 4, blue: true, level: 2 });
  });

  it('can hit a moved target again after the target is raised', () => {
    const tr = createMilestoneTracker();
    expect(run([[8 * H - 1], [8 * H]], tr)).toEqual([null, 'target']);
    expect(run([[8 * H + 1, true, 9], [9 * H - 1, true, 9], [9 * H, true, 9]], tr)).toEqual([null, null, 'target']);
    // back at 8 h with the clock stepping back across 8 h: the original one already fired
    expect(run([[8 * H + 1], [8 * H - 1], [8 * H]], tr)).toEqual([null, null, null]);
  });

  it('never fires the same milestone twice with jitter back and forth', () => {
    const hits = run([[H - 1], [H], [H - 1], [H], [H - 0.5], [H + 0.5], [H - 2], [H + 1]]);
    expect(hits.filter((h) => h === 'hour1')).toHaveLength(1);
    expect(hits[1]).toBe('hour1');
  });

  it('ignores non-finite elapsed and keeps working with a NaN target', () => {
    expect(run([[NaN], [H - 1], [H]])).toEqual([null, null, 'hour1']);
    // a glitch only rebaselines: it must not forget what already fired
    expect(run([[H - 1], [H], [NaN], [H - 1], [H], [Infinity], [H + 1]])).toEqual([
      null,
      'hour1',
      null,
      null,
      null,
      null,
      null,
    ]);
    expect(run([[H - 1, true, NaN], [H, true, NaN]])).toEqual([null, 'hour1']);
  });
});
