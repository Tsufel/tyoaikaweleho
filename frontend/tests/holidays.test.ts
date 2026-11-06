import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import type { EntryRow, WorkEntry } from '../src/lib/api/types';
import { evaluateAchievements } from '../src/lib/api/mockAchievements';
import { computeRecords } from '../src/lib/api/mockRecords';
import {
  easterSunday,
  holidayName,
  holidaysInMonth,
  holidaysInYear,
  isWorkday,
  prevWorkday,
} from '../src/lib/holidays';

// Generated from holidays.py; tests/test_holidays.py checks it against Python.
const fixture: Record<string, Record<string, string>> = JSON.parse(
  readFileSync('../tests/fixtures/fi_holidays.json', 'utf8'),
);

describe('Finnish holidays (TS twin of holidays.py)', () => {
  it('matches the Python fixture year by year', () => {
    expect(Object.keys(fixture).length).toBeGreaterThanOrEqual(10);
    for (const [year, expected] of Object.entries(fixture)) {
      expect(holidaysInYear(Number(year))).toEqual(expected);
    }
  });

  it('Easter, including the earliest and latest dates', () => {
    const at = (y: number) => {
      const d = easterSunday(y);
      return [d.getMonth() + 1, d.getDate()];
    };
    expect(at(2026)).toEqual([4, 5]);
    expect(at(2285)).toEqual([3, 22]);
    expect(at(2038)).toEqual([4, 25]);
  });

  it('a shared date names both (2008: Helatorstai on Vappu)', () => {
    expect(holidayName(new Date(2008, 4, 1))).toBe('Vappu / Helatorstai');
  });

  it('workdays skip weekends and holidays (streak rules)', () => {
    expect(isWorkday(new Date(2026, 3, 2))).toBe(true); // Thu
    expect(isWorkday(new Date(2026, 3, 3))).toBe(false); // Pitkäperjantai
    expect(isWorkday(new Date(2026, 3, 4))).toBe(false); // Sat
    expect(prevWorkday(new Date(2026, 3, 7)).getDate()).toBe(2); // Tue 7 Apr -> Thu 2 Apr
  });

  it('the mock engines keep a streak over Easter like Python', () => {
    const e = (date: string): WorkEntry => ({ id: date, date, job_shift: 'Sales', time_in: '08:00', time_out: '16:00' });
    const days = ['2026-03-30', '2026-03-31', '2026-04-01', '2026-04-02', '2026-04-07'].map(e);
    const today = new Date(2026, 3, 7);
    expect(computeRecords(days, 8, today, (x) => x as EntryRow).streak).toEqual({ current: 5, best: 5 });
    const streak = evaluateAchievements(days, 8, 0, today).find((a) => a.id === 'streak_5')!;
    expect(streak.met_on).toBe('2026-04-07');
  });

  it('month and lookup', () => {
    expect(holidaysInMonth(2026, 10)).toEqual({ '2026-10-31': 'Pyhäinpäivä' });
    expect(holidaysInMonth(2026, 2)).toEqual({});
    expect(holidayName(new Date(2026, 11, 6, 15, 30))).toBe('Itsenäisyyspäivä');
    expect(holidayName(new Date(2026, 11, 7))).toBeNull();
  });
});
