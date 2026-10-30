import { describe, expect, it } from 'vitest';
import { lensLoad, shouldDowngrade } from '../src/lib/glass/frameGuard';

const frames = (n: number, ms: number) => Array.from({ length: n }, () => ms);

describe('shouldDowngrade', () => {
  it('needs enough samples before judging', () => {
    expect(shouldDowngrade(frames(19, 40))).toBe(false);
    expect(shouldDowngrade(frames(20, 40))).toBe(true);
    expect(shouldDowngrade([])).toBe(false);
  });

  it('passes smooth frame rates', () => {
    expect(shouldDowngrade(frames(120, 16.7))).toBe(false);
    expect(shouldDowngrade(frames(60, 24))).toBe(false);
  });

  it('trips when the median frame is slower than the limit', () => {
    expect(shouldDowngrade(frames(60, 33))).toBe(true);
    expect(shouldDowngrade(frames(60, 25))).toBe(true);
  });

  it('ignores a minority of hitches', () => {
    expect(shouldDowngrade([...frames(40, 16.7), ...frames(19, 100)])).toBe(false);
    expect(shouldDowngrade([...frames(19, 16.7), ...frames(41, 40)])).toBe(true);
  });

  it('averages the middle pair for even counts and honours custom limits', () => {
    const d = [...frames(10, 20), ...frames(10, 30)]; // median 25
    expect(shouldDowngrade(d)).toBe(true);
    expect(shouldDowngrade(d, 25)).toBe(false);
    expect(shouldDowngrade(frames(5, 40), 24, 5)).toBe(true);
  });
});

describe('lensLoad', () => {
  it('ignores the transient thumb and weights dispersion lenses', () => {
    const rim = { mask: 'rim' as const, dispersion: false };
    const modal = { mask: 'rim' as const, dispersion: true };
    const thumb = { mask: 'full' as const, dispersion: false };
    expect(lensLoad([])).toBe(0);
    expect(lensLoad([rim])).toBe(1);
    expect(lensLoad([rim, thumb])).toBe(1);
    expect(lensLoad([rim, modal])).toBe(4);
  });
});
