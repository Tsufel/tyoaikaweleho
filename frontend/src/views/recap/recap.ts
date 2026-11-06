import type { StatsData } from '../../lib/api/types';
import { formatDuration, formatMoney, fromIsoDate, isoWeek, weekKey } from '../../lib/time';
import { formatRange, presetRange, type DateRange } from '../stats/ranges';

/** localStorage key: the ISO week key of the last week recapped ("2026-W44"). */
export const RECAP_KEY = 'weleho.recapWeek';

export interface RecapWeek {
  key: string;
  week: number;
  range: DateRange;
}

/** The whole ISO week before the one holding `today`. */
export function lastWeek(today: Date): RecapWeek {
  const range = presetRange('week', today, -1);
  const monday = fromIsoDate(range.start)!;
  return { key: weekKey(monday), week: isoWeek(monday)[1], range };
}

/** Browser storage can be missing or throw (private mode, blocked site data). */
export function readShownWeek(): string | null {
  try {
    return localStorage.getItem(RECAP_KEY);
  } catch {
    return null;
  }
}

export function writeShownWeek(key: string): void {
  try {
    localStorage.setItem(RECAP_KEY, key);
  } catch {
    // Not remembered: the recap may show once more, which is harmless.
  }
}

export interface RecapStat {
  label: string;
  value: string;
}

export interface Recap {
  title: string;
  range: string;
  stats: RecapStat[];
  /** One plain line under the figures, or '' for none. */
  note: string;
}

const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;

/** The card's text for one week of get_stats, or null when nothing was worked. */
export function buildRecap(week: RecapWeek, data: Pick<StatsData, 'totals' | 'longest'>, payRate: number): Recap | null {
  const t = data.totals;
  if (!(t.shifts > 0) || !(t.minutes > 0)) return null;
  const stats: RecapStat[] = [
    { label: 'Worked', value: formatDuration(t.minutes) },
    { label: 'Shifts', value: String(t.shifts) },
    { label: 'Days', value: String(t.worked_days) },
  ];
  if (payRate > 0) stats.push({ label: 'Earned', value: formatMoney(t.earnings) });
  const longest = data.longest;
  const note =
    longest && t.shifts > 1
      ? `Longest shift ${formatDuration(longest.minutes)}, on ${dayName(longest.entry.date)}.`
      : `${plural(t.shifts, 'shift', 'shifts')} done. Nice one.`;
  return { title: `Week ${week.week} in review`, range: formatRange(week.range), stats, note };
}

const DAY_NAMES = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];

function dayName(iso: string): string {
  const d = fromIsoDate(iso);
  return d ? DAY_NAMES[d.getDay()] : iso;
}
