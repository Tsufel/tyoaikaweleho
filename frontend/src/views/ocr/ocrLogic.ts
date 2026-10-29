import type { OcrCandidate, OcrRow } from '../../lib/api/types';
import { parseDateInput, parseTimeInput } from '../../lib/time';

/** One editable row of the preview sheet. All rows start checked (v1.3). */
export interface OcrDraftRow {
  key: number;
  checked: boolean;
  date: string;
  job_shift: string;
  time_in: string;
  time_out: string;
  raw_line: string;
  uncertain: boolean;
}

export function draftRows(candidates: OcrCandidate[], fallbackShift = ''): OcrDraftRow[] {
  return candidates.map((c, i) => ({
    key: i,
    checked: true,
    date: c.date ?? '',
    job_shift: c.job_shift || fallbackShift,
    time_in: c.time_in ?? '',
    time_out: c.time_out ?? '',
    raw_line: c.raw_line ?? '',
    uncertain: c.confidence === 'uncertain',
  }));
}

export const selectedCount = (rows: OcrDraftRow[]) => rows.reduce((n, r) => n + (r.checked ? 1 : 0), 0);

/** Checked rows, trimmed, dates as ISO (Python only reads ISO) — what
 *  ocr_save receives. */
export function rowsToSave(rows: OcrDraftRow[]): OcrRow[] {
  return rows
    .filter((r) => r.checked)
    .map((r) => ({
      date: parseDateInput(r.date) ?? r.date.trim(),
      job_shift: r.job_shift.trim(),
      time_in: r.time_in.trim(),
      time_out: r.time_out.trim(),
    }));
}

export type RowIssue = 'date' | 'time_in' | 'time_out' | null;

/** First problem that would make Python skip or reject the row. v1.3 skipped
 *  rows with no date or start time; an unreadable value counts the same. */
export function rowIssue(r: Pick<OcrDraftRow, 'date' | 'time_in' | 'time_out'>): RowIssue {
  if (!r.date.trim() || !parseDateInput(r.date)) return 'date';
  if (!r.time_in.trim() || !parseTimeInput(r.time_in)) return 'time_in';
  if (r.time_out.trim() && !parseTimeInput(r.time_out)) return 'time_out';
  return null;
}

export function issueText(issue: RowIssue): string | null {
  switch (issue) {
    case 'date':
      return 'No valid date — this row will be skipped.';
    case 'time_in':
      return 'No valid start time — this row will be skipped.';
    case 'time_out':
      return "End time isn't a valid time.";
    default:
      return null;
  }
}

/** Header checkbox state. */
export function allState(rows: OcrDraftRow[]): 'all' | 'none' | 'some' {
  const n = selectedCount(rows);
  return n === 0 ? 'none' : n === rows.length ? 'all' : 'some';
}

export const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;

/** v1.3 "Import complete" text. */
export function importSummary(r: { imported: number; skipped: number; invalid_skipped: number }, errors: string[] = []): string {
  let msg = `Imported ${r.imported} entr${r.imported === 1 ? 'y' : 'ies'}.`;
  if (r.skipped) msg += `\n${plural(r.skipped, 'duplicate', 'duplicates')} skipped.`;
  if (r.invalid_skipped) msg += `\n${r.invalid_skipped} row(s) had no date or start time and were skipped.`;
  if (errors.length) msg += `\n\nErrors:\n${errors.join('\n')}`;
  return msg;
}

/** Raw OCR text is clipped in the table (v1.3 showed 55 chars); full text in the tooltip. */
export const clipRaw = (s: string, n = 55) => (s.length > n ? `${s.slice(0, n - 1)}…` : s);
