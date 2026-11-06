import { describe, expect, it } from 'vitest';
import type { EntryRow, RecordsData, WorkEntry } from '../src/lib/api/types';
import { computeRecords } from '../src/lib/api/mockRecords';
import { recordTiles } from '../src/views/achievements/records';

const EMPTY: RecordsData = {
  total_shifts: 0, first_shift_date: null, days_since_first: null, longest_shift: null, best_day: null,
  best_week: null, most_shifts_week: null, best_month: null, earliest_start: null, latest_finish: null,
  streak: { current: 0, best: 0 },
};
const e = (date: string, time_in: string, time_out: string, job_shift = 'Sales'): WorkEntry =>
  ({ id: `${date}${time_in}`, date, job_shift, time_in, time_out }) as WorkEntry;
const toRow = (x: WorkEntry) => x as EntryRow;

describe('recordTiles', () => {
  it('has no tiles before the first shift', () => {
    expect(recordTiles(EMPTY)).toEqual([]);
  });

  it('labels every record, singular and plural', () => {
    const r = computeRecords(
      [e('2026-10-05', '05:12', '13:00'), e('2026-10-06', '14:00', '23:00', ''), e('2026-10-07', '18:00', '02:40')],
      8,
      new Date(2026, 9, 7, 12),
      toRow,
    );
    const by = Object.fromEntries(recordTiles(r).map((t) => [t.label, t]));
    expect(Object.keys(by)).toEqual([
      'Longest shift', 'Best day', 'Best week', 'Best month', 'Busiest week',
      'Earliest start', 'Latest finish', 'Best streak', 'With Weleho since',
    ]);
    expect(by['Longest shift']).toEqual({ label: 'Longest shift', value: '9h 00m', sub: '6.10.2026' });
    expect(by['Best week'].sub).toBe('Week 41, from 5.10.2026');
    expect(by['Best month'].sub).toBe('October 2026');
    expect(by['Busiest week'].value).toBe('3 shifts');
    expect(by['Earliest start'].value).toBe('05:12');
    expect(by['Latest finish']).toEqual({ label: 'Latest finish', value: '02:40 +1', sub: '7.10.2026, next morning' });
    expect(by['Best streak']).toEqual({ label: 'Best streak', value: '2 workdays', sub: '2 in a row now' });
    expect(by['With Weleho since'].sub).toBe('2 days, 3 shifts');
  });

  it('leaves out a one-shift busiest week', () => {
    const r = computeRecords([e('2026-10-05', '09:00', '10:00')], 8, new Date(2026, 9, 9), toRow);
    const labels = recordTiles(r).map((t) => t.label);
    expect(labels).not.toContain('Busiest week');
    expect(labels).not.toContain('Best streak');
  });
});

describe('computeRecords (mock port of records.py)', () => {
  it('matches tests/test_records.py on boundaries and streaks', () => {
    const today = new Date(2027, 1, 1);
    const r = computeRecords(
      [e('2026-12-31', '08:00', '16:00'), e('2027-01-01', '08:00', '16:00'), e('2027-01-05', '08:00', '17:00'),
        e('2027-03-01', '08:00', '20:00'), e('2027-01-06', '09:00', '09:00')],
      8,
      today,
      toRow,
    );
    expect(r.total_shifts).toBe(3);
    expect(r.best_week).toEqual({ key: '2026-W53', start: '2026-12-28', minutes: 960 });
    expect(r.best_month).toEqual({ key: '2027-01', minutes: 1020 });
    expect(r.streak).toEqual({ current: 0, best: 2 });
  });
});
