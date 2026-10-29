import { describe, expect, it } from 'vitest';
import cases from './fixtures/time_cases.json';
import {
  SLOTS,
  addHours,
  addMonths,
  entryMinutes,
  formatClock,
  formatDuration,
  formatMoney,
  fromIsoDate,
  fromIsoDateTime,
  isLongShift,
  isOvernight,
  isoWeek,
  isValidTime,
  nearestSlot,
  parseDateInput,
  parsePayRate,
  parseTimeInput,
  resolveStartTime,
  startTimeNeedsConfirm,
  toIsoDateTime,
  weekKey,
} from '../src/lib/time';

const dt = (s: string) => fromIsoDateTime(s)!;
const d = (s: string) => fromIsoDate(s)!;

describe('parseTimeInput (utils.parse_time_input)', () => {
  it.each(cases.parse_time_valid)('%j -> %j', (inp, exp) => expect(parseTimeInput(inp)).toBe(exp));
  it.each(cases.parse_time_invalid)('%j -> null', (inp) => expect(parseTimeInput(inp)).toBeNull());
  it('isValidTime', () => {
    expect(isValidTime('09:30')).toBe(true);
    expect(isValidTime('bad')).toBe(false);
  });
});

describe('entry duration', () => {
  it.each(cases.entry_minutes)('entryMinutes(%j, %j) = %j', (a, b, m) => expect(entryMinutes(a as string, b as string)).toBe(m));
  it.each(cases.is_overnight)('isOvernight(%j, %j) = %j', (a, b, v) => expect(isOvernight(a as string, b as string)).toBe(v));
  it.each(cases.long_shift)('isLongShift(%j) = %j', (m, v) => expect(isLongShift(m as number)).toBe(v));
});

describe('resolveStartTime / startTimeNeedsConfirm', () => {
  it.each(cases.resolve_start_time)('$h:$m at $now', ({ now, h, m, expected }) =>
    expect(toIsoDateTime(resolveStartTime(h, m, dt(now)))).toBe(expected),
  );
  it.each(cases.start_confirm_true)('%i:%i needs confirm', (h, m) =>
    expect(startTimeNeedsConfirm(h, m, dt(cases.start_confirm_now))).toBe(true),
  );
  it.each(cases.start_confirm_false)('%i:%i no confirm', (h, m) =>
    expect(startTimeNeedsConfirm(h, m, dt(cases.start_confirm_now))).toBe(false),
  );
  it.each(cases.start_confirm_midnight)('$h:$m at $now -> $expected', ({ now, h, m, expected }) =>
    expect(startTimeNeedsConfirm(h, m, dt(now))).toBe(expected),
  );
});

describe('isoWeek (utils.week_key)', () => {
  it.each(cases.week_key)('%s', (iso, exp) => expect(isoWeek(d(iso as string))).toEqual(exp));
  it('sorts across the year boundary', () => {
    const keys = ['2027-01-04', '2027-01-01'].map((s) => weekKey(d(s))).sort();
    expect(keys).toEqual(['2026-W53', '2027-W01']);
  });
});

describe('parseDateInput', () => {
  const today = d(cases.parse_date_today);
  it.each(cases.parse_date_valid)('%j -> %j', (raw, exp) => expect(parseDateInput(raw, today)).toBe(exp));
  it.each(cases.parse_date_invalid)('%j -> null', (raw) => expect(parseDateInput(raw, today)).toBeNull());
  it('short form uses today’s year', () => {
    const c = cases.parse_date_short_form;
    expect(parseDateInput(c.raw, d(c.today))).toBe(c.expected);
  });
});

describe('parsePayRate', () => {
  it.each(cases.parse_pay_rate_valid)('%j -> %j', (raw, exp) => expect(parsePayRate(raw as string)).toBe(exp));
  it.each(cases.parse_pay_rate_invalid)('%j -> null', (raw) => expect(parsePayRate(raw)).toBeNull());
});

describe('formatting', () => {
  it.each(cases.add_hours)('addHours(%j, %j) = %j', (t, h, exp) => expect(addHours(t as string, h as number)).toBe(exp));
  it.each(cases.format_duration)('formatDuration(%j) = %j', (m, exp) => expect(formatDuration(m as number)).toBe(exp));
  it('formatClock / formatMoney', () => {
    expect(formatClock(3725)).toBe('01:02:05');
    expect(formatMoney(12.5)).toBe('€12.50');
    expect(formatMoney(Number.NaN)).toBe('€0.00');
  });
  it('addMonths wraps years', () => {
    expect(addMonths(2026, 12, 1)).toEqual({ year: 2027, month: 1 });
    expect(addMonths(2026, 1, -1)).toEqual({ year: 2025, month: 12 });
  });
});

describe('time picker slots (utils.nearest_slot)', () => {
  it('has 48 half-hour slots', () => {
    expect(SLOTS).toHaveLength(48);
    expect(SLOTS[0]).toBe('00:00');
    expect(SLOTS[47]).toBe('23:30');
  });
  it.each(cases.nearest_slot)('%j -> %j', (t, exp) => expect(nearestSlot(t as string)).toBe(exp));
  it.each(cases.nearest_slot_invalid)('%j -> null', (t) => expect(nearestSlot(t)).toBeNull());
});
