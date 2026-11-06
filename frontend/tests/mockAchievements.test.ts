import { describe, expect, it } from 'vitest';
import type { WorkEntry } from '../src/lib/api/types';
import { evaluateAchievements } from '../src/lib/api/mockAchievements';

// The dev mock's port of achievements.py; tests/test_achievements.py is the spec.
const e = (date: string, time_in: string, time_out: string): WorkEntry =>
  ({ id: `${date}${time_in}`, date, job_shift: 'Sales', time_in, time_out }) as WorkEntry;
const iso = (y: number, m: number, d: number) =>
  `${y}-${String(m).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
const run = (entries: WorkEntry[], today = new Date(2027, 1, 1)) =>
  Object.fromEntries(evaluateAchievements(entries, 8, 0, today).map((a) => [a.id, a]));

describe('mock achievements engine', () => {
  it('has the 28 achievements, reusing medal art by icon', () => {
    const a = run([]);
    expect(Object.keys(a)).toHaveLength(28);
    expect(a.hours_250.icon).toBe('hours_100');
    expect(a.hours_2500.icon).toBe('hours_1000');
    expect(a.first_shift.icon).toBe('first_shift');
  });

  it('unlocks the calendar Easter eggs on their dates', () => {
    const a = run([
      e('2026-11-13', '13:37', '15:00'), // Friday the 13th at 13:37
      e('2026-12-25', '08:00', '12:00'),
      e('2026-12-25', '16:00', '18:00'),
    ]);
    expect(a.friday_13.met_on).toBe('2026-11-13');
    expect(a.leet.met_on).toBe('2026-11-13');
    expect(a.joulu.met_on).toBe('2026-12-25');
    expect(a.double_header.met_on).toBe('2026-12-25');
    expect(a.one_year.met_on).toBeNull();
  });

  it('counts a whole ISO week, and the first shift a year on', () => {
    const week = [5, 6, 7, 8, 9, 10, 11].map((d) => e(iso(2026, 10, d), '08:00', '16:00'));
    const a = run([e('2025-10-05', '08:00', '09:00'), ...week]);
    expect(a.no_days_off.met_on).toBe('2026-10-11');
    expect(a.one_year.met_on).toBe('2026-10-05');
    const b = run([7, 8, 9, 10, 11, 12, 13].map((d) => e(iso(2026, 10, d), '08:00', '16:00')));
    expect(b.no_days_off.met_on).toBeNull();
    expect(b.no_days_off.progress.cur).toBe(5);
  });

  it('meets streak_10, weeks_12 and the 100th shift like Python', () => {
    const days = Array.from({ length: 12 }, (_, k) => e(iso(2026, 10, 5 + k), '08:00', '16:00'));
    expect(run(days).streak_10.met_on).toBe('2026-10-16');
    const mondays = Array.from({ length: 12 }, (_, k) => {
      const d = new Date(2026, 9, 5 - 7 * k);
      return e(iso(d.getFullYear(), d.getMonth() + 1, d.getDate()), '08:00', '09:00');
    });
    expect(run(mondays).weeks_12.met_on).toBe('2026-10-05');
    const hundred = Array.from({ length: 100 }, (_, k) => {
      const d = new Date(2026, 0, 1 + k);
      return e(iso(d.getFullYear(), d.getMonth() + 1, d.getDate()), '08:00', '09:00');
    });
    expect(run(hundred).shifts_100.met_on).toBe('2026-04-10');
  });
});
