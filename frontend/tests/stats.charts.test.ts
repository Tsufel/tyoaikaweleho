import { describe, expect, it } from 'vitest';
import type { ShiftTotal, StatsBucket } from '../src/lib/api/types';
import {
  NO_SHIFT_LABEL,
  SERIES_SLOTS,
  axisHours,
  axisLabels,
  axisMoney,
  barPath,
  bucketTargets,
  cumulative,
  earningsModel,
  hourScale,
  kpiDelta,
  paceAt,
  paceReady,
  percent,
  previousTotalsAt,
  resize,
  shiftSlices,
  shownLabels,
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
  it('ranks, folds and shares by shifts when measuring shifts', () => {
    const rows = ['a', 'b', 'c', 'd', 'e'].map((j) => ({ ...st(j, 1200), shifts: 2 }));
    rows.push({ ...st('f', 180), shifts: 20 });
    const s = shiftSlices(rows, [], 'shifts');
    expect(s[0].label).toBe('f');
    expect(s[0].share).toBeCloseTo(20 / 30);
    expect(s.at(-1)!.label).toBe('Other (2)');
    expect(s.at(-1)!.shifts).toBe(4);
    expect(s.reduce((t, x) => t + x.share, 0)).toBeCloseTo(1);
    // by hours, f is the smallest and folds into Other
    expect(shiftSlices(rows, []).some((x) => x.label === 'f')).toBe(false);
  });
  it('keeps zero-minute jobs when measuring shifts', () => {
    const rows = [st('a', 60), { ...st('b', 0), shifts: 1 }];
    expect(shiftSlices(rows, [])).toHaveLength(1);
    expect(shiftSlices(rows, [], 'shifts')).toHaveLength(2);
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

describe('axis labels', () => {
  const months = (from: number, count: number, year = 2025): StatsBucket[] =>
    Array.from({ length: count }, (_, i) => {
      const y = year + Math.floor((from + i) / 12);
      const m = (from + i) % 12;
      const start = `${y}-${String(m + 1).padStart(2, '0')}-01`;
      const label = `${['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][m]} ${y}`;
      return { key: start.slice(0, 7), label, start, minutes: 0, earnings: 0, shifts: 0 };
    });
  const days = (count: number): StatsBucket[] =>
    Array.from({ length: count }, (_, i) => ({ ...bucket(`2026-11-${String(i + 1).padStart(2, '0')}`), label: `Mon ${i + 1}` }));

  /** No two shown labels overlap at `slot` px per category. */
  const clear = (labels: string[], slot: number) => {
    const shown = labels.map((l, i) => [l, i] as const).filter(([l]) => l);
    for (let k = 1; k < shown.length; k++) {
      const [a, i] = shown[k - 1];
      const [b, j] = shown[k];
      expect(((a.length + b.length) * 6.8) / 2 + 10).toBeLessThanOrEqual((j - i) * slot);
    }
  };

  it('months drop the year except on the first label and where it changes', () => {
    const { step, labels } = axisLabels(months(10, 5), 'month', 80);
    expect(step).toBe(1);
    expect(labels).toEqual(['Nov 2025', 'Dec', 'Jan 2026', 'Feb', 'Mar']);
  });
  it('a year of months fits in a narrow chart without overlap', () => {
    // about 735px wide: the case where "Jan 2026Feb 2026" ran together
    const slot = 675 / 12;
    const { step, labels } = axisLabels(months(0, 12, 2026), 'month', slot);
    expect(step).toBe(1);
    expect(labels[0]).toBe('Jan 2026');
    clear(labels, slot);
  });
  it('thins labels so none collide', () => {
    for (const slot of [8, 14, 20, 33, 60]) {
      const r = axisLabels(days(31), 'day', slot);
      clear(r.labels, slot);
      expect(r.labels.filter(Boolean).length).toBeGreaterThan(0);
      expect(r.labels.every((l, i) => (i % r.step === 0) === !!l)).toBe(true);
    }
    for (const slot of [10, 25, 40]) clear(axisLabels(months(0, 36), 'month', slot).labels, slot);
  });
  it('shows the year again when thinning skips January', () => {
    const { step, labels } = axisLabels(months(0, 24, 2025), 'month', 20);
    expect(step).toBeGreaterThan(1);
    const shown = labels.filter(Boolean);
    expect(shown[0]).toBe('Jan 2025');
    expect(shown.filter((l) => l.includes('2026'))).toHaveLength(1);
  });
  it('one label when even two cannot fit', () => {
    const r = axisLabels(days(3), 'day', 2);
    expect(r.labels.filter(Boolean)).toEqual(['Mon 1']);
    expect(axisLabels([], 'day', 50)).toEqual({ step: 1, labels: [] });
    expect(axisLabels(days(2), 'day', 0).labels.filter(Boolean)).toHaveLength(1);
  });
  it('the hovered label is shown in full and its neighbours make room', () => {
    const b = months(0, 12, 2026);
    const slot = 60;
    const { labels } = axisLabels(b, 'month', slot);
    const out = shownLabels(b, labels, 4, slot);
    expect(out[4]).toBe('May 2026');
    clear(out, slot);
    expect(shownLabels(b, labels, null, slot)).toBe(labels);
  });
});

describe('previous period at the same point', () => {
  const day = (start: string, minutes: number, shifts = minutes > 0 ? 1 : 0): StatsBucket => ({
    ...bucket(start, minutes),
    earnings: minutes / 6,
    shifts,
  });
  const nov = (spec: Record<number, number>) =>
    Array.from({ length: 30 }, (_, i) => day(`2026-11-${String(i + 1).padStart(2, '0')}`, spec[i + 1] ?? 0));
  const oct = (spec: Record<number, number>) =>
    Array.from({ length: 31 }, (_, i) => day(`2026-10-${String(i + 1).padStart(2, '0')}`, spec[i + 1] ?? 0));
  const full = { minutes: 9999, earnings: 1, shifts: 9, worked_days: 9 };

  it('counts the period before up to the same day', () => {
    const r = previousTotalsAt('2026-11-01', '2026-11-30', '2026-11-06', { current: nov({ 2: 60 }), previous: oct({ 1: 60, 6: 120, 7: 300 }) }, full);
    expect(r).toEqual({ minutes: 180, earnings: 30, shifts: 2, worked_days: 2 });
  });
  it('a shift dated ahead moves the point forward', () => {
    const r = previousTotalsAt('2026-11-01', '2026-11-30', '2026-11-06', { current: nov({ 8: 60 }), previous: oct({ 7: 300, 9: 60 }) }, full);
    expect(r?.minutes).toBe(300);
  });
  it('whole periods once this one is over, none before it starts', () => {
    expect(previousTotalsAt('2026-10-01', '2026-10-31', '2026-11-06', null, full)).toBe(full);
    expect(previousTotalsAt('2026-12-01', '2026-12-31', '2026-11-06', null, full)).toBeNull();
    expect(previousTotalsAt('2026-11-01', '2026-11-30', '2026-11-06', null, full)).toBeNull();
    expect(previousTotalsAt('2026-11-01', '2026-11-30', '2026-11-06', { current: nov({}), previous: null }, full)).toBeNull();
  });
  it('kpiDelta words the change', () => {
    expect(kpiDelta(390, 0, (n) => `${n}m`, 'October', ' at this point')).toEqual({
      tone: 'up',
      text: '390m',
      hint: '+390m vs October at this point',
    });
    expect(kpiDelta(10, 12.5, (n) => `€${n}`, 'last week', '')).toEqual({ tone: 'down', text: '€2.5', hint: '−€2.5 vs last week' });
    expect(kpiDelta(3, 3, String, '2025', '')).toEqual({ tone: 'even', text: 'Same', hint: 'Same as 2025' });
    expect(kpiDelta(0.1 + 0.2, 0.3, String, 'x', '').tone).toBe('even');
  });
});
