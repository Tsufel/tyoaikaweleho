import { describe, expect, it } from 'vitest';
import {
  FLAME_RATE,
  KIND_CORE,
  KIND_EMBER,
  KIND_FLAME,
  KIND_SMOKE,
  KIND_SPARK,
  createFire,
} from '../src/fx/fire/fireSim';
import { RING } from '../src/views/timer/timerLogic';
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
    expect(kinds).toContain(KIND_FLAME);
    expect(kinds).toContain(KIND_EMBER);
    expect(kinds).toContain(KIND_SPARK);
  });

  it('burst takes the overtime palette', () => {
    const f = createFire(500, seeded());
    f.burst(0, 0, 40, 60, 1);
    for (let i = 0; i < f.alive; i++) expect(f.pal[i]).toBe(1);
    const g = createFire(500, seeded());
    g.burst(0, 0, 40, 60);
    for (let i = 0; i < g.alive; i++) expect(g.pal[i]).toBe(0);
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
    expect(f.time).toBe(0);
  });

  const flameAngles = (f: ReturnType<typeof createFire>, cx: number, cy: number) => {
    const out: { a: number; d: number }[] = [];
    for (let i = 0; i < f.alive; i++) {
      if (f.kind[i] !== KIND_FLAME) continue;
      const dx = f.x[i] - cx;
      const dy = f.y[i] - cy;
      let a = Math.atan2(dx, -dy); // 0 at 12 o'clock, clockwise
      if (a < 0) a += Math.PI * 2;
      out.push({ a, d: Math.hypot(dx, dy) });
    }
    return out;
  };

  it('spawns flames on the outer edge of the ring stroke', () => {
    const f = createFire(5000, seeded(3));
    f.emitRing(RING.size / 2, RING.size / 2, RING.r, 1, 0.1);
    const pts = flameAngles(f, RING.size / 2, RING.size / 2);
    expect(pts.length).toBeGreaterThan(10);
    for (const p of pts) {
      expect(p.d).toBeGreaterThanOrEqual(RING.r * 1.05);
      expect(p.d).toBeLessThanOrEqual(RING.r * 1.12);
    }
  });

  it('arc-limited emission keeps flames inside the arc', () => {
    const f = createFire(5000, seeded(4));
    let n = 0;
    for (let k = 0; k < 10; k++) n += f.emitRing(120, 120, 100, 1, 0.05, { arcFrom: 0.5, arcTo: 1.5 });
    expect(n).toBeGreaterThan(50);
    for (const p of flameAngles(f, 120, 120)) {
      expect(p.a).toBeGreaterThanOrEqual(0.5 - 1e-4);
      expect(p.a).toBeLessThanOrEqual(1.5 + 1e-4);
    }
    expect(f.emitRing(120, 120, 100, 1, 0.1, { arcFrom: 2, arcTo: 1 })).toBe(0);
  });

  it('flare whooshes tall flames and sparks', () => {
    const f = createFire(5000, seeded(5));
    expect(f.flare(120, 120, 100)).toBe(180);
    const kinds = Array.from(f.kind.slice(0, f.alive));
    expect(kinds.filter((k) => k === KIND_FLAME)).toHaveLength(140);
    expect(kinds.filter((k) => k === KIND_SPARK)).toHaveLength(40);
    for (let i = 0; i < f.alive; i++) {
      if (f.kind[i] !== KIND_FLAME) continue;
      expect(f.vy[i]).toBeLessThanOrEqual(-160 + 1e-3);
      expect(f.vy[i]).toBeGreaterThanOrEqual(-260 - 1e-3);
    }
    const g = createFire(5000, seeded(5));
    expect(g.flare(120, 120, 100, 2)).toBe(360);
    for (let i = 0; i < g.alive; i++) if (g.kind[i] === KIND_FLAME) expect(g.vy[i]).toBeLessThanOrEqual(-320 + 1e-3);
    expect(f.flare(120, 120, 100, 0.5)).toBe(90);
    expect(f.flare(120, 120, 100, 0)).toBe(0);
  });

  it('arc emission wraps across 12 o’clock (angle 0 at top, clockwise)', () => {
    const f = createFire(5000, seeded(15));
    for (let k = 0; k < 10; k++) f.emitRing(120, 120, 100, 1, 0.05, { arcFrom: -0.3, arcTo: 0.3 });
    const pts = flameAngles(f, 120, 120);
    expect(pts.length).toBeGreaterThan(50);
    for (const { a } of pts) expect(a <= 0.3 + 1e-4 || a >= Math.PI * 2 - 0.3 - 1e-4).toBe(true);
    // a short arc just past 12 o'clock sits above the centre, slightly right
    const g = createFire(5000, seeded(15));
    g.emitRing(120, 120, 100, 1, 0.1, { arcFrom: 0.1, arcTo: 0.2 });
    for (let i = 0; i < g.alive; i++) {
      if (g.kind[i] !== KIND_FLAME) continue;
      expect(g.x[i]).toBeGreaterThan(120);
      expect(g.y[i]).toBeLessThan(120 - 90);
    }
  });

  it('rate scales emission and bad numbers never poison the carry', () => {
    const half = createFire(5000, seeded(16));
    let n = 0;
    for (let k = 0; k < 30; k++) n += half.emitRing(100, 100, 50, 1, 1 / 30, { rate: 0.5 });
    expect(n).toBeGreaterThanOrEqual(FLAME_RATE / 2 - 1);
    expect(n).toBeLessThanOrEqual(FLAME_RATE / 2);
    const f = createFire(5000, seeded(16));
    expect(f.emitRing(100, 100, 50, 1, NaN)).toBe(0);
    expect(f.emitRing(100, 100, 50, 1, 0.1, { rate: NaN })).toBe(0);
    expect(f.emitRing(100, 100, 50, 1, 0.1, { arcFrom: NaN, arcTo: 1 })).toBe(0);
    expect(f.emitRing(100, 100, 50, NaN, 0.1)).toBe(0);
    expect(f.alive).toBe(0);
    expect(f.emitRing(100, 100, 50, 1, 0.1)).toBe(FLAME_RATE / 10);
    for (let i = 0; i < f.alive; i++) expect(Number.isFinite(f.x[i] + f.y[i] + f.vx[i] + f.vy[i])).toBe(true);
  });

  it('swap-remove keeps per-particle arrays together', () => {
    // blue particles live far left, fire-palette ones far right; kills must never mix them up
    const f = createFire(3000, seeded(17));
    for (let k = 0; k < 40; k++) {
      f.emitRing(0, 0, 100, 1.6, 1 / 30, { blue: 1 });
      f.emitRing(10000, 0, 100, 1.6, 1 / 30);
      if (k % 10 === 0) f.flare(0, 0, 100, 1, 1);
      if (k % 10 === 5) f.burst(10000, 0, 100, 60);
      f.step(1 / 30);
      for (let i = 0; i < f.alive; i++) {
        expect(f.pal[i]).toBe(f.x[i] < 5000 ? 1 : 0);
        expect(f.seed[i]).toBeGreaterThanOrEqual(0);
        expect(f.seed[i]).toBeLessThan(1);
        expect(f.life[i]).toBeLessThanOrEqual(f.maxLife[i] + 1e-6);
      }
    }
  });

  it('douse caps flame life, adds smoke and drops embers', () => {
    const f = createFire(5000, seeded(6));
    f.emitRing(120, 120, 100, 1.6, 0.1);
    f.flare(120, 120, 100);
    f.burst(120, 120, 100, 60);
    const before = f.alive;
    const puffs = f.douse();
    expect(puffs).toBeGreaterThanOrEqual(30);
    expect(f.alive).toBe(before + puffs);
    let smoke = 0;
    for (let i = 0; i < f.alive; i++) {
      if (f.kind[i] === KIND_FLAME) expect(f.life[i]).toBeLessThanOrEqual(0.2 + 1e-6);
      if (f.kind[i] === KIND_EMBER) expect(f.vy[i]).toBeGreaterThan(0);
      if (f.kind[i] === KIND_SMOKE) smoke++;
    }
    expect(smoke).toBe(puffs);
    // with no flames left it puffs around the last emit centre
    f.clear();
    expect(f.douse()).toBe(0);
    f.emitRing(120, 120, 100, 0, 0.1);
    expect(f.douse()).toBeGreaterThan(0);
    for (let i = 0; i < f.alive; i++) {
      expect(f.kind[i]).toBe(KIND_SMOKE);
      expect(Math.hypot(f.x[i] - 120, f.y[i] - 120)).toBeCloseTo(RING.r * (1 + RING.stroke / 2 / RING.r), 1);
    }
  });

  const smokeAfter = (intensity: number) => {
    const f = createFire(5000, seeded(7));
    let smoke = 0;
    for (let k = 0; k < 120; k++) {
      f.emitRing(120, 120, 100, intensity, 1 / 30);
      f.step(1 / 30);
      for (let i = 0; i < f.alive; i++) if (f.kind[i] === KIND_SMOKE) smoke++;
    }
    return smoke;
  };

  it('dying flames only turn to smoke at high intensity', () => {
    expect(smokeAfter(0.45)).toBe(0);
    expect(smokeAfter(1.6)).toBeGreaterThan(0);
  });

  it('setSmoke(false) disables smoke conversion', () => {
    const f = createFire(5000, seeded(8));
    f.setSmoke(false);
    for (let k = 0; k < 120; k++) {
      f.emitRing(120, 120, 100, 1.6, 1 / 30);
      f.step(1 / 30);
      for (let i = 0; i < f.alive; i++) expect(f.kind[i]).not.toBe(KIND_SMOKE);
    }
  });

  it('cores start white hot', () => {
    const f = createFire(5000, seeded(9));
    f.emitRing(120, 120, 100, 1, 0.1);
    let cores = 0;
    for (let i = 0; i < f.alive; i++) {
      if (f.kind[i] !== KIND_CORE) continue;
      cores++;
      expect(f.heat(i)).toBeLessThan(0.15);
    }
    expect(cores).toBeGreaterThan(0);
  });

  it('flicker stays within 0.5…1', () => {
    const f = createFire(5000, seeded(10));
    for (let k = 0; k < 60; k++) {
      f.emitRing(120, 120, 100, 1.2, 1 / 30);
      f.step(1 / 30);
      for (let i = 0; i < f.alive; i++) {
        expect(f.flicker(i)).toBeGreaterThanOrEqual(0.5);
        expect(f.flicker(i)).toBeLessThanOrEqual(1);
      }
    }
  });

  it('turbulence nudges velocity by a bounded amount', () => {
    const calm = createFire(5000, seeded(11));
    const wild = createFire(5000, seeded(11));
    calm.setField({ strength: 0 });
    calm.emitRing(120, 120, 100, 1, 0.1);
    wild.emitRing(120, 120, 100, 1, 0.1);
    const d = 0.05;
    calm.step(d);
    wild.step(d);
    expect(wild.alive).toBe(calm.alive);
    let maxDiff = 0;
    for (let i = 0; i < calm.alive; i++) maxDiff = Math.max(maxDiff, Math.abs(wild.vx[i] - calm.vx[i]));
    expect(maxDiff).toBeGreaterThan(0);
    expect(maxDiff).toBeLessThanOrEqual(220 * d + 1e-3);
    // accel is linear in strength
    const wild2 = createFire(5000, seeded(11));
    wild2.setField({ strength: 2 });
    wild2.emitRing(120, 120, 100, 1, 0.1);
    wild2.step(d);
    for (let i = 0; i < calm.alive; i++) {
      expect(wild2.vx[i] - calm.vx[i]).toBeCloseTo(2 * (wild.vx[i] - calm.vx[i]), 2);
    }
  });

  it('never exceeds capacity under flare + burst + emit spam', () => {
    const f = createFire(300, seeded(12));
    for (let k = 0; k < 60; k++) {
      f.emitRing(120, 120, 100, 1.6, 0.1, { rate: 2 });
      if (k % 5 === 0) f.flare(120, 120, 100, 2);
      if (k % 7 === 0) f.burst(120, 120, 100);
      if (k % 11 === 0) f.douse();
      expect(f.alive).toBeLessThanOrEqual(300);
      f.step(1 / 30);
      expect(f.alive).toBeLessThanOrEqual(300);
    }
  });

  it('blue option picks the overtime palette', () => {
    const blue = createFire(5000, seeded(13));
    blue.emitRing(120, 120, 100, 1.4, 0.1, { blue: 1 });
    expect(blue.alive).toBeGreaterThan(0);
    for (let i = 0; i < blue.alive; i++) expect(blue.pal[i]).toBe(1);
    const fire = createFire(5000, seeded(13));
    fire.emitRing(120, 120, 100, 1.4, 0.1, { blue: 0 });
    for (let i = 0; i < fire.alive; i++) expect(fire.pal[i]).toBe(0);
    const mixed = createFire(5000, seeded(13));
    for (let k = 0; k < 10; k++) mixed.emitRing(120, 120, 100, 1.4, 0.1, { blue: 0.5 });
    const blues = Array.from(mixed.pal.slice(0, mixed.alive)).filter((p) => p === 1).length;
    expect(blues / mixed.alive).toBeGreaterThan(0.35);
    expect(blues / mixed.alive).toBeLessThan(0.65);
    const flare = createFire(5000, seeded(13));
    flare.flare(120, 120, 100, 1, 1);
    for (let i = 0; i < flare.alive; i++) expect(flare.pal[i]).toBe(1);
  });

  it('stays finite and in range over 600 steps', () => {
    const f = createFire(1600, seeded(14));
    for (let k = 0; k < 600; k++) {
      f.emitRing(120, 120, 100, 0.2 + (k % 100) / 70, 1 / 60, { blue: k > 300 ? 0.5 : 0 });
      if (k % 150 === 0) f.flare(120, 120, 100, 1.5);
      if (k % 200 === 100) f.burst(120, 120, 100);
      if (k === 450) f.douse();
      f.step(1 / 60);
    }
    expect(f.alive).toBeGreaterThan(0);
    for (let i = 0; i < f.alive; i++) {
      for (const v of [f.x[i], f.y[i], f.vx[i], f.vy[i], f.size[i], f.life[i]]) expect(Number.isFinite(v)).toBe(true);
      for (const v of [f.heat(i), f.alpha(i)]) {
        expect(v).toBeGreaterThanOrEqual(0);
        expect(v).toBeLessThanOrEqual(1);
      }
    }
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
