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
  hourScale,
  labelStep,
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
