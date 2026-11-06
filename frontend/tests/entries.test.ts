// @vitest-environment node
import { describe, expect, it } from 'vitest';
import type { EntryRow, MonthData } from '../src/lib/api/types';
import {
  buildRows,
  decideClose,
  earlyExportMonth,
  addMinutesToTime,
  dateHint,
  draftChanged,
  duplicateDraft,
  editorValue,
  EMPTY_HINT,
  emptyText,
  entryAsText,
  filterMonth,
  filterTotalLabel,
  importSummary,
  isFiltering,
  isSameMonth,
  isWeekend,
  dateTitle,
  holidayOn,
  jobsInMonth,
  monthAsText,
  overlapText,
  monthSummary,
  monthTotalText,
  moveSelection,
  newEntryDraft,
  nextFreeDate,
  NO_FILTER,
  parseEditor,
  parseYear,
  pickerStep,
  rangeExports,
  savedMessage,
  shortDate,
  stepMonth,
  summaryText,
  weekCrossesMonth,
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
  note: '',
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
    expect(emptyText('March 2025', false)).toBe('No shifts in March 2025. Add one by hand with + Add entry.');
    expect(EMPTY_HINT).toMatch(/weleho/);
  });

  it('knows the current month', () => {
    expect(isSameMonth({ year: 2026, month: 10 }, new Date(2026, 9, 31))).toBe(true);
    expect(isSameMonth({ year: 2026, month: 9 }, new Date(2026, 9, 1))).toBe(false);
    expect(isSameMonth({ year: 2025, month: 10 }, new Date(2026, 9, 1))).toBe(false);
  });

  it('marks a week total that spills into another month', () => {
    const sep = { year: 2026, month: 9 };
    // W39 2026 = Mon 21 – Sun 27 Sep: whole week inside September
    expect(weekCrossesMonth(month.weeks[0], sep)).toBe(false);
    expect(weekTotalText(month.weeks[0], sep)).toBe('Week 39 total 15:30 (€232.50)');
    // W40 2026 = Mon 28 Sep – Sun 4 Oct
    expect(weekCrossesMonth(month.weeks[1], sep)).toBe(true);
    expect(weekTotalText(month.weeks[1], sep)).toBe('Week 40 total (this month) 8:00 (€120.00)');
    expect(weekCrossesMonth(month.weeks[1], { year: 2026, month: 10 })).toBe(true);
    // ISO week 1 of 2027 starts on Mon 4 Jan 2027
    expect(weekCrossesMonth({ ...month.weeks[0], iso_year: 2027, week: 1 }, { year: 2027, month: 1 })).toBe(false);
    // ISO week 53 of 2026 = Mon 28 Dec 2026 – Sun 3 Jan 2027
    expect(weekCrossesMonth({ ...month.weeks[0], iso_year: 2026, week: 53 }, { year: 2026, month: 12 })).toBe(true);
  });

  it('builds the v1.3 import summary', () => {
    expect(importSummary({ imported: 1, skipped: 0, files: 1, errors: [] })).toBe('Imported 1 entry from 1 file.');
    expect(importSummary({ imported: 3, skipped: 2, files: 2, errors: ['bad.xlsx: no sheet'] })).toBe(
      'Imported 3 entries from 2 files.\n2 duplicates skipped.\n\nErrors:\nbad.xlsx: no sheet',
    );
    expect(importSummary({ imported: 0, skipped: 1, files: 1, errors: [] })).toBe('Imported 0 entries from 1 file.\n1 duplicate skipped.');
  });

  it('says why a file gave nothing', () => {
    expect(
      importSummary({ imported: 0, skipped: 0, files: 2, errors: ['b.xls: save it as .xlsx'], notes: ['No timesheet rows found in a.xlsx'] }),
    ).toBe('Imported 0 entries from 2 files.\n\nNo timesheet rows found in a.xlsx\n\nErrors:\nb.xls: save it as .xlsx');
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

describe('earlyExportMonth', () => {
  const oct = { year: 2026, month: 10 };
  it('offers last month on the current month, 1st–5th', () => {
    expect(earlyExportMonth(oct, new Date(2026, 9, 1, 8))).toEqual({ year: 2026, month: 9 });
    expect(earlyExportMonth(oct, new Date(2026, 9, 5, 23, 59))).toEqual({ year: 2026, month: 9 });
  });
  it('not from the 6th on', () => {
    expect(earlyExportMonth(oct, new Date(2026, 9, 6))).toBeNull();
  });
  it('not when another month is viewed', () => {
    expect(earlyExportMonth({ year: 2026, month: 9 }, new Date(2026, 9, 2))).toBeNull();
    expect(earlyExportMonth({ year: 2025, month: 10 }, new Date(2026, 9, 2))).toBeNull();
  });
  it('January offers December of the year before', () => {
    expect(earlyExportMonth({ year: 2027, month: 1 }, new Date(2027, 0, 3))).toEqual({ year: 2026, month: 12 });
  });
});

describe('rangeExports', () => {
  it('the viewed month as CSV, then its year as CSV or one sheet', () => {
    const [month, yearCsv, yearXlsx] = rangeExports({ year: 2028, month: 2 });
    expect(month).toMatchObject({ label: 'February 2028 as CSV…', start: '2028-02-01', end: '2028-02-29', kind: 'csv' });
    expect(yearCsv).toMatchObject({ start: '2028-01-01', end: '2028-12-31', kind: 'csv' });
    expect(yearXlsx).toMatchObject({ start: '2028-01-01', end: '2028-12-31', kind: 'xlsx' });
  });
  it('pads the month and ends on its last day', () => {
    expect(rangeExports({ year: 2026, month: 9 })[0]).toMatchObject({ start: '2026-09-01', end: '2026-09-30' });
    expect(rangeExports({ year: 2027, month: 2 })[0].end).toBe('2027-02-28');
  });
});

describe('new entry defaults', () => {
  const base = { date: '2026-09-23', startTime: '09:00', job: 'Kitchen' };
  it('ends after the Daily target, fractional hours too', () => {
    expect(newEntryDraft({ ...base, targetHours: 8 }).time_out).toBe('17:00');
    expect(newEntryDraft({ ...base, startTime: '09:30', targetHours: 7.5 }).time_out).toBe('17:00');
    expect(newEntryDraft({ ...base, startTime: '22:00', targetHours: 10 }).time_out).toBe('08:00');
    expect(newEntryDraft({ ...base, targetHours: 7.5 })).toEqual({
      date: '2026-09-23',
      job_shift: 'Kitchen',
      time_in: '09:00',
      time_out: '16:30',
    });
  });
  it('falls back to 8 h for an unusable target and leaves Time Out empty without a start', () => {
    expect(newEntryDraft({ ...base, targetHours: NaN }).time_out).toBe('17:00');
    expect(newEntryDraft({ ...base, targetHours: 24 }).time_out).toBe('17:00');
    expect(newEntryDraft({ ...base, startTime: '', targetHours: 8 }).time_out).toBe('');
  });
  it('adds minutes with wrap-around', () => {
    expect(addMinutesToTime('23:45', 30)).toBe('00:15');
    expect(addMinutesToTime('00:10', -20)).toBe('23:50');
  });
});

describe('duplicate', () => {
  it('copies the shift to the next free day', () => {
    const e = month.entries[0];
    expect(duplicateDraft(e, ['2026-09-21', '2026-09-23'])).toEqual({
      date: '2026-09-22',
      job_shift: 'Kitchen',
      time_in: '09:00',
      time_out: '17:00',
    });
    expect(nextFreeDate('2026-09-21', ['2026-09-22', '2026-09-23'])).toBe('2026-09-24');
    expect(nextFreeDate('2026-09-30', [])).toBe('2026-10-01');
    expect(nextFreeDate('2026-12-31', [])).toBe('2027-01-01');
    expect(nextFreeDate('bad', [])).toBe('bad');
  });
  it('carries no id', () => {
    expect('id' in duplicateDraft(month.entries[0], [])).toBe(false);
  });
});

describe('draftChanged', () => {
  const init = { date: '2026-09-23', job_shift: 'Kitchen', time_in: '09:00', time_out: '17:00' };
  const today = new Date(2026, 8, 30);
  it('ignores spelling of the same values', () => {
    expect(draftChanged(init, { ...init }, today)).toBe(false);
    expect(draftChanged(init, { date: '23.9.', job_shift: ' Kitchen ', time_in: '9', time_out: '1700' }, today)).toBe(false);
  });
  it('sees a real change in any field', () => {
    expect(draftChanged(init, { ...init, date: '2026-09-24' }, today)).toBe(true);
    expect(draftChanged(init, { ...init, job_shift: 'Bar' }, today)).toBe(true);
    expect(draftChanged(init, { ...init, time_in: '9:30' }, today)).toBe(true);
    expect(draftChanged(init, { ...init, time_out: '' }, today)).toBe(true);
    expect(draftChanged(init, { ...init, time_out: '17:0x' }, today)).toBe(true);
    expect(draftChanged(init, { ...init, note: 'Covered' }, today)).toBe(true);
  });
  it('treats a missing note as empty and ignores outer spaces in it', () => {
    expect(draftChanged(init, { ...init, note: '  ' }, today)).toBe(false);
    expect(draftChanged({ ...init, note: 'a' }, { ...init, note: ' a ' }, today)).toBe(false);
  });
});

describe('shift notes and undo copy', () => {
  const noted = { ...row('n', '2026-09-23', '2026-W39'), note: 'Covered for Sam' };
  it('filters by the note text', () => {
    const m = { ...month, entries: [...month.entries, noted] };
    expect(filterMonth(m, { job: null, text: 'sam' }).entries.map((e) => e.id)).toEqual(['n']);
  });
  it('adds the note to the copied line', () => {
    expect(entryAsText(noted)).toBe('Wed 23 Sep  Kitchen  09:00–17:00  8h 00m  — Covered for Sam');
  });
  it('says what was saved', () => {
    expect(savedMessage(noted, true)).toBe('Added the shift on Wed 23 Sep, 09:00–17:00.');
    expect(savedMessage(noted, false)).toBe('Changed the shift on Wed 23 Sep, 09:00–17:00.');
  });
});

describe('dateHint', () => {
  const today = new Date(2026, 9, 15, 13);
  const oct = { year: 2026, month: 10 };
  it('is quiet for a past date in the month on screen', () => {
    expect(dateHint('2026-10-15', today, oct)).toBeNull();
    expect(dateHint('2026-10-01', today, oct)).toBeNull();
    expect(dateHint(null, today, oct)).toBeNull();
  });
  it('says where the shift lands and when it is in the future', () => {
    expect(dateHint('2026-09-30', today, oct)).toBe('Saves to September 2026.');
    expect(dateHint('2026-10-16', today, oct)).toBe("That's in the future.");
    expect(dateHint('2026-11-02', today, oct)).toBe('Saves to November 2026, which is in the future.');
  });
  it('catches a typoed year', () => {
    expect(dateHint('2062-10-15', today, oct)).toBe("That's 36 years from now. Time traveller? Check the year.");
    expect(dateHint('2016-10-15', today, oct)).toBe("That's 10 years ago. Check the year.");
    expect(dateHint('2027-10-20', today, oct)).toBe("That's 1 year from now. Time traveller? Check the year.");
  });
});

describe('month summary', () => {
  it('counts shifts, distinct days and averages finished shifts', () => {
    const entries = [
      ...month.entries,
      row('d', '2026-09-28', '2026-W40', 0),
      { ...row('e', '2026-09-29', '2026-W40'), minutes: null },
    ];
    expect(monthSummary(entries)).toEqual({ shifts: 5, days: 4, avgMinutes: Math.round((480 + 450 + 480 + 0) / 4) });
    expect(summaryText(monthSummary(month.entries))).toBe('3 shifts · 3 days · avg 7:50');
    expect(summaryText(monthSummary([{ ...row('x', '2026-09-01', 'w'), minutes: null }]))).toBe('1 shift · 1 day');
    expect(summaryText(monthSummary([]))).toBe('');
  });
});

describe('filter', () => {
  const mixed: MonthData = {
    ...month,
    entries: [month.entries[0], { ...month.entries[1], job_shift: 'Bar' }, month.entries[2]],
  };
  it('lists jobs, most used first', () => {
    expect(jobsInMonth(mixed)).toEqual(['Kitchen', 'Bar']);
    expect(jobsInMonth(null)).toEqual([]);
  });
  it('recomputes weeks and totals from the visible rows', () => {
    const f = filterMonth(mixed, { job: 'Kitchen', text: '' });
    expect(f.entries.map((e) => e.id)).toEqual(['a', 'c']);
    expect(f.weeks.map((w) => [w.key, w.entry_ids, w.minutes, w.earnings])).toEqual([
      ['2026-W39', ['a'], 480, 120],
      ['2026-W40', ['c'], 480, 120],
    ]);
    expect(f.total_minutes).toBe(960);
    expect(f.earnings).toBe(240);
  });
  it('drops weeks with nothing left and matches text in dates and jobs', () => {
    const f = filterMonth(mixed, { job: null, text: ' bar ' });
    expect(f.entries.map((e) => e.id)).toEqual(['b']);
    expect(f.weeks.map((w) => w.key)).toEqual(['2026-W39']);
    expect(f.earnings).toBe(112.5);
    expect(filterMonth(mixed, { job: null, text: '09-28' }).entries.map((e) => e.id)).toEqual(['c']);
  });
  it('is a no-op without a filter', () => {
    expect(filterMonth(mixed, NO_FILTER)).toBe(mixed);
    expect(isFiltering({ job: null, text: '  ' })).toBe(false);
    expect(isFiltering({ job: '', text: '' })).toBe(true);
  });
  it('labels the total', () => {
    expect(filterTotalLabel(NO_FILTER)).toBe('Total:');
    expect(filterTotalLabel({ job: 'Bar', text: '' })).toBe('Total (Bar):');
    expect(filterTotalLabel({ job: null, text: 'mon ' })).toBe('Total (“mon”):');
  });
});

describe('row polish', () => {
  it('formats short dates and spots weekends', () => {
    expect(shortDate('2026-09-23')).toBe('Wed 23 Sep');
    expect(shortDate('oops')).toBe('oops');
    expect(isWeekend('2026-09-26')).toBe(true);
    expect(isWeekend('2026-09-27')).toBe(true);
    expect(isWeekend('2026-09-28')).toBe(false);
  });

  it('names public holidays from the month payload', () => {
    const dec: MonthData = { ...month, holidays: { '2026-12-06': 'Itsenäisyyspäivä' } };
    expect(holidayOn(dec, '2026-12-06')).toBe('Itsenäisyyspäivä');
    expect(holidayOn(dec, '2026-12-07')).toBeNull();
    expect(holidayOn(month, '2026-09-23')).toBeNull(); // older backend: no field
    expect(holidayOn(null, '2026-12-06')).toBeNull();
    expect(dateTitle('Sun 6 Dec 2026', 'Itsenäisyyspäivä')).toBe('Sun 6 Dec 2026 · Itsenäisyyspäivä (public holiday)');
    expect(dateTitle('Mon 7 Dec 2026', null)).toBe('Mon 7 Dec 2026');
  });
});

describe('copy as text', () => {
  it('formats one shift', () => {
    expect(entryAsText(month.entries[1])).toBe('Wed 23 Sep  Kitchen  09:00–17:00  7h 30m');
    const night = { ...row('n', '2026-09-23', 'w', 480), time_in: '22:00', time_out: '06:00', time_out_display: '06:00 +1' };
    expect(entryAsText(night)).toBe('Wed 23 Sep  Kitchen  22:00–06:00 +1  8h 00m');
    const open = { ...row('o', '2026-09-23', 'w'), job_shift: '', time_out: '', time_out_display: '', minutes: null };
    expect(entryAsText(open)).toBe('Wed 23 Sep  —  09:00–…  —');
  });
  it('formats the month with week totals and a summary', () => {
    expect(monthAsText(month)).toBe(
      [
        'September 2026',
        'Mon 21 Sep  Kitchen  09:00–17:00  8h 00m',
        'Wed 23 Sep  Kitchen  09:00–17:00  7h 30m',
        '  Week 39: 15h 30m (€232.50)',
        'Mon 28 Sep  Kitchen  09:00–17:00  8h 00m',
        '  Week 40: 8h 00m (€120.00)',
        'Total: 23h 30m (€352.50) · 3 shifts · 3 days · avg 7:50',
      ].join('\n'),
    );
    expect(monthAsText(month, { job: 'Kitchen', text: '' }).split('\n')[0]).toBe('September 2026 (Kitchen)');
  });
});

describe('overlap tooltip', () => {
  const o = (date: string, job: string, a: string, b: string) => ({ id: date + a, date, job_shift: job, time_in: a, time_out: b });
  it('names the overlapping shifts', () => {
    expect(overlapText([o('2026-09-22', 'Sales', '09:00', '17:00')])).toBe(
      'Overlaps Sales 09:00–17:00 on Tue 22 Sep. Both count on the timesheet.',
    );
  });
  it('falls back without details and caps a long list', () => {
    expect(overlapText(undefined)).toBe('Overlaps another entry. Both count on the timesheet.');
    const many = ['01', '02', '03', '04', '05'].map((d) => o(`2026-09-${d}`, '', '09:00', ''));
    expect(overlapText(many)).toBe(
      'Overlaps — 09:00–… on Tue 01 Sep, — 09:00–… on Wed 02 Sep, — 09:00–… on Thu 03 Sep, 2 more. Both count on the timesheet.',
    );
  });
});
