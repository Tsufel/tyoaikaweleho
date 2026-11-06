// The Hall of fame tiles (RecordsPanel) from get_records (docs/V2_UI_API.md §10.3).

import type { RecordsData } from '../../lib/api/types';
import { formatDuration, monthLabel } from '../../lib/time';
import { shortDate } from './tiers';

export interface RecordTile {
  label: string;
  value: string;
  sub: string;
}

const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;

/** One tile per record that exists, in a fixed order; none before the first shift. */
export function recordTiles(r: RecordsData): RecordTile[] {
  const out: RecordTile[] = [];
  const add = (label: string, value: string, sub = '') => out.push({ label, value, sub });
  if (r.longest_shift) {
    const e = r.longest_shift.entry;
    add('Longest shift', formatDuration(r.longest_shift.minutes), [shortDate(e.date), e.job_shift].filter(Boolean).join(' · '));
  }
  if (r.best_day) add('Best day', formatDuration(r.best_day.minutes), shortDate(r.best_day.date));
  if (r.best_week) {
    const w = r.best_week.key.split('-W')[1] ?? r.best_week.key;
    add('Best week', formatDuration(r.best_week.minutes), `Week ${Number(w)}, from ${shortDate(r.best_week.start)}`);
  }
  if (r.best_month) {
    const [y, m] = r.best_month.key.split('-').map(Number);
    add('Best month', formatDuration(r.best_month.minutes), y && m ? monthLabel(y, m) : r.best_month.key);
  }
  if (r.most_shifts_week && r.most_shifts_week.shifts > 1) {
    const w = r.most_shifts_week.key.split('-W')[1] ?? r.most_shifts_week.key;
    add('Busiest week', plural(r.most_shifts_week.shifts, 'shift', 'shifts'), `Week ${Number(w)}, from ${shortDate(r.most_shifts_week.start)}`);
  }
  if (r.earliest_start) add('Earliest start', r.earliest_start.time, shortDate(r.earliest_start.entry.date));
  if (r.latest_finish) {
    const f = r.latest_finish;
    add('Latest finish', f.next_day ? `${f.time} +1` : f.time, shortDate(f.entry.date) + (f.next_day ? ', next morning' : ''));
  }
  if (r.streak.best > 0) {
    add('Best streak', plural(r.streak.best, 'workday', 'workdays'),
      r.streak.current > 0 ? `${r.streak.current} in a row now` : 'At target, in a row');
  }
  if (r.first_shift_date && r.days_since_first !== null) {
    add('With Weleho since', shortDate(r.first_shift_date),
      `${plural(r.days_since_first, 'day', 'days')}, ${plural(r.total_shifts, 'shift', 'shifts')}`);
  }
  return out;
}
