import { describe, expect, it } from 'vitest';
import { IGNITE_MS, SHAKE, boostEnvelope, fuseProgress, gust, shakeKeyframes } from '../src/fx/fire/choreo';
import { createNoise, lehmer } from '../src/fx/fire/noise';
import { hexToRgb, lerpPalette, mixRgb, paletteSteps } from '../src/fx/fire/palette';
import { LEVELS, createFramePacer, createGovernor } from '../src/fx/fire/quality';
import { FIRE, FIRE_BLUE, FIRE_HOT } from '../src/lib/theme/tokens';

describe('noise', () => {
  it('lehmer stays in [0, 1) and is deterministic', () => {
    const a = lehmer(42);
    const b = lehmer(42);
    for (let i = 0; i < 5000; i++) {
      const v = a();
      expect(v).toBeGreaterThanOrEqual(0);
      expect(v).toBeLessThan(1);
      expect(b()).toBe(v);
    }
  });

  it('n1/n3 stay in [-1, 1], are deterministic per seed and differ across seeds', () => {
    const a = createNoise(7);
    const b = createNoise(7);
    const c = createNoise(8);
    let diff = 0;
    for (let i = 0; i < 4000; i++) {
      const x = i * 0.137 - 200;
      const y = i * 0.071 + 3.3;
      const z = i * 0.013;
      const v1 = a.n1(x);
      const v3 = a.n3(x, y, z);
      expect(Math.abs(v1)).toBeLessThanOrEqual(1);
      expect(Math.abs(v3)).toBeLessThanOrEqual(1);
      expect(b.n1(x)).toBe(v1);
      expect(b.n3(x, y, z)).toBe(v3);
      if (c.n3(x, y, z) !== v3) diff++;
    }
    expect(diff).toBeGreaterThan(3000);
  });

  it('curl is finite and within [-1, 1]', () => {
    const n = createNoise(3);
    const out = { x: 0, y: 0 };
    let moved = 0;
    for (let i = 0; i < 2000; i++) {
      n.curl(i * 0.31, i * 0.17 - 50, i * 0.05, out);
      expect(Number.isFinite(out.x) && Number.isFinite(out.y)).toBe(true);
      expect(Math.abs(out.x)).toBeLessThanOrEqual(1);
      expect(Math.abs(out.y)).toBeLessThanOrEqual(1);
      if (Math.abs(out.x) + Math.abs(out.y) > 0.05) moved++;
    }
    expect(moved).toBeGreaterThan(500);
  });
});

describe('palette', () => {
  it('parses hex and mixes', () => {
    expect(hexToRgb('#ff9f1c')).toEqual([255, 159, 28]);
    expect(hexToRgb('#fff')).toEqual([255, 255, 255]);
    expect(() => hexToRgb('red')).toThrow();
    expect(mixRgb([0, 0, 0], [200, 100, 50], 0.5)).toEqual([100, 50, 25]);
    expect(mixRgb([0, 0, 0], [200, 100, 50], 2)).toEqual([200, 100, 50]);
  });

  it('lerpPalette hits endpoints, clamps, and interpolates the midpoint', () => {
    expect(lerpPalette(['#000000', '#ffffff'], 0)).toBe('rgb(0,0,0)');
    expect(lerpPalette(['#000000', '#ffffff'], 1)).toBe('rgb(255,255,255)');
    expect(lerpPalette(['#000000', '#ffffff'], -3)).toBe('rgb(0,0,0)');
    expect(lerpPalette(['#000000', '#ffffff'], 9)).toBe('rgb(255,255,255)');
    expect(lerpPalette(['#000000', '#c86432'], 0.5)).toBe('rgb(100,50,25)');
    // 3 stops: midpoint is exactly the middle stop
    expect(lerpPalette(['#000000', '#ff9f1c', '#ffffff'], 0.5)).toBe('rgb(255,159,28)');
    expect(lerpPalette(FIRE, 1)).toBe('rgb(106,4,15)');
  });

  it('paletteSteps returns n colours with exact endpoints', () => {
    const s = paletteSteps(FIRE_BLUE, 9);
    expect(s).toHaveLength(9);
    expect(s[0]).toBe('rgb(255,255,255)');
    expect(s[8]).toBe('rgb(30,27,75)');
    expect(paletteSteps(FIRE, 1)).toHaveLength(2);
  });

  it('hexToRgb hands out copies (cache cannot be poisoned) and rejects junk', () => {
    const a = hexToRgb('#123456');
    a[0] = 999;
    expect(hexToRgb('#123456')).toEqual([0x12, 0x34, 0x56]);
    expect(lerpPalette(['#123456'], 0.7)).toBe('rgb(18,52,86)');
    for (const bad of ['#12345', '#gggggg', '123456', '']) expect(() => hexToRgb(bad)).toThrow();
    expect(() => lerpPalette([], 0)).toThrow();
  });

  it('lerpPalette is piecewise-linear across evenly spaced stops; NaN t → first stop', () => {
    const stops = ['#000000', '#ff0000', '#ffffff'];
    expect(lerpPalette(stops, 0.25)).toBe('rgb(128,0,0)');
    expect(lerpPalette(stops, 0.75)).toBe('rgb(255,128,128)');
    expect(lerpPalette(stops, NaN)).toBe('rgb(0,0,0)');
    // each stop is hit exactly at i / (len - 1)
    FIRE_HOT.forEach((c, i) => {
      const [r, g, b] = hexToRgb(c);
      expect(lerpPalette(FIRE_HOT, i / (FIRE_HOT.length - 1))).toBe(`rgb(${r},${g},${b})`);
    });
  });

  it('paletteSteps samples evenly and survives silly n', () => {
    const rgb = (c: string) => `rgb(${hexToRgb(c).join(',')})`;
    expect(paletteSteps(FIRE, FIRE.length)).toEqual(FIRE.map(rgb));
    expect(paletteSteps(['#000000', '#ffffff'], 3)).toEqual(['rgb(0,0,0)', 'rgb(128,128,128)', 'rgb(255,255,255)']);
    expect(paletteSteps(FIRE, NaN)).toHaveLength(2);
    expect(paletteSteps(FIRE, -Infinity)).toHaveLength(2);
    expect(paletteSteps(FIRE, 4.9)).toHaveLength(4);
    const big = paletteSteps(FIRE, Infinity);
    expect(big.length).toBeLessThanOrEqual(4096);
    expect(big[big.length - 1]).toBe(rgb(FIRE[FIRE.length - 1]));
  });

  it('fire tokens: FIRE_HOT prepends white, FIRE_BLUE has 6 stops', () => {
    expect(FIRE_HOT).toEqual(['#ffffff', ...FIRE]);
    expect(FIRE_BLUE).toHaveLength(6);
    expect(FIRE).toEqual(['#fff7d6', '#ffd166', '#ff9f1c', '#ff5d2a', '#d62828', '#6a040f']);
    // hot → cool: luminance falls along both ramps
    const lum = (c: string) => hexToRgb(c).reduce((a, v, i) => a + v * [0.2126, 0.7152, 0.0722][i], 0);
    for (const ramp of [FIRE_HOT, FIRE_BLUE]) {
      for (let i = 1; i < ramp.length; i++) expect(lum(ramp[i])).toBeLessThan(lum(ramp[i - 1]));
    }
    for (const c of [...FIRE_HOT, ...FIRE_BLUE]) expect(() => hexToRgb(c)).not.toThrow();
  });
});

describe('quality governor', () => {
  const run = (g: ReturnType<typeof createGovernor>, n: number, work: number, interval = 16.7) => {
    for (let i = 0; i < n; i++) g.sample(work, interval);
    return g.level;
  };

  it('starts at the best level', () => {
    const g = createGovernor();
    expect(g.level).toBe(0);
    expect(g.config).toBe(LEVELS[0]);
  });

  it('steps down under sustained 10 ms work, one level at a time, capped', () => {
    const g = createGovernor();
    expect(run(g, 19, 10)).toBe(0);
    let firstDrop = -1;
    for (let i = 0; i < 100 && firstDrop < 0; i++) if (g.sample(10, 16.7) === 1) firstDrop = i;
    expect(firstDrop).toBeGreaterThanOrEqual(0);
    expect(g.level).toBe(1);
    expect(run(g, 1000, 10, 33.3)).toBe(3);
    expect(g.config.fps).toBe(30);
    expect(createGovernor({ maxLevel: 1 }).sample(0, 1) >= 0).toBe(true);
    expect(run(createGovernor({ maxLevel: 1 }), 1000, 20)).toBe(1);
  });

  it('steps down on slow frame intervals even with cheap work', () => {
    const g = createGovernor();
    expect(run(g, 200, 1, 40)).toBeGreaterThanOrEqual(1);
  });

  it('steps back up after a calm stretch, not before', () => {
    const g = createGovernor({ start: 2 });
    expect(run(g, 179, 1, 33.3)).toBe(2);
    expect(run(g, 1, 1, 33.3)).toBe(1);
    expect(run(g, 179, 1)).toBe(1);
    expect(run(g, 1, 1)).toBe(0);
    expect(run(g, 1000, 1)).toBe(0);
  });

  it('does not flap under alternating good/bad samples', () => {
    const g = createGovernor({ start: 1 });
    let changes = 0;
    let last = g.level;
    for (let i = 0; i < 3000; i++) {
      const l = g.sample(i % 2 ? 12 : 1, 16.7);
      if (l !== last) changes++;
      last = l;
    }
    expect(changes).toBeLessThanOrEqual(1);
  });

  it('backs off upgrades that immediately fail again', () => {
    const g = createGovernor({ start: 1 });
    // calm → up, then heavy → down quickly: the next upgrade must take longer than upFrames
    run(g, 200, 1);
    expect(g.level).toBe(0);
    run(g, 40, 12);
    expect(g.level).toBe(1);
    expect(run(g, 200, 1)).toBe(1);
    expect(run(g, 200, 1)).toBe(0);
  });

  it('retries a failing upgrade ever more rarely (flap backoff, capped at 16x)', () => {
    // level 0 is too heavy for this "machine", level 1 is comfortable
    const g = createGovernor({ start: 1 });
    const ups: number[] = [];
    for (let i = 0; i < 20000; i++) {
      const before = g.level;
      if (g.sample(g.level === 0 ? 9 : 2, 16.7) < before) ups.push(i);
    }
    expect(ups[0]).toBe(179);
    const gaps = ups.slice(1).map((u, i) => u - ups[i]);
    for (let i = 1; i < gaps.length; i++) expect(gaps[i]).toBeGreaterThanOrEqual(gaps[i - 1]);
    expect(gaps[gaps.length - 1]).toBeGreaterThanOrEqual(180 * 16);
    expect(ups.length).toBeLessThanOrEqual(10);
  });

  it('forgives a strike once an upgrade has held for a while', () => {
    const g = createGovernor({ start: 1 });
    /** Samples until the level changes (work is the same for every frame). */
    const until = (work: number) => {
      const from = g.level;
      let n = 0;
      for (; g.level === from && n < 5000; n++) g.sample(work, 16.7);
      return n;
    };
    expect(until(1)).toBe(180);
    until(12); // quick re-downgrade → 1 strike
    expect(g.level).toBe(1);
    const second = until(1); // needs 2 × 180 calm frames (+ a few while the heavy EMA drains)
    expect(second).toBeGreaterThanOrEqual(360);
    expect(second).toBeLessThan(400);
    run(g, 180 * 4 + 1, 1); // held: strike forgiven
    until(12); // a late downgrade is not a strike
    expect(g.level).toBe(1);
    const third = until(1);
    expect(third).toBeGreaterThanOrEqual(180);
    expect(third).toBeLessThan(220);
  });

  it('sanitises non-finite options and work samples', () => {
    const g = createGovernor({ start: NaN, maxLevel: NaN, downFrames: NaN, upFrames: Infinity, downMs: NaN });
    expect(g.level).toBe(0);
    expect(g.config).toBe(LEVELS[0]);
    expect(run(g, 500, 20)).toBe(3);
    expect(g.config).toBe(LEVELS[3]);
    const h = createGovernor();
    for (let i = 0; i < 500; i++) h.sample(Infinity, 16.7);
    expect(h.level).toBe(0);
    // one huge GC spike is capped and cannot drag the EMA into a downgrade on its own
    h.sample(5000, 16.7);
    expect(run(h, 30, 1)).toBe(0);
  });

  it('ignores stalls and bogus intervals', () => {
    const g = createGovernor();
    for (let i = 0; i < 500; i++) {
      g.sample(80, 1000);
      g.sample(80, 0);
      g.sample(80, -5);
      g.sample(NaN, 16);
    }
    expect(g.level).toBe(0);
  });

  it('reset restores start level and counters', () => {
    const g = createGovernor({ start: 1 });
    run(g, 500, 20);
    expect(g.level).toBe(3);
    g.reset();
    expect(g.level).toBe(1);
    g.reset(9);
    expect(g.level).toBe(3);
    g.reset(0);
    expect(run(g, 19, 20)).toBe(0);
  });
});

describe('choreo', () => {
  it('fuseProgress is monotone 0 → 1 and clamped', () => {
    expect(fuseProgress(-100)).toBe(0);
    expect(fuseProgress(0)).toBe(0);
    expect(fuseProgress(IGNITE_MS / 2)).toBeCloseTo(0.5, 10);
    expect(fuseProgress(IGNITE_MS)).toBe(1);
    expect(fuseProgress(IGNITE_MS * 3)).toBe(1);
    let prev = 0;
    for (let ms = 0; ms <= IGNITE_MS; ms += 5) {
      const v = fuseProgress(ms);
      expect(v).toBeGreaterThanOrEqual(prev);
      prev = v;
    }
  });

  it('boostEnvelope peaks, decays monotonically to exactly 1, never below', () => {
    expect(boostEnvelope(-1)).toBe(1);
    expect(boostEnvelope(0)).toBe(2.2);
    expect(boostEnvelope(0, 3, 500)).toBe(3);
    let prev = Infinity;
    for (let ms = 0; ms <= 1500; ms += 7) {
      const v = boostEnvelope(ms);
      expect(v).toBeGreaterThanOrEqual(1);
      expect(v).toBeLessThanOrEqual(prev);
      prev = v;
    }
    expect(boostEnvelope(600)).toBeGreaterThan(1);
    expect(boostEnvelope(1199.9)).toBeLessThan(1.001);
    expect(boostEnvelope(1200)).toBe(1);
    expect(boostEnvelope(5000)).toBe(1);
  });

  it('boostEnvelope: holds briefly, decays continuously, tolerates junk args', () => {
    expect(boostEnvelope(60)).toBe(2.2);
    expect(boostEnvelope(61)).toBeGreaterThan(2.15);
    expect(boostEnvelope(NaN)).toBe(1);
    expect(boostEnvelope(100, NaN)).toBe(1);
    expect(boostEnvelope(100, 2.2, NaN)).toBe(1);
    expect(boostEnvelope(100, 0.5)).toBe(1);
    expect(boostEnvelope(0, 2.2, 0)).toBe(1);
    // no jumps bigger than a few % of the range per 7 ms step
    for (let ms = 61; ms < 1200; ms += 7) expect(boostEnvelope(ms) - boostEnvelope(ms + 7)).toBeLessThan(0.05);
  });

  it('gust breathes within [0.88, 1.12]', () => {
    const n = createNoise(11);
    let lo = Infinity;
    let hi = -Infinity;
    for (let t = 0; t < 120; t += 0.05) {
      const g = gust(t, n.n1);
      lo = Math.min(lo, g);
      hi = Math.max(hi, g);
    }
    expect(lo).toBeGreaterThanOrEqual(0.88);
    expect(hi).toBeLessThanOrEqual(1.12);
    expect(hi - lo).toBeGreaterThan(0.05);
    expect(gust(0, () => 5)).toBe(1.12);
    expect(gust(0, () => -5)).toBe(0.88);
    expect(gust(0, () => 0)).toBe(1);
    expect(gust(NaN, n.n1)).toBe(1);
  });

  it('shakeKeyframes start/end at rest and decay in amplitude', () => {
    const [amp, ms] = SHAKE.blast;
    const kf = shakeKeyframes(amp, ms, lehmer(5));
    const rest = 'translate(0px, 0px) rotate(0deg)';
    expect(kf.length).toBe(Math.round((ms / 1000) * 28) + 2);
    expect(kf[0]).toEqual({ transform: rest, offset: 0 });
    expect(kf[kf.length - 1]).toEqual({ transform: rest, offset: 1 });
    const parsed = kf.map((k) => {
      const m = /^translate\((-?[\d.]+)px, (-?[\d.]+)px\) rotate\((-?[\d.]+)deg\)$/.exec(String(k.transform));
      expect(m).not.toBeNull();
      return { x: +m![1], y: +m![2], z: +m![3], t: k.offset as number };
    });
    for (const p of parsed) {
      const env = amp * (1 - p.t) ** 2 + 0.01;
      expect(Math.abs(p.x)).toBeLessThanOrEqual(env);
      expect(Math.abs(p.y)).toBeLessThanOrEqual(env);
      expect(Math.abs(p.z)).toBeLessThanOrEqual(env * 0.04 + 0.01);
    }
    const half = Math.floor(parsed.length / 2);
    const peak = (ps: typeof parsed) => Math.max(...ps.map((p) => Math.abs(p.x)));
    expect(peak(parsed.slice(1, half))).toBeGreaterThan(peak(parsed.slice(half)) * 2);
    for (let i = 1; i < parsed.length; i++) expect(parsed[i].t).toBeGreaterThan(parsed[i - 1].t);
    // x alternates sign and carries at least half the envelope, so it reads as a shake rather than a drift
    for (let i = 1; i < parsed.length - 1; i++) {
      const env = amp * (1 - parsed[i].t) ** 2;
      expect(Math.sign(parsed[i].x) || -Math.sign(parsed[i - 1].x || 1)).toBe(i % 2 ? 1 : -1);
      expect(Math.abs(parsed[i].x)).toBeGreaterThanOrEqual(env * 0.5 - 0.01);
    }
    expect(JSON.stringify(kf)).not.toContain('-0px');
    expect(JSON.stringify(kf)).not.toContain('NaN');
  });

  it('shakeKeyframes is deterministic per rand and degenerate durations still rest', () => {
    expect(shakeKeyframes(9, 550, lehmer(3))).toEqual(shakeKeyframes(9, 550, lehmer(3)));
    expect(shakeKeyframes(9, 550, lehmer(3))).not.toEqual(shakeKeyframes(9, 550, lehmer(4)));
    const rest = 'translate(0px, 0px) rotate(0deg)';
    for (const d of [0, -50, NaN]) {
      expect(shakeKeyframes(9, d, lehmer(1))).toEqual([
        { transform: rest, offset: 0 },
        { transform: rest, offset: 1 },
      ]);
    }
    for (const [a, ms] of Object.values(SHAKE)) {
      expect(shakeKeyframes(a, ms, lehmer(2)).length).toBe(Math.round((ms / 1000) * 28) + 2);
    }
  });
});

describe('frame pacer', () => {
  /** Drive a pacer + governor with light work on a display of `hz`; returns the final level and refresh estimate. */
  const drive = (hz: number, fps: 60 | 30, seconds = 20) => {
    const p = createFramePacer();
    const g = createGovernor({ start: fps === 60 ? 0 : 2 });
    const vs = 1000 / hz;
    for (let k = 1; k <= seconds * hz; k++) {
      const iv = p.tick(k * vs, LEVELS[g.level].fps);
      if (iv < 0) continue;
      if (iv > 0) g.sample(0.5, iv);
    }
    return { level: g.level, vsync: p.vsync };
  };

  it('averages the target period on common refresh rates', () => {
    const mean = (hz: number, fps: number) => {
      const p = createFramePacer();
      let sum = 0;
      let n = 0;
      for (let k = 1; k <= 10 * hz; k++) {
        const iv = p.tick((k * 1000) / hz, fps);
        if (iv > 0) {
          sum += iv;
          n++;
        }
      }
      return sum / n;
    };
    for (const hz of [60, 75, 90, 120, 144, 165, 240]) {
      expect(mean(hz, 60)).toBeCloseTo(1000 / 60, 0);
      expect(mean(hz, 30)).toBeCloseTo(1000 / 30, 0);
    }
  });

  it('keeps an idle machine at the best level on 75/90/144 Hz', () => {
    for (const hz of [60, 75, 90, 144]) expect(drive(hz, 60).level).toBe(0);
  });

  it('lets fps-30 levels recover on 75 Hz', () => {
    expect(drive(75, 30, 60).level).toBe(0);
  });

  it('measures the refresh period', () => {
    expect(drive(144, 60).vsync).toBeCloseTo(1000 / 144, 1);
  });

  it('skips vsyncs only up to the period and resyncs after a stall', () => {
    const p = createFramePacer();
    expect(p.tick(1000, 60)).toBe(0);
    expect(p.tick(1016.7, 60)).toBeCloseTo(16.7, 5);
    // a long stall draws once, then keeps a steady cadence instead of bursting
    expect(p.tick(1500, 60)).toBeCloseTo(483.3, 5);
    expect(p.tick(1508, 60)).toBe(-1);
    expect(p.tick(1516.7, 60)).toBeCloseTo(16.7, 5);
    p.reset();
    expect(p.tick(5000, 30)).toBe(0);
  });
});
