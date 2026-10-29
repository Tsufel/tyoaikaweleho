import type { EntryRow, MonthData, WeekGroup } from '../../lib/api/types';
import { addMonths, formatHM, formatMoney, parseTimeInput } from '../../lib/time';

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

export const weekTotalText = (w: WeekGroup) => `Week ${w.week} total ${formatHM(w.minutes)} (${formatMoney(w.earnings)})`;

export const monthTotalText = (m: MonthData | null) =>
  `Total: ${formatHM(m?.total_minutes ?? 0)} (${formatMoney(m?.earnings ?? 0)})`;

export const emptyText = (label: string) => `No shifts in ${label}. Press START or + Add entry.`;
/** Second line under the empty-month wizard. */
export const EMPTY_HINT = 'The weleho is standing by — your hours land here once you clock out.';

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
export function importSummary(r: { imported: number; skipped: number; files: number; errors: string[] }): string {
  let msg = `Imported ${r.imported} ${plural(r.imported, 'entry', 'entries')} from ${r.files} ${plural(r.files, 'file', 'files')}.`;
  if (r.skipped) msg += `\n${r.skipped} ${plural(r.skipped, 'duplicate', 'duplicates')} skipped.`;
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
