import { describe, expect, it } from 'vitest';
import type { ShiftTotal, StatsBucket } from '../src/lib/api/types';
import {
  NO_SHIFT_LABEL,
  SERIES_SLOTS,
  axisHours,
  axisMoney,
  barPath,
  bucketTargets,
  cumulative,
  earningsModel,
  hourScale,
  labelStep,
  paceAt,
  paceReady,
  percent,
  resize,
  shiftSlices,
  stepIndex,
  weekdaysBetween,
} from '../src/charts/chartUtils';

const bucket = (start: string, minutes = 0): StatsBucket => ({
  key: start,
  label: start,
  start,
  minutes,
  earnings: 0,
  shifts: 0,
});
const st = (job_shift: string, minutes: number): ShiftTotal => ({ job_shift, minutes, earnings: minutes / 3, shifts: 1 });

describe('scales and labels', () => {
  it('hour scale always shows the target', () => {
    const { y, ticks } = hourScale(2, 8, 200);
    expect(y.domain()[1]).toBeGreaterThanOrEqual(8);
    expect(ticks[0]).toBe(0);
    expect(y(0)).toBe(200);
  });
  it('empty data still gets a usable scale', () => {
    expect(hourScale(0, 0, 100).y.domain()[1]).toBeGreaterThan(0);
  });
  it('labelStep thins crowded axes', () => {
    expect(labelStep(7, 700)).toBe(1);
    expect(labelStep(31, 600)).toBe(3);
    expect(labelStep(0, 600)).toBe(1);
  });
  it('axis formats', () => {
    expect(axisHours(7.5)).toBe('7.5h');
    expect(axisHours(40)).toBe('40h');
    expect(axisMoney(250)).toBe('€250');
    expect(axisMoney(1500)).toBe('€1.5k');
    expect(axisMoney(24000)).toBe('€24k');
    expect(percent(0.4234)).toBe('42%');
    expect(percent(0.034)).toBe('3.4%');
    expect(percent(0)).toBe('0%');
  });
});

describe('barPath', () => {
  it('is empty for zero-height bars', () => expect(barPath(0, 10, 10, 0)).toBe(''));
  it('rounds only the top', () => {
    const d = barPath(0, 0, 20, 50, 4);
    expect(d.startsWith('M0,50V4')).toBe(true);
    expect(d.endsWith('V50Z')).toBe(true);
  });
  it('clamps the radius for short bars', () => expect(barPath(0, 98, 20, 2, 4)).toContain('V100'));
});

describe('targets', () => {
  it('weekdaysBetween', () => {
    expect(weekdaysBetween(new Date(2026, 9, 26), new Date(2026, 10, 1))).toBe(5);
    expect(weekdaysBetween(new Date(2026, 9, 31), new Date(2026, 10, 1))).toBe(0);
  });
  it('day buckets use the daily target', () => {
    expect(bucketTargets([bucket('2026-10-31'), bucket('2026-11-02')], 'day', '2026-10-31', '2026-11-02', 8)).toEqual([8, 8]);
  });
  it('week buckets clip to the range', () => {
    const t = bucketTargets([bucket('2026-09-28'), bucket('2026-10-05')], 'week', '2026-10-01', '2026-10-11', 8);
    expect(t).toEqual([16, 40]); // Thu–Fri, then a full week
  });
  it('month buckets count weekdays', () => {
    expect(bucketTargets([bucket('2026-10-01')], 'month', '2026-10-01', '2026-10-31', 7.5)).toEqual([22 * 7.5]);
  });
});

describe('shiftSlices', () => {
  it('folds jobs past the palette into Other and keeps shares', () => {
    const rows = ['a', 'b', 'c', 'd', 'e', 'f', 'g'].map((j, i) => st(j, 700 - i * 100));
    const s = shiftSlices(rows, []);
    expect(s).toHaveLength(SERIES_SLOTS);
    expect(s.at(-1)!.key).toBe('other');
    expect(s.at(-1)!.label).toBe('Other (3)');
    expect(s.at(-1)!.minutes).toBe(300 + 200 + 100);
    expect(s.reduce((t, x) => t + x.share, 0)).toBeCloseTo(1);
    expect(s.at(-1)!.slot).toBe(-1);
  });
  it('labels the empty job', () => {
    expect(shiftSlices([st('', 60)], [])[0].label).toBe(NO_SHIFT_LABEL);
  });
  it('drops zero-minute jobs', () => {
    expect(shiftSlices([st('a', 60), st('b', 0)], [])).toHaveLength(1);
  });
  it('colour follows the job, not its rank', () => {
    const known = ['Morning', 'Evening', 'Night'];
    const one = shiftSlices([st('Night', 600), st('Morning', 60)], known);
    const two = shiftSlices([st('Morning', 900), st('Night', 30)], known);
    const slot = (xs: ReturnType<typeof shiftSlices>, name: string) => xs.find((x) => x.label === name)!.slot;
    expect(slot(one, 'Night')).toBe(2);
    expect(slot(two, 'Night')).toBe(2);
    expect(slot(one, 'Morning')).toBe(0);
    expect(slot(two, 'Morning')).toBe(0);
  });
  it('unknown jobs get free slots without collisions', () => {
    const s = shiftSlices([st('x', 50), st('y', 40), st('Morning', 30)], ['Morning']);
    expect(new Set(s.map((x) => x.slot)).size).toBe(3);
    expect(s.find((x) => x.label === 'Morning')!.slot).toBe(0);
  });
});

describe('helpers', () => {
  it('cumulative rounds to cents', () => expect(cumulative([0.1, 0.2, 0.3])).toEqual([0.1, 0.3, 0.6]));
  it('resize pads with zeros and truncates', () => {
    expect(resize([1, 2], 4)).toEqual([1, 2, 0, 0]);
    expect(resize([1, 2, 3], 2)).toEqual([1, 2]);
  });
  it('stepIndex', () => {
    expect(stepIndex('ArrowRight', null, 5)).toBe(0);
    expect(stepIndex('ArrowLeft', null, 5)).toBe(4);
    expect(stepIndex('ArrowRight', 4, 5)).toBe(4);
    expect(stepIndex('ArrowLeft', 0, 5)).toBe(0);
    expect(stepIndex('End', 1, 5)).toBe(4);
    expect(stepIndex('PageDown', 0, 20)).toBe(7);
    expect(stepIndex('PageUp', 3, 20)).toBe(0);
    expect(stepIndex('a', 1, 5)).toBeNull();
    expect(stepIndex('ArrowRight', null, 0)).toBeNull();
  });
});

describe('earnings running total', () => {
  // 1–10 Nov, €100 on the 2nd and 4th
  const days = (n: number, earn: Record<number, number>, month = 11): StatsBucket[] =>
    Array.from({ length: n }, (_, i) => {
      const start = `2026-${String(month).padStart(2, '0')}-${String(i + 1).padStart(2, '0')}`;
      return { ...bucket(start), earnings: earn[i + 1] ?? 0 };
    });

  it('stops the earned line at today and paces to the period end', () => {
    const m = earningsModel(days(10, { 2: 100, 4: 100 }), '2026-11-01', '2026-11-10', '2026-11-05');
    expect(m.elapsed).toBe(4);
    expect(m.over).toBe(false);
    expect(m.totals[4]).toBe(200);
    expect(m.projected).toBe(400); // €200 in 5 of 10 days
  });

  it('paces from the first stored shift when the period began before it', () => {
    // started using the app on the 6th: €200 in 5 days, 5 days left
    const m = earningsModel(days(15, { 7: 100, 9: 100 }), '2026-11-01', '2026-11-15', '2026-11-10', null, '2026-11-06');
    expect(m.projected).toBe(400);
    // counted from the 1st it would be €200 in 10 days of 15
    expect(earningsModel(days(15, { 7: 100, 9: 100 }), '2026-11-01', '2026-11-15', '2026-11-10').projected).toBe(300);
    // an earlier first shift changes nothing
    const old = earningsModel(days(10, { 2: 100, 4: 100 }), '2026-11-01', '2026-11-10', '2026-11-05', null, '2025-01-01');
    expect(old.projected).toBe(400);
  });

  it('waits for enough of the period before projecting', () => {
    expect(paceReady(1, 7)).toBe(false);
    expect(paceReady(2, 7)).toBe(true);
    expect(paceReady(5, 30)).toBe(false);
    expect(paceReady(6, 30)).toBe(true);
    expect(paceReady(30, 30)).toBe(false);
    const m = earningsModel(days(30, { 1: 100 }), '2026-11-01', '2026-11-30', '2026-11-03');
    expect(m.projected).toBeNull();
  });

  it('keeps shifts dated ahead on the line and then does not project', () => {
    const m = earningsModel(days(10, { 2: 100, 8: 50 }), '2026-11-01', '2026-11-10', '2026-11-05');
    expect(m.elapsed).toBe(7);
    expect(m.projected).toBeNull();
  });

  it('draws the whole line and no pace once the period is over', () => {
    const m = earningsModel(days(10, { 2: 100 }), '2026-11-01', '2026-11-10', '2026-12-01');
    expect(m.elapsed).toBe(9);
    expect(m.over).toBe(true);
    expect(m.projected).toBeNull();
  });

  it('draws nothing earned before the period starts', () => {
    const m = earningsModel(days(10, {}), '2026-11-01', '2026-11-10', '2026-10-20');
    expect(m.elapsed).toBe(-1);
    expect(m.projected).toBeNull();
  });

  it('matches the previous period by position and compares at the same point', () => {
    const prev = days(12, { 1: 50, 3: 50, 12: 80 }, 10);
    const now = earningsModel(days(10, { 2: 100 }), '2026-11-01', '2026-11-10', '2026-11-05', prev);
    expect(now.previous).toHaveLength(10);
    expect(now.previous![8]).toBe(100);
    expect(now.previous![9]).toBe(180); // a longer period still ends on its total
    expect(now.previousAt).toBe(100); // by day 5
    expect(now.now).toBe(100);
    const done = earningsModel(days(10, { 2: 100 }), '2026-11-01', '2026-11-10', '2026-12-01', prev);
    expect(done.previousAt).toBe(180); // whole periods once over
    const shortPrev = earningsModel(days(10, {}), '2026-11-01', '2026-11-10', '2026-11-05', days(3, { 1: 10 }, 10));
    expect(shortPrev.previous![9]).toBe(10); // a shorter period stays at its total
  });

  describe('with week buckets and day-level data', () => {
    const coarse = (a: string, b: string, ea: number, eb: number): StatsBucket[] => [
      { ...bucket(a), earnings: ea },
      { ...bucket(b), earnings: eb },
    ];
    // Oct: €100 on the 2nd, 4th, 9th and 12th
    const prevDaily = days(14, { 2: 100, 4: 100, 9: 100, 12: 100 }, 10);
    const prevCoarse = coarse('2026-10-01', '2026-10-08', 200, 200);

    it('compares the same day of the period, not the whole bucket', () => {
      const cur = days(14, { 2: 100, 4: 100, 9: 100 });
      const args = [coarse('2026-11-01', '2026-11-08', 200, 100), '2026-11-01', '2026-11-14', '2026-11-10', prevCoarse] as const;
      // by bucket the whole second week of October counts: €100 behind
      expect(earningsModel(...args).previousAt).toBe(400);
      const m = earningsModel(...args, null, { current: cur, previous: prevDaily });
      expect(m.now).toBe(300);
      expect(m.previousAt).toBe(300); // up to 10 Oct: level
    });

    it('notices a shift dated ahead inside today\'s bucket', () => {
      const cur = days(14, { 2: 100, 4: 100, 9: 100, 13: 50 });
      const buckets = coarse('2026-11-01', '2026-11-08', 200, 150);
      expect(earningsModel(buckets, '2026-11-01', '2026-11-14', '2026-11-10').projected).not.toBeNull();
      const m = earningsModel(buckets, '2026-11-01', '2026-11-14', '2026-11-10', prevCoarse, null, {
        current: cur,
        previous: prevDaily,
      });
      expect(m.projected).toBeNull();
      expect(m.now).toBe(350); // up to the shift on the 13th
      expect(m.previousAt).toBe(400); // and October up to the 13th
    });
  });

  it('has not started when only its first week bucket has', () => {
    const buckets = [bucket('2026-11-02'), bucket('2026-11-09'), bucket('2026-11-16')];
    const m = earningsModel(buckets, '2026-11-08', '2026-11-22', '2026-11-06', days(3, { 1: 50 }, 10));
    expect(m.elapsed).toBe(-1);
    expect(m.previousAt).toBeNull();
    expect(m.now).toBe(0);
  });

  it('skips a previous period that earned nothing', () => {
    const m = earningsModel(days(10, { 2: 100 }), '2026-11-01', '2026-11-10', '2026-11-05', days(10, {}, 10));
    expect(m.previous).toBeNull();
    expect(m.previousAt).toBeNull();
  });

  it('runs the pace line straight from today to the projection', () => {
    expect(paceAt(4, 4, 10, 200, 400)).toBe(200);
    expect(paceAt(9, 4, 10, 200, 400)).toBe(400);
    expect(paceAt(6, 4, 10, 200, 400)).toBe(280);
    expect(paceAt(9, 9, 10, 200, 400)).toBe(200);
  });
});
