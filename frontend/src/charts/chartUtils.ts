import { scaleLinear } from 'd3-scale';
import type { Granularity, ShiftTotal, StatsBucket } from '../lib/api/types';
import { fromIsoDate } from '../lib/time';

/** Categorical slots (validated for CVD/contrast on both glass surfaces); defined in StatsView. */
export const SERIES_SLOTS = 5;
export const NO_SHIFT_LABEL = 'No job / shift';
export const OTHER_LABEL = 'Other';

/** Y domain + gridline ticks for hours; always shows the target. */
export function hourScale(maxHours: number, target: number, height: number) {
  const top = Math.max(maxHours, target, 1) * 1.08;
  const y = scaleLinear().domain([0, top]).range([height, 0]).nice(4);
  return { y, ticks: y.ticks(4) };
}

export function moneyScale(max: number, height: number) {
  const y = scaleLinear().domain([0, Math.max(max, 1) * 1.08]).range([height, 0]).nice(4);
  return { y, ticks: y.ticks(4) };
}

/** Advance of one character in the 11px mono axis font (0.6em, with room to spare). */
export const AXIS_CHAR_PX = 6.8;
/** Clear space between two neighbouring axis labels. */
export const AXIS_LABEL_GAP = 10;
const MONTH_SHORT = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

/** Two centred labels `dist` px apart do not touch. */
function labelsFit(a: string, b: string, dist: number, charPx: number): boolean {
  return ((a.length + b.length) * charPx) / 2 + AXIS_LABEL_GAP <= dist;
}

/**
 * Category-axis labels thinned so they never collide: every `step`th one is shown, the rest are ''.
 * Months read "Jan", with the year on the first shown label and wherever it changes.
 * `slot` is the distance between neighbouring category centres in px.
 */
export function axisLabels(
  buckets: StatsBucket[],
  granularity: Granularity | undefined,
  slot: number,
  charPx = AXIS_CHAR_PX,
): { step: number; labels: string[] } {
  const n = buckets.length;
  if (!n) return { step: 1, labels: [] };
  const text = (s: number): string[] => {
    const out = buckets.map(() => '');
    let year: number | null = null;
    for (let i = 0; i < n; i += s) {
      const d = granularity === 'month' ? fromIsoDate(buckets[i].start) : null;
      if (!d) {
        out[i] = buckets[i].label;
        continue;
      }
      const m = MONTH_SHORT[d.getMonth()];
      out[i] = d.getFullYear() === year ? m : `${m} ${d.getFullYear()}`;
      year = d.getFullYear();
    }
    return out;
  };
  if (!(slot > 0)) return { step: n, labels: text(n) };
  // no step below what the shortest labels need
  const shortest = Math.min(...buckets.map((b) => (granularity === 'month' ? 3 : b.label.length)));
  const s0 = Math.max(1, Math.floor((shortest * charPx + AXIS_LABEL_GAP) / slot));
  for (let s = s0; s < n; s++) {
    const labels = text(s);
    let fits = true;
    for (let i = s; i < n && fits; i += s) fits = labelsFit(labels[i - s], labels[i], s * slot, charPx);
    if (fits) return { step: s, labels };
  }
  return { step: n, labels: text(n) };
}

/**
 * The labels to draw: the thinned set, plus the hovered category in full, with any shown
 * label it would run into hidden.
 */
export function shownLabels(
  buckets: StatsBucket[],
  labels: string[],
  active: number | null,
  slot: number,
  charPx = AXIS_CHAR_PX,
): string[] {
  if (active === null || active < 0 || active >= buckets.length) return labels;
  const on = buckets[active].label;
  return labels.map((l, i) => {
    if (i === active) return on;
    if (!l) return '';
    return labelsFit(l, on, Math.abs(i - active) * slot, charPx) ? l : '';
  });
}

/** Bar outline: rounded data end (top), square at the baseline. */
export function barPath(x: number, y: number, w: number, h: number, r = 4): string {
  if (h <= 0 || w <= 0) return '';
  const rr = Math.min(r, w / 2, h);
  const b = y + h;
  return (
    `M${x},${b}V${y + rr}Q${x},${y} ${x + rr},${y}H${x + w - rr}` +
    `Q${x + w},${y} ${x + w},${y + rr}V${b}Z`
  );
}

/** Mon–Fri days in [a, b]. */
export function weekdaysBetween(a: Date, b: Date): number {
  let n = 0;
  const d = new Date(a.getFullYear(), a.getMonth(), a.getDate());
  while (d <= b) {
    const wd = d.getDay();
    if (wd !== 0 && wd !== 6) n++;
    d.setDate(d.getDate() + 1);
  }
  return n;
}

/**
 * Target hours for each bucket. Days use the daily target as-is; weeks and
 * months use target × weekdays of the bucket that fall inside the range.
 */
export function bucketTargets(
  buckets: StatsBucket[],
  g: Granularity,
  rangeStart: string,
  rangeEnd: string,
  targetHours: number,
): number[] {
  if (g === 'day') return buckets.map(() => targetHours);
  const rs = fromIsoDate(rangeStart)!;
  const re = fromIsoDate(rangeEnd)!;
  return buckets.map((b) => {
    const s = fromIsoDate(b.start)!;
    const e = g === 'week' ? new Date(s.getFullYear(), s.getMonth(), s.getDate() + 6) : new Date(s.getFullYear(), s.getMonth() + 1, 0);
    const from = s < rs ? rs : s;
    const to = e > re ? re : e;
    return from > to ? 0 : weekdaysBetween(from, to) * targetHours;
  });
}

export interface Slice {
  key: string;
  label: string;
  minutes: number;
  earnings: number;
  shifts: number;
  /** 0..SERIES_SLOTS-1, or -1 for the neutral "Other". */
  slot: number;
  share: number;
}

/**
 * Donut slices: the biggest `SERIES_SLOTS` jobs by `metric`, the rest folded into "Other".
 * Colour follows the job (its place in the saved job list), not its rank.
 */
export function shiftSlices(rows: ShiftTotal[], knownShifts: string[], metric: 'hours' | 'shifts' = 'hours'): Slice[] {
  const value = (r: { minutes: number; shifts: number }) => (metric === 'shifts' ? r.shifts : r.minutes);
  const total = rows.reduce((s, r) => s + value(r), 0);
  const sorted = rows
    .filter((r) => value(r) > 0)
    .sort((a, b) => value(b) - value(a) || b.minutes - a.minutes || a.job_shift.localeCompare(b.job_shift));
  const tooMany = sorted.length > SERIES_SLOTS;
  const shown = tooMany ? sorted.slice(0, SERIES_SLOTS - 1) : sorted;
  const rest = tooMany ? sorted.slice(SERIES_SLOTS - 1) : [];

  const order = (name: string) => {
    const i = knownShifts.indexOf(name);
    return i < 0 ? Number.MAX_SAFE_INTEGER : i;
  };
  const byIdentity = [...shown].sort((a, b) => order(a.job_shift) - order(b.job_shift) || a.job_shift.localeCompare(b.job_shift));
  const used = new Set<number>();
  const slotOf = new Map<string, number>();
  for (const r of byIdentity) {
    const o = order(r.job_shift);
    let s = o === Number.MAX_SAFE_INTEGER ? -1 : o % SERIES_SLOTS;
    if (s < 0 || used.has(s)) {
      s = [...Array(SERIES_SLOTS).keys()].find((k) => !used.has(k))!;
    }
    used.add(s);
    slotOf.set(r.job_shift, s);
  }

  const share = (m: number) => (total > 0 ? m / total : 0);
  const out: Slice[] = shown.map((r) => ({
    key: `job:${r.job_shift}`,
    label: r.job_shift.trim() || NO_SHIFT_LABEL,
    minutes: r.minutes,
    earnings: r.earnings,
    shifts: r.shifts,
    slot: slotOf.get(r.job_shift)!,
    share: share(value(r)),
  }));
  if (rest.length) {
    const m = rest.reduce((s, r) => s + r.minutes, 0);
    const n = rest.reduce((s, r) => s + r.shifts, 0);
    out.push({
      key: 'other',
      label: `${OTHER_LABEL} (${rest.length})`,
      minutes: m,
      earnings: Math.round(rest.reduce((s, r) => s + r.earnings, 0) * 100) / 100,
      shifts: n,
      slot: -1,
      share: share(metric === 'shifts' ? n : m),
    });
  }
  return out;
}

/** Running total, rounded to cents at each step. */
export function cumulative(values: number[]): number[] {
  let acc = 0;
  return values.map((v) => (acc = Math.round((acc + v) * 100) / 100));
}

/** Resize a tweened array to `n` items, keeping what overlaps (new items start at 0). */
export function resize(values: number[], n: number): number[] {
  return Array.from({ length: n }, (_, i) => values[i] ?? 0);
}

/** "7.5h", "40h", "0h" for axes. */
export function axisHours(h: number): string {
  return `${Math.round(h * 10) / 10}h`;
}

export function axisMoney(x: number): string {
  if (x >= 10_000) return `€${Math.round(x / 1000)}k`;
  if (x >= 1000) return `€${(Math.round(x / 100) / 10).toString()}k`;
  return `€${Math.round(x)}`;
}

/** "42%" with one decimal under 10 %. */
export function percent(share: number): string {
  const p = share * 100;
  if (p > 0 && p < 10) return `${(Math.round(p * 10) / 10).toString()}%`;
  return `${Math.round(p)}%`;
}

/** Arrow-key navigation over n items; null when the key is not a nav key. */
export function stepIndex(key: string, i: number | null, n: number, page = 7): number | null {
  if (n <= 0) return null;
  const cur = i ?? -1;
  switch (key) {
    case 'ArrowRight':
    case 'ArrowDown':
      return Math.min(n - 1, cur + 1);
    case 'ArrowLeft':
    case 'ArrowUp':
      return cur < 0 ? n - 1 : Math.max(0, cur - 1);
    case 'Home':
      return 0;
    case 'End':
      return n - 1;
    case 'PageDown':
      return Math.min(n - 1, Math.max(0, cur) + page);
    case 'PageUp':
      return Math.max(0, Math.max(0, cur) - page);
  }
  return null;
}

// ── earnings running total ────────────────────────────────────────

const dayNumber = (iso: string): number | null => {
  const d = fromIsoDate(iso);
  return d ? Math.round(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()) / 86_400_000) : null;
};

export interface EarningsModel {
  /** Running total per bucket. */
  totals: number[];
  /** Last bucket drawn as earned (today's, or a later one with shifts); -1 before the period starts. */
  elapsed: number;
  /** The period is over: comparisons are between whole periods. */
  over: boolean;
  /** Period-end total at the pace so far; null when the period is over, barely begun or has later shifts. */
  projected: number | null;
  /** Earned so far: up to today (or the latest shift dated ahead), all of it once the period is over. */
  now: number;
  /** Previous period's running total, matched by position (day 1 with day 1) and ending on its own
   *  total; null when it earned nothing. */
  previous: number[] | null;
  /** Previous period's total at the same point as `now` (all of it once this one is over). */
  previousAt: number | null;
}

/** Day-level buckets of both periods, so "at this point" is exact when the chart groups by week or month. */
export interface DailyEarnings {
  current: StatsBucket[];
  previous: StatsBucket[] | null;
}

/** A pace needs this much of the period behind it: 2 days of a week, 6 of a month. */
export function paceReady(elapsedDays: number, totalDays: number): boolean {
  return elapsedDays >= Math.max(2, Math.ceil(totalDays * 0.2)) && elapsedDays < totalDays;
}

/**
 * What the earnings card draws: the line stops at today (days ahead are not
 * earned yet), a straight-line pace to the period end, and the previous
 * period for comparison.
 */
export function earningsModel(
  buckets: StatsBucket[],
  start: string,
  end: string,
  today: string,
  prevBuckets: StatsBucket[] | null = null,
  /** First stored shift: the pace counts from there when it falls inside the period. */
  since: string | null = null,
  /** Day-level buckets; without them a week or month bucket counts as a whole. */
  daily: DailyEarnings | null = null,
): EarningsModel {
  const totals = cumulative(buckets.map((b) => b.earnings));
  const n = buckets.length;
  const over = today > end;
  // the first week or month bucket can start before the range itself
  const started = today >= start;
  let todayIdx = -1;
  if (over) todayIdx = n - 1;
  else if (started) for (let i = 0; i < n && buckets[i].start <= today; i++) todayIdx = i;
  let lastEarn = -1;
  buckets.forEach((b, i) => {
    if (b.earnings > 0) lastEarn = i;
  });
  const elapsed = Math.max(todayIdx, lastEarn);

  const first = dayNumber(start);
  const e = dayNumber(end);
  const t = dayNumber(today);
  const r2 = (v: number) => Math.round(v * 100) / 100;

  // "this point": today, or the latest shift dated ahead of it
  let now = elapsed >= 0 ? totals[elapsed] : 0;
  let cut: number | null = null;
  let ahead = lastEarn > todayIdx;
  if (over) now = totals[n - 1] ?? 0;
  else if (daily && first !== null && t !== null) {
    let last: number | null = null;
    for (const b of daily.current) {
      const d = dayNumber(b.start);
      if (d !== null && b.earnings > 0 && (last === null || d > last)) last = d;
    }
    ahead = last !== null && last > t;
    cut = ahead && last !== null ? last : t;
    let sum = 0;
    for (const b of daily.current) {
      const d = dayNumber(b.start);
      if (d !== null && d >= first && d <= cut) sum += b.earnings;
    }
    now = r2(sum);
  }

  let projected: number | null = null;
  const from = since ? dayNumber(since) : null;
  const s = first !== null && from !== null && from > first ? from : first;
  if (s !== null && e !== null && t !== null && !over && t >= s && !ahead && now > 0) {
    const done = t - s + 1;
    if (paceReady(done, e - s + 1)) projected = r2(now + (now * (e - t)) / done);
  }

  let previous: number[] | null = null;
  let previousAt: number | null = null;
  if (prevBuckets?.length && n) {
    const pt = cumulative(prevBuckets.map((b) => b.earnings));
    const full = pt[pt.length - 1];
    if (full > 0) {
      previous = Array.from({ length: n }, (_, i) => pt[Math.min(i, pt.length - 1)]);
      // a longer period before still ends on its total, the figure the text compares against
      previous[n - 1] = full;
      if (over) previousAt = full;
      else if (cut !== null && first !== null && daily?.previous?.length) {
        const p0 = dayNumber(daily.previous[0].start);
        let sum = 0;
        for (const b of daily.previous) {
          const d = dayNumber(b.start);
          if (p0 !== null && d !== null && d - p0 <= cut - first) sum += b.earnings;
        }
        previousAt = r2(sum);
      } else if (elapsed >= 0) previousAt = previous[elapsed];
    }
  }
  return { totals, elapsed, over, projected, now, previous, previousAt };
}

/** Pace line value at bucket `i` (past `elapsed`), straight from today's total to the projection. */
export function paceAt(i: number, elapsed: number, n: number, from: number, to: number): number {
  if (i <= elapsed || n - 1 <= elapsed) return from;
  return from + ((to - from) * (i - elapsed)) / (n - 1 - elapsed);
}

// ── KPI comparison ────────────────────────────────────────────────

export interface PeriodTotals {
  minutes: number;
  earnings: number;
  shifts: number;
  worked_days: number;
}

/**
 * The previous period's totals at the same point as this one, the way the earnings card
 * compares: all of them once this period is over, else up to the same day of the period as
 * today (or the latest shift dated ahead of it). `daily` holds day-level buckets of both
 * periods. Null before the period starts, or when a running period has no day-level data.
 */
export function previousTotalsAt(
  start: string,
  end: string,
  today: string,
  daily: DailyEarnings | null,
  previousTotals: PeriodTotals,
): PeriodTotals | null {
  if (today > end) return previousTotals;
  if (today < start) return null;
  const first = dayNumber(start);
  const t = dayNumber(today);
  if (first === null || t === null || !daily?.previous?.length) return null;
  let cut = t;
  for (const b of daily.current) {
    const d = dayNumber(b.start);
    if (d !== null && d > cut && (b.shifts > 0 || b.minutes > 0 || b.earnings > 0)) cut = d;
  }
  const p0 = dayNumber(daily.previous[0].start);
  if (p0 === null) return null;
  const out: PeriodTotals = { minutes: 0, earnings: 0, shifts: 0, worked_days: 0 };
  for (const b of daily.previous) {
    const d = dayNumber(b.start);
    if (d === null || d - p0 > cut - first) continue;
    out.minutes += b.minutes;
    out.earnings += b.earnings;
    out.shifts += b.shifts;
    if (b.minutes > 0) out.worked_days += 1;
  }
  out.earnings = Math.round(out.earnings * 100) / 100;
  return out;
}

export interface KpiDelta {
  tone: 'up' | 'down' | 'even';
  /** Short, unsigned: "6h 30m". */
  text: string;
  /** Full sentence for the tooltip and screen readers. */
  hint: string;
}

/** Change from `before` to `now`, written with `fmt`; `who` is "October", `when` " at this point" or "". */
export function kpiDelta(now: number, before: number, fmt: (n: number) => string, who: string, when: string): KpiDelta {
  const diff = Math.round((now - before) * 100) / 100;
  if (diff === 0) return { tone: 'even', text: 'Same', hint: `Same as ${who}${when}` };
  const text = fmt(Math.abs(diff));
  return {
    tone: diff > 0 ? 'up' : 'down',
    text,
    hint: `${diff > 0 ? '+' : '−'}${text} vs ${who}${when}`,
  };
}
