import { describe, expect, it } from 'vitest';
import { lehmer } from '../src/fx/fire/noise';
import {
  MAX_BOUNCES,
  MAX_LIFE,
  O_CONFETTI,
  O_EMBER,
  O_PUFF,
  O_SMOKE,
  O_SPARK,
  SHOCK_SLOTS,
  createOverlaySim,
  type OverlaySim,
} from '../src/fx/fire/overlaySim';

const W = 960;
const H = 760;

function kinds(s: OverlaySim): Set<number> {
  return new Set(Array.from(s.kind.slice(0, s.alive)));
}

function countKind(s: OverlaySim, k: number): number {
  let n = 0;
  for (let i = 0; i < s.alive; i++) if (s.kind[i] === k) n++;
  return n;
}

function liveShocks(s: OverlaySim): number {
  return s.shocks.filter((sh) => sh.alive).length;
}

describe('overlay sim', () => {
  it('blast spawns sparks, puffs, confetti and embers with a flash and two shockwaves', () => {
    const s = createOverlaySim(3000, lehmer(7));
    const n = s.blast(480, 380);
    expect(n).toBe(36 + 380 + 110 + 80);
    expect(s.alive).toBe(n);
    expect(kinds(s)).toEqual(new Set([O_SPARK, O_PUFF, O_CONFETTI, O_EMBER]));
    expect(s.flash).toBeCloseTo(0.9);
    expect(s.flashX).toBe(480);
    expect(s.flashY).toBe(380);
    expect(liveShocks(s)).toBe(2);
    expect(s.shocks).toHaveLength(6);
    expect(s.active).toBe(true);
  });

  it('sparks bounce off the floor and die on the third hit', () => {
    const s = createOverlaySim(500, lehmer(3));
    s.flare(480, 380, 1);
    for (let i = 0; i < s.alive; i++) {
      s.x[i] = W / 2;
      s.y[i] = H - 2;
      s.vx[i] = 0;
      s.vy[i] = 800;
      s.life[i] = s.maxLife[i] = 3.9;
    }
    const n = s.alive;
    let flipped = false;
    let maxBounces = 0;
    for (let k = 0; k < 120 && s.alive > 0; k++) {
      s.step(1 / 60, W, H);
      for (let i = 0; i < s.alive; i++) {
        expect(s.y[i]).toBeLessThanOrEqual(H);
        if (s.bounces[i] > 0 && s.vy[i] < 0) flipped = true;
        maxBounces = Math.max(maxBounces, s.bounces[i]);
      }
    }
    expect(n).toBeGreaterThan(0);
    expect(flipped).toBe(true);
    expect(maxBounces).toBe(MAX_BOUNCES - 1);
    expect(s.alive).toBe(0);
  });

  it('first bounce flips vy with restitution', () => {
    const s = createOverlaySim(500, lehmer(4));
    s.flare(480, 380, 1);
    for (let i = 0; i < s.alive; i++) {
      s.x[i] = W / 2;
      s.y[i] = H - 1;
      s.vx[i] = 100;
      s.vy[i] = 600;
    }
    s.step(1 / 60, W, H);
    for (let i = 0; i < s.alive; i++) {
      expect(s.bounces[i]).toBe(1);
      expect(s.vy[i]).toBeLessThan(0);
      expect(s.y[i]).toBe(H);
      expect(Math.abs(s.vx[i])).toBeLessThan(100);
    }
  });

  it('goes fully inactive within 4.2 s with finite positions throughout', () => {
    const s = createOverlaySim(3000, lehmer(11));
    s.blast(480, 600, { power: 1.5 });
    s.flare(300, 300, 4, { pal: 1 });
    s.fizzle(700, 500);
    let ok = true;
    for (let t = 0; t < 4.2; t += 1 / 60) {
      s.step(1 / 60, W, H);
      for (let i = 0; i < s.alive; i++) {
        if (!Number.isFinite(s.x[i]) || !Number.isFinite(s.y[i]) || !Number.isFinite(s.size[i])) ok = false;
        const a = s.alpha(i);
        const h = s.heat(i);
        if (!(a >= 0 && a <= 1 && h >= 0 && h <= 1)) ok = false;
      }
      for (const sh of s.shocks) if (sh.alive && !Number.isFinite(sh.r)) ok = false;
    }
    expect(ok).toBe(true);
    expect(s.alive).toBe(0);
    expect(s.flash).toBe(0);
    expect(liveShocks(s)).toBe(0);
    expect(s.banner).toBeNull();
    expect(s.active).toBe(false);
  });

  it('flash decays monotonically to zero', () => {
    const s = createOverlaySim(3000, lehmer(5));
    s.blast(100, 100);
    let prev = s.flash;
    for (let k = 0; k < 120; k++) {
      s.step(1 / 60, W, H);
      expect(s.flash).toBeLessThanOrEqual(prev);
      prev = s.flash;
    }
    expect(s.flash).toBe(0);
  });

  it('shockwaves expand and ease out', () => {
    const s = createOverlaySim(3000, lehmer(5));
    s.blast(100, 100);
    const sh = s.shocks.find((x) => x.alive)!;
    s.step(1 / 60, W, H);
    const r1 = sh.r;
    const v1 = sh.v;
    s.step(1 / 60, W, H);
    expect(sh.r).toBeGreaterThan(r1);
    expect(sh.v).toBeLessThan(v1);
  });

  it('higher tiers spawn more and only tier >= 2 shows a banner', () => {
    let prev = 0;
    for (const tier of [1, 2, 3, 4] as const) {
      const s = createOverlaySim(3000, lehmer(9));
      const n = s.flare(480, 380, tier, { label: tier === 3 ? 'Target!' : undefined, pal: 1 });
      expect(n).toBeGreaterThan(prev);
      prev = n;
      if (tier === 1) {
        expect(s.banner).toBeNull();
        expect(s.flash).toBe(0);
      } else {
        expect(s.banner).not.toBeNull();
        expect(s.banner!.pal).toBe(1);
        expect(s.banner!.life).toBe(tier === 4 ? 2 : 1.6);
        expect(s.flash).toBeGreaterThan(0);
      }
      if (tier === 3) expect(s.banner!.text).toBe('Target!');
      expect(liveShocks(s)).toBe(tier >= 3 ? 2 : 1);
    }
  });

  it('banner expires on its own', () => {
    const s = createOverlaySim(3000, lehmer(9));
    s.flare(480, 380, 2);
    for (let k = 0; k < 100; k++) s.step(1 / 60, W, H);
    expect(s.banner).toBeNull();
  });

  it('scale 0.5 roughly halves counts', () => {
    const full = createOverlaySim(3000, lehmer(2)).blast(480, 380);
    const half = createOverlaySim(3000, lehmer(2)).blast(480, 380, { scale: 0.5 });
    expect(half).toBeGreaterThanOrEqual(Math.floor(full / 2) - 2);
    expect(half).toBeLessThanOrEqual(Math.ceil(full / 2) + 2);
    const s = createOverlaySim(3000, lehmer(2));
    s.flare(480, 380, 4, { scale: 0.5 });
    expect(countKind(s, O_SPARK)).toBe(225);
  });

  it('respects capacity under repeated blasts', () => {
    const s = createOverlaySim(800, lehmer(6));
    expect(() => {
      for (let k = 0; k < 5; k++) {
        s.blast(480, 380, { power: 2 });
        s.step(1 / 60, W, H);
      }
    }).not.toThrow();
    expect(s.alive).toBe(800);
    expect(s.blast(480, 380)).toBe(0);
  });

  it('fizzle produces smoke and dim sparks only, no flash or shock', () => {
    const s = createOverlaySim(3000, lehmer(8));
    const n = s.fizzle(480, 380);
    expect(n).toBe(45);
    expect(kinds(s)).toEqual(new Set([O_SMOKE, O_SPARK]));
    expect(countKind(s, O_SMOKE)).toBe(20);
    expect(s.flash).toBe(0);
    expect(liveShocks(s)).toBe(0);
    expect(s.banner).toBeNull();
    for (let i = 0; i < s.alive; i++) if (s.kind[i] === O_SPARK) expect(s.alpha(i)).toBeLessThanOrEqual(0.5);
    // smoke rises
    const y0 = s.y[0];
    for (let k = 0; k < 30; k++) s.step(1 / 60, W, H);
    expect(s.y[0]).toBeLessThan(y0);
  });

  it('clear resets everything', () => {
    const s = createOverlaySim(3000, lehmer(1));
    s.blast(10, 10);
    s.flare(10, 10, 4);
    s.clear();
    expect(s.alive).toBe(0);
    expect(s.active).toBe(false);
  });

  it('swap-remove keeps every per-particle field together', () => {
    const s = createOverlaySim(3000, lehmer(21));
    s.blast(480, 600);
    s.fizzle(300, 500);
    // seeds are unique enough to act as identities; remember what each particle was at birth
    const born = new Map<number, { kind: number; maxLife: number; dim: boolean }>();
    for (let i = 0; i < s.alive; i++) {
      born.set(s.seed[i], { kind: s.kind[i], maxLife: s.maxLife[i], dim: s.kind[i] === O_SPARK && s.heat(i) > 0.4 });
    }
    expect(born.size).toBe(s.alive);
    // plain checks + one assert: ~600k expect() calls would blow the timeout under load
    const bad: string[] = [];
    for (let k = 0; k < 150; k++) {
      s.step(1 / 60, W, H);
      for (let i = 0; i < s.alive; i++) {
        const b = born.get(s.seed[i]);
        const why = !b
          ? 'unknown seed'
          : s.kind[i] !== b.kind
            ? 'kind'
            : s.maxLife[i] !== b.maxLife
              ? 'maxLife'
              : !(s.life[i] > 0 && s.life[i] <= s.maxLife[i])
                ? 'life range'
                : s.maxLife[i] > MAX_LIFE
                  ? 'maxLife cap'
                  : // fizzle sparks stay dim after their slot moves (gain/heat0 travel with them)
                    b.dim && s.alpha(i) > 0.46
                    ? 'dim spark brightened'
                    : '';
        if (why && bad.length < 5) bad.push(`step ${k} slot ${i}: ${why}`);
      }
    }
    expect(bad).toEqual([]);
  });

  it('side walls reflect with damping', () => {
    const s = createOverlaySim(10, lehmer(1));
    s.flare(480, 380, 1, { scale: 2 / 120 });
    expect(s.alive).toBe(2);
    s.x[0] = W - 1;
    s.vx[0] = 600;
    s.x[1] = 1;
    s.vx[1] = -600;
    for (let i = 0; i < 2; i++) {
      s.y[i] = 300;
      s.vy[i] = 0;
    }
    s.step(1 / 60, W, H);
    // the two may have swapped slots only on a kill; none happened
    expect(s.alive).toBe(2);
    expect(s.x[0]).toBe(W);
    expect(s.vx[0]).toBeLessThan(0);
    expect(Math.abs(s.vx[0])).toBeLessThan(600 * 0.6 + 1);
    expect(s.x[1]).toBe(0);
    expect(s.vx[1]).toBeGreaterThan(0);
  });

  it('culls far left/right/below but never above the top', () => {
    const s = createOverlaySim(10, lehmer(1));
    s.flare(480, 380, 1, { scale: 4 / 120 });
    expect(s.alive).toBe(4);
    const place = (i: number, px: number, py: number) => {
      s.x[i] = px;
      s.y[i] = py;
      s.vx[i] = 0;
      s.vy[i] = -50;
      s.life[i] = s.maxLife[i] = 3;
    };
    place(0, W / 2, -1500); // way above: kept
    place(1, -300, 300);
    place(2, W + 300, 300);
    place(3, W / 2, H + 400); // window shrank under it: culled, not dragged back to the floor
    s.step(1 / 60, W, H);
    expect(s.alive).toBe(1);
    expect(s.y[0]).toBeLessThan(-1400);
  });

  it('shockwaves stay within their fixed slots', () => {
    const s = createOverlaySim(3000, lehmer(3));
    for (let k = 0; k < 5; k++) s.blast(100 * k, 100);
    expect(s.shocks).toHaveLength(SHOCK_SLOTS);
    expect(liveShocks(s)).toBe(SHOCK_SLOTS);
    // the newest blast's rings are among the live ones
    expect(s.shocks.filter((sh) => sh.x === 400 && sh.alive)).toHaveLength(2);
    // a later flare evicts the most-spent ring, not a fresh one
    s.step(0.03, W, H);
    s.flare(900, 100, 1);
    const live = s.shocks.filter((sh) => sh.alive);
    expect(live).toHaveLength(SHOCK_SLOTS);
    expect(live.filter((sh) => sh.x === 900)).toHaveLength(1);
    expect(live.filter((sh) => sh.x === 400)).toHaveLength(2);
  });

  it('spawn speeds scale with the window size', () => {
    const maxSpeed = (s: OverlaySim) => {
      let m = 0;
      for (let i = 0; i < s.alive; i++) if (s.kind[i] === O_SPARK) m = Math.max(m, Math.hypot(s.vx[i], s.vy[i]));
      return m;
    };
    const big = createOverlaySim(3000, lehmer(2));
    big.blast(480, 380, { W: 1400, H: 1400 });
    const small = createOverlaySim(3000, lehmer(2));
    small.blast(480, 380, { W: 350, H: 350 });
    expect(maxSpeed(small)).toBeCloseTo(maxSpeed(big) / 4, 0);
    expect(maxSpeed(big)).toBeLessThanOrEqual((1500 + 300) * 2 + 1);
  });

  it('ignores non-finite origins, tiers and window sizes', () => {
    const s = createOverlaySim(3000, lehmer(4));
    expect(s.blast(NaN, 100)).toBe(0);
    expect(s.flare(100, Infinity, 2)).toBe(0);
    expect(s.fizzle(NaN, NaN)).toBe(0);
    expect(s.active).toBe(false);
    s.flare(100, 100, NaN as unknown as 1);
    s.blast(100, 100, { W: NaN, H: 0 });
    expect(Number.isFinite(s.flash)).toBe(true);
    for (let k = 0; k < 20; k++) s.step(1 / 60, NaN, H);
    s.step(NaN, W, H);
    for (let i = 0; i < s.alive; i++) {
      expect(Number.isFinite(s.x[i]) && Number.isFinite(s.y[i]) && Number.isFinite(s.vy[i])).toBe(true);
    }
  });

  it('is deterministic for a seeded rand', () => {
    const a = createOverlaySim(3000, lehmer(42));
    const b = createOverlaySim(3000, lehmer(42));
    a.blast(480, 380);
    b.blast(480, 380);
    for (let k = 0; k < 30; k++) {
      a.step(1 / 60, W, H);
      b.step(1 / 60, W, H);
    }
    expect(Array.from(a.x.slice(0, a.alive))).toEqual(Array.from(b.x.slice(0, b.alive)));
  });
});
