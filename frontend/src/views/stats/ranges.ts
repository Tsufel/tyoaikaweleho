import type { Granularity } from '../../lib/api/types';
import { MONTHS, MONTHS_SHORT, fromIsoDate, toIsoDate } from '../../lib/time';

export type Preset = 'week' | 'month' | 'quarter' | 'year' | 'custom';

export interface DateRange {
  start: string;
  end: string;
}

export const PRESETS: { value: Preset; label: string }[] = [
  { value: 'week', label: 'This week' },
  { value: 'month', label: 'This month' },
  { value: 'quarter', label: 'Last 3 months' },
  { value: 'year', label: 'This year' },
  { value: 'custom', label: 'Custom' },
];

export const GRANULARITIES: { value: Granularity; label: string }[] = [
  { value: 'day', label: 'Day' },
  { value: 'week', label: 'Week' },
  { value: 'month', label: 'Month' },
];

/** get_stats rejects longer ranges (contract §5). */
export const MAX_RANGE_DAYS = 3700;
/** Above these spans a granularity would draw too many bars to read. */
const MAX_BUCKETS_DAYS: Record<Granularity, number> = { day: 93, week: 742, month: Infinity };

const DAY_MS = 86_400_000;

function ymd(y: number, m: number, d: number): string {
  return toIsoDate(new Date(y, m, d));
}

/** Calendar days in [start, end], inclusive (DST-safe). */
export function spanDays(r: DateRange): number {
  const a = fromIsoDate(r.start);
  const b = fromIsoDate(r.end);
  if (!a || !b) return 0;
  const ua = Date.UTC(a.getFullYear(), a.getMonth(), a.getDate());
  const ub = Date.UTC(b.getFullYear(), b.getMonth(), b.getDate());
  return Math.round((ub - ua) / DAY_MS) + 1;
}

export function addDays(iso: string, n: number): string {
  const d = fromIsoDate(iso)!;
  return toIsoDate(new Date(d.getFullYear(), d.getMonth(), d.getDate() + n));
}

/**
 * Range for a preset, `offset` periods away from the one containing `today`
 * (−1 = previous). Periods are whole: the current week/month/year includes
 * days still ahead, which stay zero.
 */
export function presetRange(preset: Exclude<Preset, 'custom'>, today: Date, offset = 0): DateRange {
  const y = today.getFullYear();
  const m = today.getMonth();
  const d = today.getDate();
  switch (preset) {
    case 'week': {
      const monday = d - ((today.getDay() + 6) % 7) + offset * 7;
      return { start: ymd(y, m, monday), end: ymd(y, m, monday + 6) };
    }
    case 'month':
      return { start: ymd(y, m + offset, 1), end: ymd(y, m + offset + 1, 0) };
    case 'quarter':
      return { start: ymd(y, m - 2 + offset * 3, 1), end: ymd(y, m + 1 + offset * 3, 0) };
    case 'year':
      return { start: ymd(y + offset, 0, 1), end: ymd(y + offset, 11, 31) };
  }
}

/** Custom ranges step by their own length. */
export function shiftRange(r: DateRange, direction: -1 | 1): DateRange {
  const n = spanDays(r) * direction;
  return { start: addDays(r.start, n), end: addDays(r.end, n) };
}

export function granularityAllowed(g: Granularity, r: DateRange): boolean {
  return spanDays(r) <= MAX_BUCKETS_DAYS[g];
}

export function defaultGranularity(preset: Preset, r: DateRange): Granularity {
  if (preset === 'week' || preset === 'month') return 'day';
  if (preset === 'quarter') return 'week';
  if (preset === 'year') return 'month';
  const n = spanDays(r);
  return n <= 45 ? 'day' : n <= 200 ? 'week' : 'month';
}

/** Keep the chosen granularity when it still fits, else fall back. */
export function fitGranularity(g: Granularity, preset: Preset, r: DateRange): Granularity {
  if (granularityAllowed(g, r)) return g;
  const d = defaultGranularity(preset, r);
  return granularityAllowed(d, r) ? d : 'month';
}

/** Error text for a custom range, or null when it can be fetched. */
export function validateRange(r: DateRange): string | null {
  const a = fromIsoDate(r.start);
  const b = fromIsoDate(r.end);
  if (!a || !b) return 'Pick a start and an end date.';
  if (b < a) return 'Pick an end date on or after the start date.';
  if (spanDays(r) > MAX_RANGE_DAYS) return 'Pick a range of ten years or less.';
  return null;
}

const dm = (d: Date) => `${d.getDate()} ${MONTHS_SHORT[d.getMonth()]}`;

/** "26 Oct – 1 Nov 2026", "1 Oct – 31 Dec 2026", "29 Dec 2025 – 4 Jan 2026", "29 Oct 2026". */
export function formatRange(r: DateRange): string {
  const a = fromIsoDate(r.start);
  const b = fromIsoDate(r.end);
  if (!a || !b) return '';
  if (r.start === r.end) return `${dm(a)} ${a.getFullYear()}`;
  if (a.getFullYear() === b.getFullYear()) return `${dm(a)} – ${dm(b)} ${b.getFullYear()}`;
  return `${dm(a)} ${a.getFullYear()} – ${dm(b)} ${b.getFullYear()}`;
}

/** Heading for the period: "This week", "Last month", "October 2026", … */
export function periodTitle(preset: Preset, offset: number, r: DateRange): string {
  const a = fromIsoDate(r.start);
  if (preset === 'custom' || !a) return 'Custom range';
  if (offset === 0) return PRESETS.find((p) => p.value === preset)!.label;
  if (offset === -1) {
    if (preset === 'week') return 'Last week';
    if (preset === 'month') return 'Last month';
    if (preset === 'year') return 'Last year';
  }
  if (preset === 'month') return `${MONTHS[a.getMonth()]} ${a.getFullYear()}`;
  if (preset === 'year') return String(a.getFullYear());
  return preset === 'week' ? 'Week' : '3 months';
}
