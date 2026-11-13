import type { HHMM, RoundMode, RoundStep, Rounding } from './api/types';

// Settings → Round shift times. The rule itself runs in Python (utils.round_shift)
// when a timer shift is saved; this copy only draws the example in Settings.
// tests/fixtures/rounding_cases.json keeps the two the same.

export const ROUND_MODES: RoundMode[] = ['nearest', 'up', 'down'];
export const ROUND_STEPS: RoundStep[] = [15, 30, 60];

const DAY = 24 * 60;

function minutesOf(t: string): number | null {
  const m = /^(\d{2}):(\d{2})$/.exec(t);
  if (!m) return null;
  const h = Number(m[1]);
  const min = Number(m[2]);
  return h < 24 && min < 60 ? h * 60 + min : null;
}

const fmt = (m: number): HHMM => `${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`;

/** The shift timeIn–timeOut rounded: its length to a whole step (up, down,
 *  or nearest with a half step going up), its start to the nearest step, or
 *  the step before when that would pass midnight. null when nothing changes
 *  or the rounded length would be zero or a whole day. */
export function roundShift(timeIn: string, timeOut: string, mode: string, step: number): [HHMM, HHMM] | null {
  if (!(ROUND_MODES as string[]).includes(mode) || !(ROUND_STEPS as number[]).includes(step)) return null;
  const start = minutesOf(timeIn);
  const end = minutesOf(timeOut);
  if (start === null || end === null) return null;
  const minutes = (end - start + DAY) % DAY;
  if (minutes <= 0) return null;
  const length =
    mode === 'up'
      ? Math.ceil(minutes / step) * step
      : mode === 'down'
        ? Math.floor(minutes / step) * step
        : Math.floor((minutes + Math.floor(step / 2)) / step) * step;
  if (!(length > 0 && length < DAY)) return null;
  let snapped = Math.floor((start + Math.floor(step / 2)) / step) * step;
  if (snapped >= DAY) snapped = Math.floor(start / step) * step;
  const out: [HHMM, HHMM] = [fmt(snapped), fmt((snapped + length) % DAY)];
  return out[0] === timeIn && out[1] === timeOut ? null : out;
}

/** Settings' worked example for the chosen rule: "09:07–16:41 is saved as 09:00–17:00". */
export function roundingExample(r: Rounding, timeIn = '09:07', timeOut = '16:41'): string {
  const out = roundShift(timeIn, timeOut, r.mode, r.step);
  return out ? `${timeIn}–${timeOut} is saved as ${out[0]}–${out[1]}` : `${timeIn}–${timeOut} is saved as is`;
}
