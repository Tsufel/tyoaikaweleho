// Port of records.py for the dev mock (mock.ts). tests/test_records.py is the
// spec: the same shifts as achievements count, ties go to the earliest.

import type { EntryRow, RecordsData, WorkEntry } from './types';
import { entryMinutes, fromIsoDate, toIsoDate, weekKey } from '../time';
import { isWorkday, prevWorkday } from '../holidays';

const DAY = 24 * 60;
const clock = (t: string) => {
  const m = /^(\d{1,2}):(\d{2})$/.exec(t);
  return m ? +m[1] * 60 + +m[2] : null;
};
const pad2 = (n: number) => String(n).padStart(2, '0');
const hhmm = (minute: number) => `${pad2(Math.floor((minute % DAY) / 60))}:${pad2(minute % 60)}`;
const addDays = (d: Date, n: number) => new Date(d.getFullYear(), d.getMonth(), d.getDate() + n);
const weekday = (d: Date) => (d.getDay() + 6) % 7; // Mon 0 … Sun 6

/** The key with the biggest value; sorted keys first, so a tie keeps the earliest. */
function best<K extends string>(map: Map<K, number>): K | null {
  let top: K | null = null;
  for (const k of [...map.keys()].sort()) if (top === null || map.get(k)! > map.get(top)!) top = k;
  return top;
}

export function computeRecords(
  entries: WorkEntry[],
  targetHours: number,
  today: Date,
  toRow: (e: WorkEntry) => EntryRow,
): RecordsData {
  const targetMin = Math.max(1, Number.isFinite(targetHours) && targetHours > 0 ? targetHours : 8) * 60;
  const todayIso = toIsoDate(today);
  const shifts = entries
    .map((e) => ({ e, start: clock(e.time_in), end: clock(e.time_out), d: fromIsoDate(e.date) }))
    .filter((s) => s.start !== null && s.end !== null && s.d && s.e.date <= todayIso)
    .map((s) => ({ ...s, start: s.start!, d: s.d!, mins: entryMinutes(s.e.time_in, s.e.time_out) }))
    .filter((s) => s.mins > 0)
    .sort((a, b) => (a.e.date < b.e.date ? -1 : a.e.date > b.e.date ? 1 : a.start - b.start));

  let longest: (typeof shifts)[number] | null = null;
  let earliest: (typeof shifts)[number] | null = null;
  let latest: { s: (typeof shifts)[number]; finish: number } | null = null;
  const dayMin = new Map<string, number>();
  const weekMin = new Map<string, number>();
  const weekShifts = new Map<string, number>();
  const weekStart = new Map<string, string>();
  const monthMin = new Map<string, number>();
  for (const s of shifts) {
    if (!longest || s.mins > longest.mins) longest = s;
    if (!earliest || s.start < earliest.start) earliest = s;
    const finish = s.start + s.mins;
    if (!latest || finish > latest.finish) latest = { s, finish };
    dayMin.set(s.e.date, (dayMin.get(s.e.date) ?? 0) + s.mins);
    const wk = weekKey(s.d);
    weekMin.set(wk, (weekMin.get(wk) ?? 0) + s.mins);
    weekShifts.set(wk, (weekShifts.get(wk) ?? 0) + 1);
    if (!weekStart.has(wk)) weekStart.set(wk, toIsoDate(addDays(s.d, -weekday(s.d))));
    const mk = s.e.date.slice(0, 7);
    monthMin.set(mk, (monthMin.get(mk) ?? 0) + s.mins);
  }

  // Workday streaks (achievements' streak_5 rules).
  let run = 0;
  let bestRun = 0;
  let last: string | null = null;
  for (const iso of [...dayMin.keys()].sort()) {
    const d = fromIsoDate(iso)!;
    if (!isWorkday(d)) continue;
    if (dayMin.get(iso)! >= targetMin) {
      run = last === toIsoDate(prevWorkday(d)) ? run + 1 : 1;
      last = iso;
      bestRun = Math.max(bestRun, run);
    } else {
      run = 0;
      last = null;
    }
  }
  const at = (d: Date) => (dayMin.get(toIsoDate(d)) ?? 0) >= targetMin;
  let current = 0;
  let d = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  if (!isWorkday(d) || !at(d)) d = prevWorkday(d);
  const first = shifts[0]?.d ?? null;
  while (first && d >= first && at(d)) {
    current++;
    d = prevWorkday(d);
  }

  const bd = best(dayMin);
  const bw = best(weekMin);
  const bs = best(weekShifts);
  const bm = best(monthMin);
  const midnight = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  return {
    total_shifts: shifts.length,
    first_shift_date: first ? toIsoDate(first) : null,
    days_since_first: first ? Math.round((midnight.getTime() - first.getTime()) / 86_400_000) : null,
    longest_shift: longest ? { entry: toRow(longest.e), minutes: longest.mins } : null,
    best_day: bd ? { date: bd, minutes: dayMin.get(bd)! } : null,
    best_week: bw ? { key: bw, start: weekStart.get(bw)!, minutes: weekMin.get(bw)! } : null,
    most_shifts_week: bs ? { key: bs, start: weekStart.get(bs)!, shifts: weekShifts.get(bs)! } : null,
    best_month: bm ? { key: bm, minutes: monthMin.get(bm)! } : null,
    earliest_start: earliest ? { entry: toRow(earliest.e), time: hhmm(earliest.start) } : null,
    latest_finish: latest
      ? { entry: toRow(latest.s.e), time: hhmm(latest.finish), next_day: latest.finish >= DAY }
      : null,
    streak: { current, best: bestRun },
  };
}
