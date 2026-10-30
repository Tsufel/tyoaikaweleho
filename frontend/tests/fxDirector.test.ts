import { describe, expect, it } from 'vitest';
import { ANCHOR_FRESH_MS, blastPower, fxOrigin, shakeKey } from '../src/fx/fire/FxDirector.svelte';
import { SHAKE } from '../src/fx/fire/choreo';

describe('fx director helpers', () => {
  it('uses a fresh ring anchor, else the window centre', () => {
    const a = { x: 120, y: 340, r: 90, at: 1000 };
    expect(fxOrigin(a, 1000 + ANCHOR_FRESH_MS, 800, 600)).toEqual({ x: 120, y: 340, ring: true });
    expect(fxOrigin(a, 1001 + ANCHOR_FRESH_MS, 800, 600)).toEqual({ x: 400, y: 300, ring: false });
    expect(fxOrigin(null, 0, 800, 600)).toEqual({ x: 400, y: 300, ring: false });
    expect(fxOrigin({ ...a, x: NaN }, 1000, 800, 600).ring).toBe(false);
  });

  it('scales blast power mildly with the shift length', () => {
    expect(blastPower(null)).toBe(1);
    expect(blastPower(NaN)).toBe(1);
    expect(blastPower(0)).toBeCloseTo(0.9);
    expect(blastPower(480)).toBeCloseTo(1.2);
    expect(blastPower(10_000)).toBeCloseTo(1.3);
    expect(blastPower(-5)).toBeCloseTo(0.9);
  });

  it('maps every tier to a shake preset', () => {
    for (const t of [1, 2, 3, 4] as const) expect(SHAKE[shakeKey(t)]).toHaveLength(2);
  });
});
