import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { roundingExample, roundShift } from '../src/lib/rounding';

// The same cases tests/test_rounding.py runs against utils.round_shift.
const { cases } = JSON.parse(
  readFileSync('../tests/fixtures/rounding_cases.json', 'utf8'),
) as { cases: [string, string, string, number, [string, string] | null][] };

describe('roundShift', () => {
  it.each(cases)('%s–%s %s %i', (timeIn, timeOut, mode, step, expected) => {
    expect(roundShift(timeIn, timeOut, mode, step)).toEqual(expected);
  });

  it('refuses times that are not HH:MM', () => {
    expect(roundShift('9:07', '16:41', 'up', 30)).toBeNull();
    expect(roundShift('24:00', '16:41', 'up', 30)).toBeNull();
  });
});

describe('roundingExample', () => {
  it('shows what the chosen rule does to 09:07–16:41', () => {
    expect(roundingExample({ enabled: true, mode: 'up', step: 30 })).toBe('09:07–16:41 is saved as 09:00–17:00');
    expect(roundingExample({ enabled: true, mode: 'down', step: 60 })).toBe('09:07–16:41 is saved as 09:00–16:00');
    expect(roundingExample({ enabled: true, mode: 'nearest', step: 30 }, '09:00', '17:00')).toBe('09:00–17:00 is saved as is');
  });
});
