import { describe, expect, it } from 'vitest';
import type { EntryRow, MonthData } from '../src/lib/api/types';
import {
  buildRows,
  decideClose,
  editorValue,
  EMPTY_HINT,
  emptyText,
  importSummary,
  monthTotalText,
  moveSelection,
  parseEditor,
  parseYear,
  pickerStep,
  stepMonth,
  weekTotalText,
} from '../src/views/entries/entriesLogic';

const row = (id: string, date: string, week_key: string, minutes = 480): EntryRow => ({
  id,
  date,
  job_shift: 'Kitchen',
  time_in: '09:00',
  time_out: '17:00',
  minutes,
  overnight: false,
  display_date: date,
  time_out_display: '17:00',
  week_key,
});

const month: MonthData = {
  year: 2026,
  month: 9,
  label: 'September 2026',
  pay_rate: 15,
  entries: [row('a', '2026-09-21', '2026-W39'), row('b', '2026-09-23', '2026-W39', 450), row('c', '2026-09-28', '2026-W40')],
  weeks: [
    { key: '2026-W39', iso_year: 2026, week: 39, entry_ids: ['a', 'b'], minutes: 930, earnings: 232.5 },
    { key: '2026-W40', iso_year: 2026, week: 40, entry_ids: ['c'], minutes: 480, earnings: 120 },
  ],
  total_minutes: 1410,
  earnings: 352.5,
};

describe('buildRows', () => {
  it('puts a week total after the last entry of each week', () => {
    const rows = buildRows(month);
    expect(rows.map((r) => r.key)).toEqual(['a', 'b', 'week-2026-W39', 'c', 'week-2026-W40']);
  });
  it('is empty without data', () => {
    expect(buildRows(null)).toEqual([]);
  });
});

describe('texts', () => {
  it('formats week, total and empty lines', () => {
    expect(weekTotalText(month.weeks[0])).toBe('Week 39 total 15:30 (€232.50)');
    expect(monthTotalText(month)).toBe('Total: 23:30 (€352.50)');
    expect(monthTotalText(null)).toBe('Total: 0:00 (€0.00)');
    expect(emptyText('October 2026')).toBe('No shifts in October 2026. Press START or + Add entry.');
    expect(EMPTY_HINT).toMatch(/weleho/);
  });

  it('builds the v1.3 import summary', () => {
    expect(importSummary({ imported: 1, skipped: 0, files: 1, errors: [] })).toBe('Imported 1 entry from 1 file.');
    expect(importSummary({ imported: 3, skipped: 2, files: 2, errors: ['bad.xlsx: no sheet'] })).toBe(
      'Imported 3 entries from 2 files.\n2 duplicates skipped.\n\nErrors:\nbad.xlsx: no sheet',
    );
    expect(importSummary({ imported: 0, skipped: 1, files: 1, errors: [] })).toBe('Imported 0 entries from 1 file.\n1 duplicate skipped.');
  });
});

describe('inline editor', () => {
  it('drops a pasted +1 suffix', () => {
    expect(editorValue('06:00 +1')).toBe('06:00');
    expect(editorValue('  ')).toBe('');
    expect(parseEditor('time_out', '6.00 +1')).toBe('06:00');
  });

  it('allows clearing time out but not time in', () => {
    expect(parseEditor('time_out', '')).toBeNull();
    expect(parseEditor('time_in', '')).toBeNull();
  });

  it('Esc closes without saving', () => {
    expect(decideClose('time_in', '10:00', '09:00', false, true)).toEqual({ action: 'close' });
  });

  it('strict keeps an invalid value open, lenient reverts with a note', () => {
    expect(decideClose('time_in', '25:99', '09:00', true, true)).toEqual({ action: 'mark-invalid' });
    expect(decideClose('time_in', '25:99', '09:00', true, false)).toEqual({ action: 'close', note: 'Invalid time, not saved' });
  });

  it('an unchanged invalid text closes silently', () => {
    expect(decideClose('time_in', 'x', 'x', true, true)).toEqual({ action: 'close' });
  });

  it('unchanged values do not save; changed ones are normalised', () => {
    expect(decideClose('time_in', '9', '09:00', true, true)).toEqual({ action: 'close' });
    expect(decideClose('time_in', '930', '09:00', true, false)).toEqual({ action: 'save', value: '09:30' });
    expect(decideClose('time_out', '', '17:00', true, true)).toEqual({ action: 'mark-invalid' });
    expect(decideClose('time_out', '', '17:00', true, false)).toEqual({ action: 'close', note: 'Invalid time, not saved' });
  });
});

describe('month picker', () => {
  it('maps keys like MonthPickerDialog', () => {
    expect(pickerStep('ArrowUp')).toBe(-1);
    expect(pickerStep('ArrowDown')).toBe(1);
    expect(pickerStep('PageUp')).toBe(-12);
    expect(pickerStep('PageDown')).toBe(12);
    expect(pickerStep('Enter')).toBeNull();
  });

  it('steps across years and stays inside 1900-9999', () => {
    expect(stepMonth(2026, 12, 1)).toEqual({ year: 2027, month: 1 });
    expect(stepMonth(2026, 1, -1)).toEqual({ year: 2025, month: 12 });
    expect(stepMonth(1900, 1, -1)).toEqual({ year: 1900, month: 1 });
    expect(stepMonth(9999, 6, 12)).toEqual({ year: 9999, month: 6 });
  });

  it('validates the year field', () => {
    expect(parseYear(' 2026 ')).toBe(2026);
    expect(parseYear('1899')).toBeNull();
    expect(parseYear('20x6')).toBeNull();
    expect(parseYear('')).toBeNull();
  });
});

describe('moveSelection', () => {
  const ids = ['a', 'b', 'c'];
  it('moves and clamps', () => {
    expect(moveSelection(ids, 'a', 1)).toBe('b');
    expect(moveSelection(ids, 'c', 1)).toBe('c');
    expect(moveSelection(ids, 'a', -1)).toBe('a');
  });
  it('starts at an end without a selection', () => {
    expect(moveSelection(ids, null, 1)).toBe('a');
    expect(moveSelection(ids, null, -1)).toBe('c');
    expect(moveSelection([], null, 1)).toBeNull();
  });
});
