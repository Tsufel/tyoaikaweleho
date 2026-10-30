import { describe, expect, it } from 'vitest';
import type { PetStats } from '../src/lib/api/types';
import {
  energy,
  level,
  levelHours,
  petName,
  petPose,
  rankOf,
  usualWeekdays,
} from '../src/views/pet/petLogic';

// Friday 2026-10-30
const FRI = new Date(2026, 9, 30, 12, 0);
const iso = (d: Date) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
const day = (offset: number) => iso(new Date(2026, 9, 30 + offset));
const stats = (days: Record<string, number>, lifetime?: number): PetStats => ({
  lifetime_minutes: lifetime ?? Object.values(days).reduce((a, b) => a + b, 0),
  days,
});
/** Mon–Fri 8 h for the last `weeks` weeks before today (today excluded). */
function workweeks(weeks: number, mins = 480, weekdays = [0, 1, 2, 3, 4]) {
  const out: Record<string, number> = {};
  for (let k = 1; k <= weeks * 7; k++) {
    const d = new Date(2026, 9, 30 - k);
    if (weekdays.includes((d.getDay() + 6) % 7)) out[iso(d)] = mins;
  }
  return out;
}

describe('petName', () => {
  it('falls back to the default per kind', () => {
    expect(petName('familiar', '')).toBe('Tähti');
    expect(petName('wizard', '  ')).toBe('Weleho');
    expect(petName('wizard', ' Merlin ')).toBe('Merlin');
    expect(petName('off', null)).toBe('Tähti');
  });
});

describe('usualWeekdays', () => {
  it('is Mon–Fri until there is history', () => {
    expect(usualWeekdays({})).toEqual([0, 1, 2, 3, 4]);
    expect(usualWeekdays({ [day(-1)]: 60 })).toEqual([0, 1, 2, 3, 4]);
  });

  it('counts weekdays worked at least twice', () => {
    // Tue/Thu/Sat worker
    expect(usualWeekdays(workweeks(8, 300, [1, 3, 5]))).toEqual([1, 3, 5]);
    // a single Sunday shift isn't a habit
    expect(usualWeekdays({ ...workweeks(2, 300, [1]), [day(-5)]: 120 })).toEqual([1]);
  });

  it('ignores empty days', () => {
    expect(usualWeekdays({ [day(-7)]: 0, [day(-14)]: 0 })).toEqual([0, 1, 2, 3, 4]);
  });
});

describe('energy', () => {
  it('is hours in the last 7 days over target × usual workdays', () => {
    const e = energy(stats(workweeks(8)), FRI, 8);
    // Sat 24th … Thu 29th: Mon–Thu = 4 × 8 h; goal 5 × 8 h
    expect(e.hours).toBe(32);
    expect(e.goal).toBe(40);
    expect(e.pct).toBe(80);
  });

  it('charges live with the running shift and caps at 100', () => {
    const s = stats(workweeks(8));
    expect(energy(s, FRI, 8, 240).pct).toBe(90);
    expect(energy(s, FRI, 8, 6000).pct).toBe(100);
  });

  it('a part-timer is measured against their own days', () => {
    const e = energy(stats(workweeks(8, 300, [1, 3])), FRI, 5);
    expect(e.goal).toBe(10);
    expect(e.pct).toBe(100);
  });

  it('days off outside the usual ones do not drain it', () => {
    // a weekend away changes nothing: the window still holds a full Mon–Thu
    const weekdaysOnly = energy(stats(workweeks(8)), FRI, 8).pct;
    const withWeekend = energy(stats({ ...workweeks(8), [day(-6)]: 0 }), FRI, 8).pct;
    expect(withWeekend).toBe(weekdaysOnly);
  });

  it('counts today and nothing older than 7 days', () => {
    expect(energy(stats({ [day(0)]: 480, [day(-7)]: 480 }), FRI, 8).hours).toBe(8);
  });

  it('a bad target falls back to 8 h', () => {
    expect(energy(stats({}), FRI, Number.NaN).goal).toBe(40);
    expect(energy(stats({}), FRI, 0).goal).toBe(40);
  });
});

describe('level', () => {
  it('level n needs 10·(n−1)^1.5 lifetime hours', () => {
    expect(levelHours(1)).toBe(0);
    expect(levelHours(2)).toBe(10);
    expect(level(0).level).toBe(1);
    expect(level(599).level).toBe(1);
    expect(level(600).level).toBe(2);
    // exact thresholds land on the new level despite float error
    for (const n of [3, 5, 10, 20, 37]) {
      expect(level(levelHours(n) * 60).level).toBe(n);
      expect(level(levelHours(n) * 60 - 1).level).toBe(n - 1);
    }
  });

  it('reports progress to the next level and adds the running shift', () => {
    const l = level(300, 0);
    expect(l.progress).toBeCloseTo(0.5);
    expect(l.next).toBe(10);
    expect(level(300, 300).level).toBe(2);
    expect(level(-50).hours).toBe(0);
  });

  it('ranks', () => {
    expect([1, 4, 5, 9, 10, 19, 20, 99].map(rankOf)).toEqual([
      'Apprentice',
      'Apprentice',
      'Adept',
      'Adept',
      'Wizard',
      'Wizard',
      'Archmage',
      'Archmage',
    ]);
    expect(level(levelHours(10) * 60).rank).toBe('Wizard');
  });
});

describe('petPose', () => {
  const busy = stats(workweeks(8));
  const at = (h: number, d = FRI) => new Date(d.getFullYear(), d.getMonth(), d.getDate(), h, 30);

  it('flies while working and gets drowsy in overtime, day or night', () => {
    expect(petPose({ running: true, overTarget: false, now: at(23), stats: busy })).toBe('fly');
    expect(petPose({ running: true, overTarget: true, now: at(10), stats: busy })).toBe('drowsy');
  });

  it('is idle by day and asleep 22–06 when not working', () => {
    const p = (h: number) => petPose({ running: false, overTarget: false, now: at(h), stats: busy });
    expect([p(5), p(6), p(12), p(21), p(22)]).toEqual(['sleep', 'idle', 'idle', 'idle', 'sleep']);
  });

  it('naps after three usual workdays without a shift, and wakes on the next one', () => {
    // last shift the Monday before last: Tue … Thu off (3 usual workdays)
    const old = workweeks(8);
    for (const k of [1, 2, 3]) delete old[day(-k)];
    const s = stats(old);
    expect(petPose({ running: false, overTarget: false, now: FRI, stats: s })).toBe('sleep');
    // only two usual workdays off: still awake
    expect(petPose({ running: false, overTarget: false, now: FRI, stats: stats({ ...old, [day(-3)]: 480 }) })).toBe(
      'idle',
    );
    // a shift today wakes it
    expect(petPose({ running: false, overTarget: false, now: FRI, stats: stats({ ...old, [day(0)]: 60 }) })).toBe(
      'idle',
    );
  });

  it('a weekend is not three days off', () => {
    const mon = new Date(2026, 10, 2, 12, 0);
    const s = stats({ ...workweeks(8), [day(0)]: 480 });
    expect(petPose({ running: false, overTarget: false, now: mon, stats: s })).toBe('idle');
  });

  it('a brand-new pet with no hours is awake, and so is one without stats yet', () => {
    expect(petPose({ running: false, overTarget: false, now: FRI, stats: stats({}) })).toBe('idle');
    expect(petPose({ running: false, overTarget: false, now: FRI, stats: null })).toBe('idle');
  });
});
