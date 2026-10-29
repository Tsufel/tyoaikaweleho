import { describe, expect, it } from 'vitest';
import { FLAME_RATE, KIND_EMBER, KIND_FLAME, createFire } from '../src/fx/fire/fireSim';
import { WIZARD_LINE, WIZARD_POP_MS, shouldPopWizard } from '../src/fx/fire/wizardPop';

function seeded(seed = 1) {
  let s = seed;
  return () => ((s = (s * 16807) % 2147483647) - 1) / 2147483646;
}

describe('fire sim', () => {
  it('emits flames at FLAME_RATE × intensity, carrying fractions across frames', () => {
    const f = createFire(5000, seeded());
    let flames = 0;
    for (let k = 0; k < 30; k++) flames += f.emitRing(100, 100, 50, 1, 1 / 30);
    expect(flames).toBeGreaterThanOrEqual(FLAME_RATE - 1);
    expect(flames).toBeLessThanOrEqual(FLAME_RATE);
    expect(f.alive).toBeGreaterThanOrEqual(flames);
  });

  it('emits nothing at zero intensity or dt', () => {
    const f = createFire(100, seeded());
    expect(f.emitRing(0, 0, 10, 0, 1)).toBe(0);
    expect(f.emitRing(0, 0, 10, 1, 0)).toBe(0);
    expect(f.alive).toBe(0);
  });

  it('never exceeds capacity', () => {
    const f = createFire(50, seeded());
    for (let k = 0; k < 20; k++) f.emitRing(0, 0, 40, 1.4, 0.1);
    expect(f.alive).toBe(50);
    expect(f.burst(0, 0, 40)).toBe(0);
  });

  it('burst spawns the requested count with flames and embers', () => {
    const f = createFire(500, seeded());
    expect(f.burst(0, 0, 40, 90)).toBe(90);
    const kinds = new Set(Array.from(f.kind.slice(0, f.alive)));
    expect(kinds).toEqual(new Set([KIND_FLAME, KIND_EMBER]));
  });

  it('step ages particles and returns dead ones to the pool', () => {
    const f = createFire(500, seeded());
    f.burst(0, 0, 40, 60);
    f.step(0.05);
    expect(f.alive).toBe(60);
    for (let k = 0; k < 40; k++) f.step(0.1);
    expect(f.alive).toBe(0);
  });

  it('flames rise', () => {
    const f = createFire(500, seeded());
    f.emitRing(0, 0, 40, 1, 0.1);
    const before = Array.from(f.y.slice(0, f.alive));
    f.step(0.05);
    const risen = before.filter((y, i) => f.y[i] < y).length;
    expect(risen).toBeGreaterThan(before.length * 0.8);
  });

  it('heat and alpha stay within 0…1', () => {
    const f = createFire(500, seeded());
    f.burst(0, 0, 40);
    f.emitRing(0, 0, 40, 1.4, 0.1);
    for (let t = 0; t < 10; t++) {
      for (let i = 0; i < f.alive; i++) {
        expect(f.heat(i)).toBeGreaterThanOrEqual(0);
        expect(f.heat(i)).toBeLessThanOrEqual(1);
        expect(f.alpha(i)).toBeGreaterThanOrEqual(0);
        expect(f.alpha(i)).toBeLessThanOrEqual(1);
      }
      f.step(0.1);
    }
  });

  it('clear() empties the pool', () => {
    const f = createFire(100, seeded());
    f.burst(0, 0, 10, 30);
    f.clear();
    expect(f.alive).toBe(0);
  });
});

describe('clock-out wizard pop', () => {
  it('only pops with lulz on and full motion', () => {
    expect(shouldPopWizard(true, 'full')).toBe(true);
    expect(shouldPopWizard(true, 'reduced')).toBe(false);
    expect(shouldPopWizard(false, 'full')).toBe(false);
    expect(shouldPopWizard(false, 'reduced')).toBe(false);
  });

  it('runs about 2.5 s and says the line', () => {
    expect(WIZARD_POP_MS).toBeGreaterThanOrEqual(2000);
    expect(WIZARD_POP_MS).toBeLessThanOrEqual(3000);
    expect(WIZARD_LINE).toBe('sie oot weleho!');
  });
});
