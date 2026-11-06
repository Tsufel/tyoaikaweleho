import type { EntryDraft, EntryRow, MonthData, OverlapRef, WeekGroup } from '../../lib/api/types';
import {
  addMonths,
  formatDuration,
  formatHM,
  formatMoney,
  fromIsoDate,
  monthLabel,
  parseDateInput,
  parseTimeInput,
  strftime,
  toIsoDate,
} from '../../lib/time';

export type TableRow =
  | { kind: 'entry'; key: string; entry: EntryRow; index: number }
  | { kind: 'week'; key: string; week: WeekGroup; index: number };

/** Entries in display order with a "Week N total" row after each ISO week. */
export function buildRows(m: MonthData | null): TableRow[] {
  if (!m) return [];
  const weeks = new Map(m.weeks.map((w) => [w.key, w]));
  const rows: TableRow[] = [];
  m.entries.forEach((entry, i) => {
    rows.push({ kind: 'entry', key: entry.id, entry, index: i });
    const next = m.entries[i + 1];
    if (!next || next.week_key !== entry.week_key) {
      const w = weeks.get(entry.week_key);
      if (w) rows.push({ kind: 'week', key: `week-${w.key}`, week: w, index: i });
    }
  });
  return rows;
}

/** True when the ISO week reaches into the month before or after `view`,
 * so its total only counts this month's days. */
export function weekCrossesMonth(w: WeekGroup, view: { year: number; month: number }): boolean {
  const monIso = parseDateInput(`${w.iso_year}-W${String(w.week).padStart(2, '0')}`);
  const mon = monIso ? fromIsoDate(monIso) : null;
  if (!mon) return false;
  const sun = new Date(mon.getFullYear(), mon.getMonth(), mon.getDate() + 6);
  const inView = (d: Date) => d.getFullYear() === view.year && d.getMonth() + 1 === view.month;
  return !inView(mon) || !inView(sun);
}

/** "Week 39 total 15:30 (€232.50)"; with `view`, a week that spills into
 * the month before or after says "(this month)". */
export const weekTotalText = (w: WeekGroup, view?: { year: number; month: number }) =>
  `Week ${w.week} total${view && weekCrossesMonth(w, view) ? ' (this month)' : ''} ${formatHM(w.minutes)} (${formatMoney(w.earnings)})`;

export const monthTotalText = (m: MonthData | null) =>
  `Total: ${formatHM(m?.total_minutes ?? 0)} (${formatMoney(m?.earnings ?? 0)})`;

/** Empty-month line: START only records today, so other months point at Add entry. */
export const emptyText = (label: string, isCurrentMonth = true) =>
  isCurrentMonth
    ? `No shifts in ${label}. Press START or + Add entry.`
    : `No shifts in ${label}. Add one by hand with + Add entry.`;
/** Second line under the empty-month wizard. */
export const EMPTY_HINT = 'The weleho is standing by — your hours land here once you clock out.';

export const isSameMonth = (view: { year: number; month: number }, today: Date) =>
  view.year === today.getFullYear() && view.month === today.getMonth() + 1;

export type EditField = 'time_in' | 'time_out';

/** Editor text without a pasted " +1" (first word only, like the v1.3 editor). */
export function editorValue(text: string): string {
  return text.trim().split(/\s+/)[0] ?? '';
}

/** Parsed editor value; null = not a time (an empty cell too, like v1.3). */
export function parseEditor(_field: EditField, text: string): string | null {
  return parseTimeInput(editorValue(text));
}

export type CloseDecision =
  /** Strict commit of an invalid value: keep open, red, select all. */
  | { action: 'mark-invalid' }
  /** Close without saving; `note` = status toast. */
  | { action: 'close'; note?: string }
  | { action: 'save'; value: string };

/** v1.3 `_close_editor`: what to do with the editor text. */
export function decideClose(field: EditField, text: string, original: string, commit: boolean, strict: boolean): CloseDecision {
  if (!commit) return { action: 'close' };
  const parsed = parseEditor(field, text);
  if (parsed === null) {
    if (editorValue(text) === original) return { action: 'close' };
    if (strict) return { action: 'mark-invalid' };
    return { action: 'close', note: 'Invalid time, not saved' };
  }
  if (parsed === original) return { action: 'close' };
  return { action: 'save', value: parsed };
}

const plural = (n: number, one: string, many: string) => (n === 1 ? one : many);

/** "Import complete" text of v1.3 `_import_excel`. */
export function importSummary(r: {
  imported: number;
  skipped: number;
  files: number;
  errors: string[];
  notes?: string[];
}): string {
  let msg = `Imported ${r.imported} ${plural(r.imported, 'entry', 'entries')} from ${r.files} ${plural(r.files, 'file', 'files')}.`;
  if (r.skipped) msg += `\n${r.skipped} ${plural(r.skipped, 'duplicate', 'duplicates')} skipped.`;
  if (r.notes?.length) msg += '\n\n' + r.notes.join('\n');
  if (r.errors.length) msg += '\n\nErrors:\n' + r.errors.join('\n');
  return msg;
}

export const MIN_YEAR = 1900;
export const MAX_YEAR = 9999;

/** MonthPickerDialog stepping: ↑/↓ ±1 month, PgUp/PgDn ±1 year. null = key not handled. */
export function pickerStep(key: string): number | null {
  switch (key) {
    case 'ArrowUp':
      return -1;
    case 'ArrowDown':
      return 1;
    case 'PageUp':
      return -12;
    case 'PageDown':
      return 12;
    default:
      return null;
  }
}

/** Step within 1900–9999; out of range keeps the current month. */
export function stepMonth(year: number, month: number, delta: number): { year: number; month: number } {
  const n = addMonths(year, month, delta);
  return n.year < MIN_YEAR || n.year > MAX_YEAR ? { year, month } : n;
}

/** Year field text → year, or null outside 1900–9999. */
export function parseYear(text: string): number | null {
  const t = text.trim();
  if (!/^\d{1,4}$/.test(t)) return null;
  const y = Number(t);
  return y >= MIN_YEAR && y <= MAX_YEAR ? y : null;
}

/** Selection after ↑/↓ in the table. */
export function moveSelection(ids: string[], current: string | null, delta: number): string | null {
  if (!ids.length) return null;
  const i = current ? ids.indexOf(current) : -1;
  if (i < 0) return delta > 0 ? ids[0] : ids[ids.length - 1];
  return ids[Math.max(0, Math.min(ids.length - 1, i + delta))];
}

/** Through the 5th the timesheet due is usually last month's. */
export const EARLY_EXPORT_DAYS = 5;

/** Last month, when Export is pressed on the current month early in it
 * (the 1st–5th) — the month to offer first. Null otherwise. */
export function earlyExportMonth(
  view: { year: number; month: number },
  today: Date,
): { year: number; month: number } | null {
  if (today.getDate() > EARLY_EXPORT_DAYS) return null;
  if (view.year !== today.getFullYear() || view.month !== today.getMonth() + 1) return null;
  return addMonths(view.year, view.month, -1);
}

export interface RangeExport {
  id: string;
  label: string;
  start: string;
  end: string;
  kind: 'xlsx' | 'csv';
}

/** The "More exports" presets for the viewed month: the month as CSV and
 * the whole year as CSV or a Simple workbook. */
export function rangeExports(view: { year: number; month: number }): RangeExport[] {
  const { year, month } = view;
  const mm = String(month).padStart(2, '0');
  const last = new Date(year, month, 0).getDate();
  return [
    { id: 'month-csv', label: `${monthLabel(year, month)} as CSV…`, start: `${year}-${mm}-01`, end: `${year}-${mm}-${last}`, kind: 'csv' },
    { id: 'year-csv', label: `All of ${year} as CSV…`, start: `${year}-01-01`, end: `${year}-12-31`, kind: 'csv' },
    { id: 'year-xlsx', label: `All of ${year} as one sheet…`, start: `${year}-01-01`, end: `${year}-12-31`, kind: 'xlsx' },
  ];
}

// ── New / duplicate entry drafts ─────────────────────────────────

const pad2 = (n: number) => String(n).padStart(2, '0');

/** "HH:MM" plus whole minutes, wrapping past midnight. */
export function addMinutesToTime(t: string, minutes: number): string {
  const [h, m] = t.split(':').map(Number);
  const total = (((h * 60 + m + Math.round(minutes)) % 1440) + 1440) % 1440;
  return `${pad2(Math.floor(total / 60))}:${pad2(total % 60)}`;
}

/** Defaults of a new entry: Time Out = start + the Daily target (Settings),
 * so 7.5 h days get 09:00–16:30. An unusable target falls back to 8 h. */
export function newEntryDraft(o: { date: string; startTime: string; targetHours: number; job: string }): EntryDraft {
  const start = parseTimeInput(o.startTime);
  const t = o.targetHours;
  const hours = Number.isFinite(t) && t >= 1 && t < 24 ? t : 8;
  return {
    date: o.date,
    job_shift: o.job,
    time_in: o.startTime,
    time_out: start ? addMinutesToTime(start, hours * 60) : '',
  };
}

/** The first day after `iso` that has no entry in `taken` (ISO dates). */
export function nextFreeDate(iso: string, taken: Iterable<string>): string {
  const d = fromIsoDate(iso);
  if (!d) return iso;
  const used = new Set(taken);
  const day = (i: number) => toIsoDate(new Date(d.getFullYear(), d.getMonth(), d.getDate() + i));
  for (let i = 1; i <= 366; i++) if (!used.has(day(i))) return day(i);
  return day(1);
}

/** A copy of `e` without an id, on the next day that has no shift. */
export function duplicateDraft(
  e: Pick<EntryRow, 'date' | 'job_shift' | 'time_in' | 'time_out'>,
  takenDates: Iterable<string>,
): EntryDraft {
  return { date: nextFreeDate(e.date, takenDates), job_shift: e.job_shift, time_in: e.time_in, time_out: e.time_out };
}

/** True when the modal's fields differ from `init`, after normalising
 * ("9" = "09:00", "23.9.2026" = "2026-09-23", outer spaces ignored). */
export function draftChanged(init: EntryDraft, now: EntryDraft, today: Date = new Date()): boolean {
  const date = (s: string) => parseDateInput(s, today) ?? s.trim();
  const time = (s: string) => parseTimeInput(s) ?? s.trim();
  return (
    date(now.date) !== date(init.date) ||
    now.job_shift.trim() !== init.job_shift.trim() ||
    time(now.time_in) !== time(init.time_in) ||
    time(now.time_out) !== time(init.time_out)
  );
}

/** Soft note under the modal's date: catches a typoed year, a future date,
 * or a date that saves outside the month on screen. Null = nothing to say. */
export function dateHint(iso: string | null, today: Date, view: { year: number; month: number }): string | null {
  const d = iso ? fromIsoDate(iso) : null;
  if (!d) return null;
  const t = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  const days = Math.round((d.getTime() - t.getTime()) / 86_400_000);
  const years = Math.max(1, Math.abs(d.getFullYear() - t.getFullYear()));
  const n = `${years} ${plural(years, 'year', 'years')}`;
  if (days > 366) return `That's ${n} from now. Time traveller? Check the year.`;
  if (days < -366) return `That's ${n} ago. Check the year.`;
  const other = d.getFullYear() !== view.year || d.getMonth() + 1 !== view.month;
  const where = other ? `Saves to ${monthLabel(d.getFullYear(), d.getMonth() + 1)}` : '';
  if (days > 0) return where ? `${where}, which is in the future.` : "That's in the future.";
  return where ? `${where}.` : null;
}

// ── Month summary, filter, copy as text ──────────────────────────

export interface MonthSummary {
  shifts: number;
  /** Distinct dates with a shift. */
  days: number;
  /** Average of the finished shifts; null when none is finished. */
  avgMinutes: number | null;
}

export function monthSummary(entries: EntryRow[]): MonthSummary {
  const closed = entries.filter((e) => e.minutes !== null);
  const sum = closed.reduce((a, e) => a + (e.minutes ?? 0), 0);
  return {
    shifts: entries.length,
    days: new Set(entries.map((e) => e.date)).size,
    avgMinutes: closed.length ? Math.round(sum / closed.length) : null,
  };
}

/** "12 shifts · 9 days · avg 7:12" ('' for none). */
export function summaryText(s: MonthSummary): string {
  if (!s.shifts) return '';
  const parts = [`${s.shifts} ${plural(s.shifts, 'shift', 'shifts')}`, `${s.days} ${plural(s.days, 'day', 'days')}`];
  if (s.avgMinutes !== null) parts.push(`avg ${formatHM(s.avgMinutes)}`);
  return parts.join(' · ');
}

export interface EntryFilter {
  /** Exact job_shift, or null for every job. */
  job: string | null;
  /** Case-insensitive text in the date, job or times. */
  text: string;
}

export const NO_FILTER: EntryFilter = { job: null, text: '' };
export const isFiltering = (f: EntryFilter) => f.job !== null || f.text.trim() !== '';

/** Distinct job names in the month, most used first (ties A–Z). */
export function jobsInMonth(m: MonthData | null): string[] {
  const n = new Map<string, number>();
  for (const e of m?.entries ?? []) if (e.job_shift) n.set(e.job_shift, (n.get(e.job_shift) ?? 0) + 1);
  return [...n].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0])).map(([j]) => j);
}

const money2 = (x: number) => Math.round(x * 100) / 100;

/** The month with only the matching rows; weeks and totals are recomputed
 * from them (earnings at the month's pay rate, like list_month). */
export function filterMonth(m: MonthData, f: EntryFilter): MonthData {
  if (!isFiltering(f)) return m;
  const q = f.text.trim().toLowerCase();
  const entries = m.entries.filter((e) => {
    if (f.job !== null && e.job_shift !== f.job) return false;
    if (!q) return true;
    return [e.date, e.display_date, e.job_shift, e.time_in, e.time_out].some((s) => (s ?? '').toLowerCase().includes(q));
  });
  const byId = new Map(entries.map((e) => [e.id, e]));
  const weeks = m.weeks
    .map((w) => {
      const ids = w.entry_ids.filter((id) => byId.has(id));
      const minutes = ids.reduce((a, id) => a + (byId.get(id)?.minutes ?? 0), 0);
      return { ...w, entry_ids: ids, minutes, earnings: money2((minutes / 60) * m.pay_rate) };
    })
    .filter((w) => w.entry_ids.length);
  const total = entries.reduce((a, e) => a + (e.minutes ?? 0), 0);
  return { ...m, entries, weeks, total_minutes: total, earnings: money2((total / 60) * m.pay_rate) };
}

/** What the filter is showing: the job, or the quoted search text. */
export function filterName(f: EntryFilter): string {
  if (f.job !== null) return f.job || 'no job';
  return `“${f.text.trim()}”`;
}

/** Footer label: "Total:" or, filtered, "Total (Sales):". */
export const filterTotalLabel = (f: EntryFilter) => (isFiltering(f) ? `Total (${filterName(f)}):` : 'Total:');

/** "Tue 23 Sep": the table's date without the year the month header already shows. */
export function shortDate(iso: string): string {
  const d = fromIsoDate(iso);
  return d ? strftime(d, '%a %d %b') : iso;
}

/** Saturday or Sunday. */
/** The public holiday's name on *iso* (list_month's `holidays`), or null. */
export function holidayOn(m: MonthData | null, iso: string): string | null {
  return m?.holidays?.[iso] ?? null;
}

/** The date cell's tooltip: the long date, plus the holiday when there is one. */
export function dateTitle(displayDate: string, holiday: string | null): string {
  return holiday ? `${displayDate} · ${holiday} (public holiday)` : displayDate;
}

export function isWeekend(iso: string): boolean {
  const d = fromIsoDate(iso);
  return !!d && (d.getDay() === 0 || d.getDay() === 6);
}

/** "Tue 23 Sep  Kitchen  09:00–17:00  8h 00m" (one shift as plain text). */
export function entryAsText(e: EntryRow): string {
  const out = e.time_out ? e.time_out_display || e.time_out : '…';
  const dur = e.minutes === null ? '—' : formatDuration(e.minutes);
  return [shortDate(e.date), e.job_shift || '—', `${e.time_in}–${out}`, dur].join('  ');
}

/** The month as plain text for a chat or an email: shifts, week totals and the total. */
export function monthAsText(m: MonthData, f: EntryFilter = NO_FILTER): string {
  const lines = [isFiltering(f) ? `${m.label} (${filterName(f)})` : m.label];
  const weeks = new Map(m.weeks.map((w) => [w.key, w]));
  m.entries.forEach((e, i) => {
    lines.push(entryAsText(e));
    const next = m.entries[i + 1];
    const w = weeks.get(e.week_key);
    if (w && (!next || next.week_key !== e.week_key)) {
      lines.push(`  Week ${w.week}: ${formatDuration(w.minutes)} (${formatMoney(w.earnings)})`);
    }
  });
  const s = summaryText(monthSummary(m.entries));
  lines.push(`Total: ${formatDuration(m.total_minutes)} (${formatMoney(m.earnings)})${s ? ` · ${s}` : ''}`);
  return lines.join('\n');
}

/** The ⚠ tooltip: "Overlaps Sales 09:00–17:00 on Tue 22 Sep. Both count on the timesheet." */
export function overlapText(others: OverlapRef[] | undefined): string {
  if (!others?.length) return 'Overlaps another entry. Both count on the timesheet.';
  const one = (o: OverlapRef) => `${o.job_shift || '—'} ${o.time_in}–${o.time_out || '…'} on ${shortDate(o.date)}`;
  const names = others.length > 3 ? [...others.slice(0, 3).map(one), `${others.length - 3} more`] : others.map(one);
  return `Overlaps ${names.join(', ')}. Both count on the timesheet.`;
}
