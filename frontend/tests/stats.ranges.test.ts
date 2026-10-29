import { describe, expect, it } from 'vitest';
import {
  MAX_RANGE_DAYS,
  addDays,
  defaultGranularity,
  fitGranularity,
  formatRange,
  granularityAllowed,
  periodTitle,
  presetRange,
  shiftRange,
  spanDays,
  validateRange,
} from '../src/views/stats/ranges';

const today = new Date(2026, 9, 29); // Thu 29 Oct 2026

describe('presetRange', () => {
  it('week runs Monday to Sunday', () => {
    expect(presetRange('week', today)).toEqual({ start: '2026-10-26', end: '2026-11-01' });
    expect(presetRange('week', today, -1)).toEqual({ start: '2026-10-19', end: '2026-10-25' });
  });
  it('week containing a Sunday starts the Monday before', () => {
    expect(presetRange('week', new Date(2026, 10, 1))).toEqual({ start: '2026-10-26', end: '2026-11-01' });
  });
  it('week across a year boundary', () => {
    expect(presetRange('week', new Date(2026, 0, 1))).toEqual({ start: '2025-12-29', end: '2026-01-04' });
  });
  it('month is whole, offsets wrap years', () => {
    expect(presetRange('month', today)).toEqual({ start: '2026-10-01', end: '2026-10-31' });
    expect(presetRange('month', today, -10)).toEqual({ start: '2025-12-01', end: '2025-12-31' });
    expect(presetRange('month', new Date(2028, 1, 10))).toEqual({ start: '2028-02-01', end: '2028-02-29' });
  });
  it('last 3 months includes the current month', () => {
    expect(presetRange('quarter', today)).toEqual({ start: '2026-08-01', end: '2026-10-31' });
    expect(presetRange('quarter', today, -1)).toEqual({ start: '2026-05-01', end: '2026-07-31' });
    expect(presetRange('quarter', new Date(2026, 0, 15))).toEqual({ start: '2025-11-01', end: '2026-01-31' });
  });
  it('year', () => {
    expect(presetRange('year', today, -1)).toEqual({ start: '2025-01-01', end: '2025-12-31' });
  });
});

describe('spans and shifting', () => {
  it('spanDays is inclusive and DST-safe', () => {
    expect(spanDays({ start: '2026-10-26', end: '2026-11-01' })).toBe(7);
    expect(spanDays({ start: '2026-03-28', end: '2026-03-30' })).toBe(3);
    expect(spanDays({ start: '2026-01-01', end: '2026-12-31' })).toBe(365);
  });
  it('addDays crosses months', () => {
    expect(addDays('2026-10-31', 1)).toBe('2026-11-01');
    expect(addDays('2026-03-01', -1)).toBe('2026-02-28');
  });
  it('custom ranges step by their own length', () => {
    expect(shiftRange({ start: '2026-10-01', end: '2026-10-10' }, 1)).toEqual({ start: '2026-10-11', end: '2026-10-20' });
    expect(shiftRange({ start: '2026-10-01', end: '2026-10-10' }, -1)).toEqual({ start: '2026-09-21', end: '2026-09-30' });
  });
});

describe('granularity', () => {
  const year = presetRange('year', today);
  it('defaults per preset', () => {
    expect(defaultGranularity('week', presetRange('week', today))).toBe('day');
    expect(defaultGranularity('month', presetRange('month', today))).toBe('day');
    expect(defaultGranularity('quarter', presetRange('quarter', today))).toBe('week');
    expect(defaultGranularity('year', year)).toBe('month');
  });
  it('custom default follows the span', () => {
    expect(defaultGranularity('custom', { start: '2026-10-01', end: '2026-10-20' })).toBe('day');
    expect(defaultGranularity('custom', { start: '2026-01-01', end: '2026-05-01' })).toBe('week');
    expect(defaultGranularity('custom', { start: '2024-01-01', end: '2026-05-01' })).toBe('month');
  });
  it('day bars are not allowed for a whole year', () => {
    expect(granularityAllowed('day', year)).toBe(false);
    expect(granularityAllowed('week', year)).toBe(true);
    expect(granularityAllowed('month', { start: '2016-01-01', end: '2026-01-01' })).toBe(true);
  });
  it('fitGranularity keeps a valid choice and falls back otherwise', () => {
    expect(fitGranularity('week', 'month', presetRange('month', today))).toBe('week');
    expect(fitGranularity('day', 'year', year)).toBe('month');
    expect(fitGranularity('week', 'custom', { start: '2016-01-01', end: '2026-01-01' })).toBe('month');
  });
});

describe('validateRange', () => {
  it('accepts a normal range', () => expect(validateRange({ start: '2026-10-01', end: '2026-10-01' })).toBeNull());
  it('rejects reversed ranges', () => expect(validateRange({ start: '2026-10-02', end: '2026-10-01' })).toMatch(/on or after/));
  it('rejects malformed dates', () => expect(validateRange({ start: '2026-13-01', end: '2026-10-01' })).toMatch(/Pick a start/));
  it('rejects ranges past the backend limit', () => {
    const end = addDays('2016-01-01', MAX_RANGE_DAYS);
    expect(validateRange({ start: '2016-01-01', end })).toMatch(/ten years/);
    expect(validateRange({ start: '2016-01-01', end: addDays('2016-01-01', MAX_RANGE_DAYS - 1) })).toBeNull();
  });
});

describe('labels', () => {
  it('formatRange', () => {
    expect(formatRange({ start: '2026-10-26', end: '2026-11-01' })).toBe('26 Oct – 1 Nov 2026');
    expect(formatRange({ start: '2025-12-29', end: '2026-01-04' })).toBe('29 Dec 2025 – 4 Jan 2026');
    expect(formatRange({ start: '2026-10-29', end: '2026-10-29' })).toBe('29 Oct 2026');
  });
  it('periodTitle', () => {
    const m = (o: number) => presetRange('month', today, o);
    expect(periodTitle('month', 0, m(0))).toBe('This month');
    expect(periodTitle('month', -1, m(-1))).toBe('Last month');
    expect(periodTitle('month', -2, m(-2))).toBe('August 2026');
    expect(periodTitle('year', -3, presetRange('year', today, -3))).toBe('2023');
    expect(periodTitle('week', -1, presetRange('week', today, -1))).toBe('Last week');
    expect(periodTitle('custom', 0, m(0))).toBe('Custom range');
  });
});
