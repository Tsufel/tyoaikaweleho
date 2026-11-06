// @vitest-environment node
import { describe, expect, it } from 'vitest';
import type { EntryRow, MonthData } from '../src/lib/api/types';
import { recentJobs, weekMinutesSaved, weekText } from '../src/views/timer/timerLogic';

function row(date: string, job: string, time_in = '09:00', minutes: number | null = 480, week_key = ''): EntryRow {
  return {
    id: `${date}-${job}-${time_in}`,
    date,
    job_shift: job,
    time_in,
    time_out: '17:00',
    minutes,
    overnight: false,
    display_date: date,
    time_out_display: '17:00',
    week_key,
    note: '',
  };
}

function monthOf(year: number, month: number, entries: EntryRow[]): MonthData {
  return { year, month, label: '', pay_rate: 0, entries, weeks: [], total_minutes: 0, earnings: 0 };
}

describe('recentJobs', () => {
  it('lists up to four distinct jobs, newest first', () => {
    const entries = [
      row('2026-11-02', 'Sales'),
      row('2026-11-05', 'Stock', '08:00'),
      row('2026-11-05', 'Till', '13:00'),
      row('2026-11-04', 'Sales'),
      row('2026-11-03', 'Office'),
      row('2026-11-01', 'Night'),
    ];
    expect(recentJobs(entries)).toEqual(['Till', 'Stock', 'Sales', 'Office']);
  });

  it('skips blank and placeholder jobs, and copes with no data', () => {
    expect(recentJobs([row('2026-11-05', ' '), row('2026-11-04', '—'), row('2026-11-03', 'Sales')])).toEqual(['Sales']);
    expect(recentJobs(null)).toEqual([]);
  });
});

describe('weekMinutesSaved', () => {
  // Fri 6 Nov 2026 is in ISO week 45 (Mon 2 Nov – Sun 8 Nov)
  const today = new Date(2026, 10, 6, 12, 0);

  it('sums the current ISO week from the loaded month', () => {
    const m = monthOf(2026, 11, [
      row('2026-11-02', 'A', '09:00', 480, '2026-W45'),
      row('2026-11-05', 'A', '09:00', 300, '2026-W45'),
      row('2026-11-01', 'A', '09:00', 600, '2026-W44'),
      row('2026-11-06', 'A', '09:00', null, '2026-W45'),
    ]);
    expect(weekMinutesSaved(m, today)).toBe(780);
  });

  it('is null when another month is loaded or the week began last month', () => {
    expect(weekMinutesSaved(monthOf(2026, 10, []), today)).toBeNull();
    expect(weekMinutesSaved(null, today)).toBeNull();
    // Tue 1 Dec 2026: the week began on Mon 30 Nov
    expect(weekMinutesSaved(monthOf(2026, 12, []), new Date(2026, 11, 1))).toBeNull();
  });
});

describe('weekText', () => {
  it('compares with the daily target times five', () => {
    expect(weekText(31 * 60 + 20, 8)).toBe('This week 31h 20m of 40h');
    expect(weekText(90.7, 7.5)).toBe('This week 1h 30m of 37.5h');
  });
});
