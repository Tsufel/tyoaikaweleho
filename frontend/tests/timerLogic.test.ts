import { describe, expect, it, vi } from 'vitest';
import {
  DIAL_MAX_MIN,
  IDLE_TEXT,
  agoText,
  dialDay,
  clockGlyphs,
  elapsedHM,
  fireBadge,
  fireIntensity,
  haloHue,
  hourTicks,
  nudgeStart,
  pointerFraction,
  recoveryDate,
  ringPoint,
  ringProgress,
  runningText,
  snapStart,
  spokenDuration,
  startFromLaps,
  startedText,
  unwrapLaps,
} from '../src/views/timer/timerLogic';

describe('ring maths', () => {
  it('progress is elapsed / target and exceeds 1 in overtime', () => {
    expect(ringProgress(0, 8)).toBe(0);
    expect(ringProgress(4 * 3600, 8)).toBe(0.5);
    expect(ringProgress(12 * 3600, 8)).toBe(1.5);
    expect(ringProgress(-5, 8)).toBe(0);
    expect(ringProgress(3600, 0)).toBe(1 / 8); // falls back to 8 h
  });

  it('hue walks violet → teal → amber and clamps', () => {
    expect(haloHue(0)).toBe(265);
    expect(haloHue(0.5)).toBe(195);
    expect(haloHue(1)).toBe(165);
    expect(haloHue(0.25)).toBe(230);
    expect(haloHue(2)).toBe(32);
    expect(haloHue(9)).toBe(32);
    expect(haloHue(-1)).toBe(265);
  });

  it('hour ticks split the circle by target hours', () => {
    expect(hourTicks(8)).toEqual([0, 45, 90, 135, 180, 225, 270, 315]);
    expect(hourTicks(0)).toHaveLength(8);
    expect(hourTicks(99)).toHaveLength(24);
  });

  it('ringPoint starts at 12 o’clock and goes clockwise', () => {
    const top = ringPoint(0, 100, 240);
    expect(top.x).toBeCloseTo(120);
    expect(top.y).toBeCloseTo(20);
    const right = ringPoint(0.25, 100, 240);
    expect(right.x).toBeCloseTo(220);
    expect(right.y).toBeCloseTo(120);
  });
});

describe('fire', () => {
  it('intensity grows with time and is bounded', () => {
    const a = fireIntensity(0, 8);
    const b = fireIntensity(2 * 3600, 8);
    const c = fireIntensity(8 * 3600, 8);
    const d = fireIntensity(100 * 3600, 8);
    expect(a).toBeCloseTo(0.15);
    expect(b).toBeGreaterThan(a);
    expect(c).toBeGreaterThan(b);
    expect(c).toBeCloseTo(1);
    expect(d).toBe(1.4);
  });

  it('badge levels', () => {
    expect(fireBadge(false, 5000, 8)).toBeNull();
    expect(fireBadge(true, 60, 8)?.text).toBe('warming up');
    expect(fireBadge(true, 3600, 8)).toEqual({ emoji: '🔥', text: 'on fire' });
    expect(fireBadge(true, 8.5 * 3600, 8)?.text).toBe('unstoppable');
    expect(fireBadge(true, 11 * 3600, 8)?.text).toBe('inferno');
  });
});

describe('texts (v1.3 TimerPanel)', () => {
  const now = new Date(2026, 9, 29, 14, 0, 0);

  it('idle text', () => {
    expect(IDLE_TEXT).toBe('Press START (F5) to begin tracking');
  });

  it('started today / yesterday / earlier', () => {
    expect(startedText('2026-10-29T09:12:00', now)).toBe('Started 09:12');
    expect(startedText('2026-10-28T22:05:00', now)).toBe('Started 22:05 (yesterday)');
    expect(startedText('2026-10-26T08:00:00', now)).toBe('Started 08:00 (Mon 26 Oct)');
    expect(startedText(null, now)).toBe('Started —');
  });

  it('running line includes job, blank job → —', () => {
    expect(runningText('2026-10-29T09:12:00', 'Support', now)).toBe('Started 09:12  ·  Support  ·  running…');
    expect(runningText('2026-10-29T09:12:00', '', now)).toBe('Started 09:12  ·  —  ·  running…');
  });

  it('clock glyphs and spoken form', () => {
    expect(clockGlyphs(0).join('')).toBe('00:00:00');
    expect(clockGlyphs(3725).join('')).toBe('01:02:05');
    expect(clockGlyphs(100 * 3600).join('')).toBe('100:00:00');
    expect(spokenDuration(3725)).toBe('1 hour 2 minutes');
    expect(spokenDuration(59)).toBe('0 minutes');
    expect(spokenDuration(7260)).toBe('2 hours 1 minute');
  });

  it('recovery date and elapsed', () => {
    expect(recoveryDate('2026-09-23T09:00:00')).toBe('Wed 2026-09-23');
    const from = new Date(2026, 9, 29, 9, 0).getTime();
    expect(elapsedHM(from, from + (3 * 60 + 7) * 60_000)).toBe('3h 07m');
    expect(elapsedHM(from, from + 30 * 3600_000)).toBe('30h 00m');
    expect(elapsedHM(from, from - 1000)).toBe('0h 00m');
  });
});

describe('start dial', () => {
  const at = (h: number, m: number, s = 0) => new Date(2026, 9, 30, h, m, s).getTime();
  const now = at(10, 3, 20);

  it('maps pointer positions to clockwise ring fractions from the top', () => {
    expect(pointerFraction(50, 0, 50, 50)).toBeCloseTo(0);
    expect(pointerFraction(100, 50, 50, 50)).toBeCloseTo(0.25);
    expect(pointerFraction(50, 100, 50, 50)).toBeCloseTo(0.5);
    expect(pointerFraction(0, 50, 50, 50)).toBeCloseTo(0.75);
  });

  it('keeps counting laps across the top and never goes below zero', () => {
    expect(unwrapLaps(0.95, 0.05, 3)).toBeCloseTo(1.05);
    expect(unwrapLaps(1.05, 0.95, 3)).toBeCloseTo(0.95);
    expect(unwrapLaps(0, 0.9, 3)).toBe(0);
    expect(unwrapLaps(2.9, 0.2, 3)).toBe(3);
  });

  it('stops at either end until the pointer comes back near it', () => {
    // dragged anticlockwise past "now" and round the bottom: no jump
    expect(unwrapLaps(0, 0.7, 3)).toBe(0);
    expect(unwrapLaps(0, 0.4, 3)).toBe(0);
    expect(unwrapLaps(0, 0.1, 3)).toBeCloseTo(0.1);
    expect(unwrapLaps(3, 0.5, 3)).toBe(3);
    expect(unwrapLaps(3, 0.95, 3)).toBeCloseTo(2.95);
  });

  it('a fresh press jumps to the nearest in-range lap', () => {
    expect(unwrapLaps(0, 0.75, 3, true)).toBeCloseTo(0.75);
    expect(unwrapLaps(1.3, 0.1, 3, true)).toBeCloseTo(1.1);
    expect(unwrapLaps(0, 0.9, 0.5, true)).toBe(0.5);
  });

  it('snaps to 5 minutes; at or after now means live "now"', () => {
    expect(snapStart(at(9, 12), now)).toBe(at(9, 10));
    expect(snapStart(at(10, 4), now)).toBeNull();
    expect(snapStart(now - DIAL_MAX_MIN * 60_000 - 3_600_000, now)).toBe(at(10, 5) - DIAL_MAX_MIN * 60_000);
  });

  it('steps from now to the previous 5-minute mark, then by the step', () => {
    expect(nudgeStart(null, -5, now)).toBe(at(10, 0));
    expect(nudgeStart(null, -5, at(10, 0, 10))).toBe(at(9, 55));
    expect(nudgeStart(null, -60, now)).toBe(at(9, 5));
    expect(nudgeStart(null, 5, now)).toBeNull();
    expect(nudgeStart(at(9, 0), 5, now)).toBe(at(9, 5));
    expect(nudgeStart(at(10, 0), 5, now)).toBeNull();
  });

  it('turns ring laps of the target into a start time', () => {
    expect(startFromLaps(0, 8, now)).toBeNull();
    expect(startFromLaps(0.25, 8, now)).toBe(at(8, 5));
    expect(startFromLaps(1, 8, now)).toBe(at(2, 5));
  });

  it('flags a pick that rolled back past midnight', () => {
    expect(dialDay(at(0, 5), now)).toBe('');
    expect(dialDay(at(0, 5) - 10 * 60_000, now)).toBe('yesterday');
    expect(dialDay(snapStart(now - DIAL_MAX_MIN * 60_000, now)!, now)).toBe('yesterday');
  });

  it('only offers starts that the HH:MM sent to Python lands on (DST)', () => {
    vi.stubEnv('TZ', 'Europe/Helsinki');
    try {
      // spring forward: Sun 2027-03-28 10:00:20 EEST; yesterday is 23 wall-clock hours back
      const sun = Date.parse('2027-03-28T07:00:20Z');
      const earliest = snapStart(sun - DIAL_MAX_MIN * 60_000, sun)!;
      expect(new Date(earliest).toISOString()).toBe('2027-03-27T08:05:00.000Z'); // Sat 10:05 EET
      expect(dialDay(earliest, sun)).toBe('yesterday');
      // an ordinary day keeps the full 23h55 range
      const jan = Date.parse('2027-01-15T08:00:20Z');
      expect(snapStart(jan - DIAL_MAX_MIN * 60_000, jan)).toBe(Date.parse('2027-01-14T08:10:00Z')); // Thu 10:10;
    } finally {
      vi.unstubAllEnvs();
    }
  });

  it('says how long ago the picked start is', () => {
    expect(agoText(at(10, 0), now)).toBe('3m ago');
    expect(agoText(at(8, 45), now)).toBe('1h 18m ago');
  });
});
