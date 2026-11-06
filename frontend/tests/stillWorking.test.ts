// @vitest-environment node
import { describe, expect, it } from 'vitest';
import { STILL_WORKING_AFTER_H, stillWorkingDue, stillWorkingText } from '../src/views/timer/timerLogic';

const H = 3600;

describe('Still working? nudge', () => {
  it('shows only once the shift is 2 h past the daily target', () => {
    expect(STILL_WORKING_AFTER_H).toBe(2);
    expect(stillWorkingDue(10 * H - 1, 8)).toBe(false);
    expect(stillWorkingDue(10 * H, 8)).toBe(true);
    expect(stillWorkingDue(8 * H, 6)).toBe(true);
    expect(stillWorkingDue(7 * H, 6)).toBe(false);
  });

  it('falls back to an 8 h target when none is set', () => {
    expect(stillWorkingDue(10 * H, 0)).toBe(true);
    expect(stillWorkingDue(9 * H, 0)).toBe(false);
  });

  it('says how long the shift has run and how far past the target', () => {
    expect(stillWorkingText(10 * H + 5 * 60 + 30, 8)).toBe('10h 05m on the clock, 2h 05m past your 8h target.');
  });
});
