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

/** Show every `step`th category label so labels never collide. */
export function labelStep(count: number, plotWidth: number, minLabelPx = 44): number {
  if (count <= 0 || plotWidth <= 0) return 1;
  return Math.max(1, Math.ceil((count * minLabelPx) / plotWidth));
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
 * Donut slices: the biggest `SERIES_SLOTS` jobs, the rest folded into "Other".
 * Colour follows the job (its place in the saved job list), not its rank.
 */
export function shiftSlices(rows: ShiftTotal[], knownShifts: string[]): Slice[] {
  const total = rows.reduce((s, r) => s + r.minutes, 0);
  const sorted = rows.filter((r) => r.minutes > 0).sort((a, b) => b.minutes - a.minutes || a.job_shift.localeCompare(b.job_shift));
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
    share: share(r.minutes),
  }));
  if (rest.length) {
    const m = rest.reduce((s, r) => s + r.minutes, 0);
    out.push({
      key: 'other',
      label: `${OTHER_LABEL} (${rest.length})`,
      minutes: m,
      earnings: Math.round(rest.reduce((s, r) => s + r.earnings, 0) * 100) / 100,
      shifts: rest.reduce((s, r) => s + r.shifts, 0),
      slot: -1,
      share: share(m),
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
