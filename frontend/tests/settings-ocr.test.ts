import { describe, expect, it } from 'vitest';
import type { OcrCandidate } from '../src/lib/api/types';
import {
  allState,
  clipRaw,
  draftRows,
  importSummary,
  issueText,
  rowIssue,
  rowsToSave,
  selectedCount,
} from '../src/views/ocr/ocrLogic';

const C: OcrCandidate[] = [
  { date: '2026-10-01', job_shift: 'Morning', time_in: '09:00', time_out: '17:00', raw_line: '1.10 9:00-17:00', confidence: 'ok' },
  { date: '2026-10-02', job_shift: '', time_in: '2l:00', time_out: '', raw_line: '2.10 2l:00', confidence: 'uncertain' },
];

describe('OCR preview rows', () => {
  it('starts all rows checked, flags uncertain, fills the fallback shift', () => {
    const rows = draftRows(C, 'Default');
    expect(rows.every((r) => r.checked)).toBe(true);
    expect(rows[1].uncertain).toBe(true);
    expect(rows[1].job_shift).toBe('Default');
    expect(rows[0].job_shift).toBe('Morning');
  });

  it('counts and saves only checked rows, trimmed', () => {
    const rows = draftRows(C);
    rows[0].date = ' 2026-10-01 ';
    rows[1].checked = false;
    expect(selectedCount(rows)).toBe(1);
    expect(allState(rows)).toBe('some');
    expect(rowsToSave(rows)).toEqual([{ date: '2026-10-01', job_shift: 'Morning', time_in: '09:00', time_out: '17:00' }]);
    rows[0].checked = false;
    expect(allState(rows)).toBe('none');
  });

  it('finds row issues', () => {
    expect(rowIssue({ date: '2026-10-01', time_in: '09:00', time_out: '' })).toBeNull();
    expect(rowIssue({ date: '', time_in: '09:00', time_out: '' })).toBe('date');
    expect(rowIssue({ date: '2026-10-01', time_in: '2l:00', time_out: '' })).toBe('time_in');
    expect(rowIssue({ date: '2026-10-01', time_in: '09:00', time_out: 'xx' })).toBe('time_out');
    expect(issueText('date')).toContain('skipped');
    expect(issueText(null)).toBeNull();
  });

  it('clips raw text', () => {
    expect(clipRaw('short')).toBe('short');
    const long = 'x'.repeat(80);
    expect(clipRaw(long)).toHaveLength(55);
    expect(clipRaw(long).endsWith('…')).toBe(true);
  });
});

describe('import summary', () => {
  it('covers singular, duplicates, invalid rows and errors', () => {
    expect(importSummary({ imported: 1, skipped: 0, invalid_skipped: 0 })).toBe('Imported 1 entry.');
    const s = importSummary({ imported: 3, skipped: 2, invalid_skipped: 1 }, ['a.png: unreadable']);
    expect(s).toContain('Imported 3 entries.');
    expect(s).toContain('2 duplicates skipped.');
    expect(s).toContain('1 row(s) had no date or start time');
    expect(s).toContain('Errors:\na.png: unreadable');
  });
});
