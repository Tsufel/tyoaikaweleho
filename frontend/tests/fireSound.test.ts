import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  LOOKAHEAD,
  MASTER_GAIN,
  MAX_LOOKAHEAD,
  MAX_PENDING_CRACKLES,
  MAX_VOICES,
  createFireSound,
  planCrackles,
} from '../src/fx/fire/sound';

function seeded(seed = 1) {
  let s = seed;
  return () => ((s = (s * 16807) % 2147483647) - 1) / 2147483646;
}

// ---- Web Audio fakes ----

type Call = { m: string; v: number; t: number };

class FakeParam {
  value: number;
  calls: Call[] = [];
  constructor(
    private log: Call[],
    v = 0,
  ) {
    this.value = v;
  }
  private rec(m: string, v: number, t: number) {
    const c = { m, v, t };
    this.calls.push(c);
    this.log.push(c);
    return this;
  }
  setValueAtTime(v: number, t: number) {
    this.value = v;
    return this.rec('set', v, t);
  }
  linearRampToValueAtTime(v: number, t: number) {
    return this.rec('lin', v, t);
  }
  exponentialRampToValueAtTime(v: number, t: number) {
    return this.rec('exp', v, t);
  }
  setTargetAtTime(v: number, t: number, tc: number) {
    void tc;
    return this.rec('target', v, t);
  }
  cancelScheduledValues(t: number) {
    return this.rec('cancel', 0, t);
  }
}

class FakeNode {
  out: unknown[] = [];
  disconnected = false;
  constructor(
    public ctx: FakeCtx,
    public kind: string,
  ) {
    ctx.nodes.push(this);
  }
  param(v = 0) {
    return new FakeParam(this.ctx.log, v);
  }
  connect(dst: unknown) {
    this.out.push(dst);
    return dst;
  }
  disconnect() {
    this.disconnected = true;
  }
}

class FakeSource extends FakeNode {
  startAt: number | null = null;
  offset: number | undefined;
  stopAt: number | null = null;
  ended = false;
  onended: (() => void) | null = null;
  constructor(ctx: FakeCtx, kind: string) {
    super(ctx, kind);
    ctx.sources.push(this);
  }
  start(t = 0, offset?: number) {
    this.startAt = t;
    this.offset = offset;
  }
  stop(t = 0) {
    this.stopAt = t;
  }
}

class FakeOsc extends FakeSource {
  type = 'sine';
  frequency = this.param(440);
  detune = this.param(0);
  constructor(ctx: FakeCtx) {
    super(ctx, 'osc');
  }
}

class FakeBufferSource extends FakeSource {
  buffer: unknown = null;
  loop = false;
  constructor(ctx: FakeCtx) {
    super(ctx, 'buffer');
  }
}

class FakeCtx {
  log: Call[] = [];
  nodes: FakeNode[] = [];
  sources: FakeSource[] = [];
  buffers: { getChannelData: (i: number) => Float32Array }[] = [];
  currentTime = 0;
  sampleRate = 8000;
  state: AudioContextState = 'running';
  destination = new FakeNode(this, 'destination');
  suspend = vi.fn(() => {
    this.state = 'suspended';
    return Promise.resolve();
  });
  resume = vi.fn(() => {
    this.state = 'running';
    return Promise.resolve();
  });
  close = vi.fn(() => {
    this.state = 'closed';
    return Promise.resolve();
  });
  createGain() {
    const n = new FakeNode(this, 'gain');
    return Object.assign(n, { gain: n.param(1) });
  }
  createBiquadFilter() {
    const n = new FakeNode(this, 'biquad');
    return Object.assign(n, { type: 'lowpass', frequency: n.param(350), Q: n.param(1), gain: n.param(0) });
  }
  createWaveShaper() {
    return Object.assign(new FakeNode(this, 'shaper'), { curve: null as Float32Array | null, oversample: 'none' });
  }
  createDynamicsCompressor() {
    const n = new FakeNode(this, 'comp');
    return Object.assign(n, {
      threshold: n.param(-24),
      knee: n.param(30),
      ratio: n.param(12),
      attack: n.param(0.003),
      release: n.param(0.25),
    });
  }
  createOscillator() {
    return new FakeOsc(this);
  }
  createBufferSource() {
    return new FakeBufferSource(this);
  }
  createBuffer(channels: number, length: number, sampleRate: number) {
    const data = new Float32Array(length);
    const b = { numberOfChannels: channels, length, sampleRate, getChannelData: () => data };
    this.buffers.push(b);
    return b;
  }
  /** Advance the audio clock and fire onended for sources whose stop time has passed. */
  advance(dt: number) {
    this.currentTime += dt;
    for (const s of this.sources) {
      if (!s.ended && s.stopAt !== null && s.stopAt <= this.currentTime) {
        s.ended = true;
        s.onended?.();
      }
    }
  }
  oscs() {
    return this.sources.filter((s): s is FakeOsc => s instanceof FakeOsc);
  }
  of(kind: string) {
    return this.nodes.filter((n) => n.kind === kind);
  }
}

function setup(o: { enabled?: boolean; unlock?: boolean } = {}) {
  const ctxs: FakeCtx[] = [];
  const makeContext = vi.fn(() => {
    const c = new FakeCtx();
    ctxs.push(c);
    return c as unknown as AudioContext;
  });
  const fs = createFireSound({ makeContext, rand: seeded(7), now: () => Date.now() });
  if (o.enabled ?? true) fs.setEnabled(true);
  if (o.unlock ?? true) fs.unlock();
  return { fs, makeContext, ctx: () => ctxs[0] };
}

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe('planCrackles', () => {
  it('is sorted, within the window, with gains in (0, 1]', () => {
    const list = planCrackles(seeded(3), 1, 2, 3);
    expect(list.length).toBeGreaterThan(50);
    for (let i = 0; i < list.length; i++) {
      const k = list[i];
      expect(k.t).toBeGreaterThanOrEqual(2);
      expect(k.t).toBeLessThan(5);
      if (i) expect(k.t).toBeGreaterThanOrEqual(list[i - 1].t);
      expect(k.gain).toBeGreaterThan(0);
      expect(k.gain).toBeLessThanOrEqual(1);
      expect(k.q).toBeGreaterThanOrEqual(0.8);
      if (k.pop) {
        expect(k.freq).toBeGreaterThanOrEqual(600);
        expect(k.freq).toBeLessThanOrEqual(1200);
      } else {
        expect(k.freq).toBeGreaterThanOrEqual(1500);
        expect(k.freq).toBeLessThanOrEqual(5000);
        expect(k.dur).toBeGreaterThanOrEqual(0.003);
        expect(k.dur).toBeLessThanOrEqual(0.02);
        expect(k.q).toBeLessThanOrEqual(3);
      }
    }
    expect(list.some((k) => k.pop)).toBe(true);
  });

  it('has density near 6 + 40·intensity per second, clamped at 1.6', () => {
    const per = (i: number) => planCrackles(seeded(11), i, 0, 50).length / 50;
    expect(per(1)).toBeGreaterThan(40);
    expect(per(1)).toBeLessThan(52);
    expect(per(1.6)).toBeGreaterThan(per(0.2) * 3);
    expect(Math.abs(per(5) - per(1.6))).toBeLessThan(1e-9);
  });

  it('is empty at zero or negative intensity and for empty windows', () => {
    expect(planCrackles(seeded(), 0, 0, 1)).toEqual([]);
    expect(planCrackles(seeded(), -1, 0, 1)).toEqual([]);
    expect(planCrackles(seeded(), 1, 0, 0)).toEqual([]);
  });

  it('is empty for non-finite windows instead of looping forever', () => {
    expect(planCrackles(seeded(), 1, 0, Infinity)).toEqual([]);
    expect(planCrackles(seeded(), 1, NaN, 1)).toEqual([]);
    expect(planCrackles(seeded(), NaN, 0, 1)).toEqual([]);
  });

  it('terminates with a degenerate rand', () => {
    expect(planCrackles(() => 0, 1, 0, 1).length).toBeLessThanOrEqual(46 * 4 + 32);
    expect(planCrackles(() => 1, 1, 0, 1).length).toBeLessThan(5);
  });
});

describe('fire sound engine', () => {
  it('creates no context before unlock or while disabled', () => {
    const a = setup({ enabled: false, unlock: false });
    a.fs.whoosh();
    a.fs.boom();
    a.fs.unlock();
    a.fs.soundcheck();
    a.fs.setBed(1, true);
    expect(a.makeContext).not.toHaveBeenCalled();
    expect(a.fs.state).toBe('none');

    const b = setup({ enabled: true, unlock: false });
    b.fs.whoosh();
    b.fs.ignite();
    b.fs.milestone(4, true);
    expect(b.makeContext).not.toHaveBeenCalled();
    b.fs.unlock();
    expect(b.makeContext).toHaveBeenCalledTimes(1);
    b.fs.unlock();
    expect(b.makeContext).toHaveBeenCalledTimes(1);
  });

  it('creates the context for a one-shot once the page has user activation', () => {
    vi.stubGlobal('navigator', { userActivation: { hasBeenActive: true } });
    const a = setup({ unlock: false });
    a.fs.whoosh();
    expect(a.makeContext).toHaveBeenCalledTimes(1);
    expect(a.ctx().of('buffer').length).toBe(1);
  });

  it('closes a context whose graph setup throws and stays at none', () => {
    const made: FakeCtx[] = [];
    const fs = createFireSound({
      makeContext: () => {
        const c = new FakeCtx();
        c.createBuffer = () => {
          throw new Error('no buffers');
        };
        made.push(c);
        return c as unknown as AudioContext;
      },
    });
    fs.setEnabled(true);
    expect(() => fs.unlock()).not.toThrow();
    expect(made[0].close).toHaveBeenCalledTimes(1);
    expect(fs.state).toBe('none');
  });

  it('stays at none when context creation throws', () => {
    const fs = createFireSound({
      makeContext: () => {
        throw new Error('no audio');
      },
    });
    fs.setEnabled(true);
    expect(() => fs.unlock()).not.toThrow();
    expect(() => fs.boom()).not.toThrow();
    expect(fs.state).toBe('none');
  });

  it('wires master -> compressor -> destination with two noise buffers', () => {
    const { fs, ctx } = setup();
    const c = ctx();
    expect(fs.state).toBe('running');
    const comp = c.of('comp')[0] as FakeNode & { threshold: FakeParam; ratio: FakeParam };
    const master = c.of('gain').find((g) => g.out.includes(comp)) as FakeNode & { gain: FakeParam };
    expect(master).toBeDefined();
    expect(master.gain.value).toBeCloseTo(MASTER_GAIN);
    expect(comp.out).toEqual([c.destination]);
    expect(comp.threshold.value).toBe(-18);
    expect(comp.ratio.value).toBe(6);
    expect(c.buffers).toHaveLength(2);
    for (const b of c.buffers) expect(b.getChannelData(0).length).toBe(2 * c.sampleRate);
    expect(c.buffers[0].getChannelData(0).some((v) => v !== 0)).toBe(true);
    // The looping brown bed has no step at its seam.
    const brown = c.buffers[1].getChannelData(0);
    expect(Math.abs(brown[brown.length - 1] - brown[0])).toBeLessThan(0.05);
  });

  it('makes no nodes for one-shots once disabled', () => {
    const { fs, ctx } = setup();
    const c = ctx();
    fs.setEnabled(false);
    const before = c.nodes.length;
    fs.whoosh();
    fs.boom();
    fs.ignite();
    fs.fizzle();
    fs.milestone(4, true);
    fs.setBed(1, true);
    vi.advanceTimersByTime(1000);
    expect(c.nodes.length).toBe(before);
  });

  it('boom sweeps an oscillator down from 110 to 32 Hz', () => {
    const { fs, ctx } = setup();
    fs.boom();
    const osc = ctx().oscs()[0];
    expect(osc).toBeDefined();
    expect(osc.frequency.calls[0]).toMatchObject({ m: 'set', v: 110 });
    const exp = osc.frequency.calls.filter((c) => c.m === 'exp');
    expect(exp.at(-1)?.v).toBe(32);
    expect(osc.frequency.calls.at(-1)?.t).toBeGreaterThan(osc.frequency.calls[0].t);
    expect(ctx().of('shaper')).toHaveLength(1);
  });

  it('schedules stop() for every source and never ramps exponentially to <= 0', () => {
    const { fs, ctx } = setup();
    const c = ctx();
    fs.setBed(1.2, true);
    for (let i = 0; i < 20; i++) {
      vi.advanceTimersByTime(100);
      c.advance(0.1);
    }
    fs.setBed(0.4, true);
    vi.advanceTimersByTime(300);
    c.advance(0.3);
    fs.ignite();
    fs.fizzle();
    fs.milestone(1, false);
    fs.milestone(2, false);
    fs.milestone(3, true);
    c.advance(5);
    fs.milestone(4, true);
    fs.whoosh(0);
    fs.boom(3);
    fs.setBed(0, false);
    fs.setEnabled(false);
    fs.setEnabled(true);
    fs.soundcheck();

    expect(c.sources.length).toBeGreaterThan(50);
    for (const s of c.sources) {
      expect(s.startAt).not.toBeNull();
      expect(s.stopAt).not.toBeNull();
      expect(s.stopAt!).toBeGreaterThan(s.startAt!);
    }
    const exps = c.log.filter((k) => k.m === 'exp');
    expect(exps.length).toBeGreaterThan(50);
    for (const k of exps) expect(k.v).toBeGreaterThan(0);
    // Every ramp is preceded by a set on the same param.
    for (const n of c.nodes) {
      for (const p of Object.values(n).filter((x): x is FakeParam => x instanceof FakeParam)) {
        const first = p.calls.findIndex((k) => k.m === 'lin' || k.m === 'exp' || k.m === 'target');
        if (first >= 0) expect(p.calls.slice(0, first).some((k) => k.m === 'set')).toBe(true);
      }
    }
  });

  it('ignite gates a highpassed noise with a 23 Hz square LFO, then whooshes', () => {
    const { fs, ctx } = setup();
    fs.ignite();
    const c = ctx();
    const lfo = c.oscs().find((o) => o.type === 'square');
    expect(lfo?.frequency.value).toBe(23);
    const hp = c.of('biquad').find((b) => (b as FakeNode & { type: string }).type === 'highpass');
    expect(hp).toBeDefined();
    const noises = c.sources.filter((s) => s.kind === 'buffer');
    expect(noises).toHaveLength(2);
    expect(noises[1].startAt! - noises[0].startAt!).toBeCloseTo(0.75);
  });

  it('maps milestone tiers to whoosh / boom / shimmer voices', () => {
    const run = (tier: 1 | 2 | 3 | 4, blue: boolean) => {
      const { fs, ctx } = setup();
      fs.milestone(tier, blue);
      const c = ctx();
      return { oscs: c.oscs().length, noises: c.sources.filter((s) => s.kind === 'buffer').length, log: c.log };
    };
    const t1 = run(1, false);
    expect(t1.oscs).toBe(0);
    expect(t1.noises).toBe(1);
    expect(t1.log.find((k) => k.m === 'lin')?.v).toBeCloseTo(0.25);
    expect(run(3, false).oscs).toBe(1);
    expect(run(4, false).oscs).toBe(1 + 3);
    expect(run(4, true).oscs).toBe(1 + 6);
  });

  it('keeps every param finite for NaN / Infinity powers', () => {
    const { fs, ctx } = setup();
    fs.whoosh(NaN);
    fs.boom(Infinity);
    fs.boom(-Infinity);
    fs.setBed(NaN, true);
    fs.setBed(Infinity, true);
    vi.advanceTimersByTime(300);
    const c = ctx();
    expect(c.log.length).toBeGreaterThan(0);
    for (const k of c.log) {
      expect(Number.isFinite(k.v)).toBe(true);
      expect(Number.isFinite(k.t)).toBe(true);
    }
  });

  it('releases the voice slot when a one-shot throws before starting a source', () => {
    const { fs, ctx } = setup();
    const c = ctx();
    const err = vi.spyOn(console, 'error').mockImplementation(() => {});
    const real = c.createOscillator.bind(c);
    c.createOscillator = () => {
      throw new Error('boom');
    };
    for (let i = 0; i < MAX_VOICES + 2; i++) fs.boom();
    expect(err).toHaveBeenCalled();
    c.createOscillator = real;
    fs.boom();
    expect(c.oscs()).toHaveLength(1);
  });

  it('resumes on enable even while a suspend() is still in flight', () => {
    const { fs, ctx } = setup();
    const c = ctx();
    c.suspend = vi.fn(() => new Promise<void>(() => {}));
    fs.setEnabled(false);
    vi.advanceTimersByTime(250);
    expect(c.suspend).toHaveBeenCalledTimes(1);
    expect(c.state).toBe('running');
    c.resume.mockClear();
    fs.setEnabled(true);
    expect(c.resume).toHaveBeenCalledTimes(1);
  });

  it('suspends the context after disabling and resumes on enable', async () => {
    const { fs, ctx } = setup();
    const c = ctx();
    fs.setEnabled(false);
    expect(c.suspend).not.toHaveBeenCalled();
    vi.advanceTimersByTime(250);
    expect(c.suspend).toHaveBeenCalledTimes(1);
    await Promise.resolve();
    expect(fs.state).toBe('suspended');
    fs.setEnabled(true);
    expect(c.resume).toHaveBeenCalled();
  });

  it('does not suspend when re-enabled within the fade', () => {
    const { fs, ctx } = setup();
    fs.setEnabled(false);
    vi.advanceTimersByTime(50);
    fs.setEnabled(true);
    vi.advanceTimersByTime(500);
    expect(ctx().suspend).not.toHaveBeenCalled();
  });

  it(`caps concurrent one-shots at ${MAX_VOICES} voices`, () => {
    const { fs, ctx } = setup();
    const c = ctx();
    for (let i = 0; i < 10; i++) fs.boom();
    const booms = () => c.oscs().filter((o) => o.frequency.calls[0]?.v === 110).length;
    expect(booms()).toBe(MAX_VOICES);
    fs.whoosh();
    expect(booms()).toBe(MAX_VOICES);
    c.advance(5);
    // Ended voices free their slots and disconnect their nodes.
    expect(c.sources.every((s) => s.disconnected)).toBe(true);
    fs.boom();
    expect(booms()).toBe(MAX_VOICES + 1);
  });

  it('schedules bed crackles over time, denser at higher intensity', () => {
    const count = (intensity: number) => {
      const { fs, ctx } = setup();
      const c = ctx();
      fs.setBed(intensity, true);
      const bed = c.sources.filter((s) => (s as FakeBufferSource).loop && s.stopAt === null);
      expect(bed).toHaveLength(1);
      for (let i = 0; i < 30; i++) {
        vi.advanceTimersByTime(100);
        c.advance(0.1);
      }
      const crackles = c.sources.filter((s) => s !== bed[0]);
      // No gaps and no duplicates: start times are strictly inside the scheduled span.
      for (const s of crackles) expect(s.startAt!).toBeLessThan(c.currentTime + 0.15 + 1e-9);
      const starts = crackles.map((s) => s.startAt);
      expect(new Set(starts).size).toBe(starts.length);
      fs.setBed(intensity, false);
      expect(bed[0].stopAt).not.toBeNull();
      const n = c.sources.length;
      vi.advanceTimersByTime(1000);
      c.advance(1);
      expect(c.sources.length).toBe(n);
      fs.dispose();
      return crackles.length;
    };
    const low = count(0.2);
    const high = count(1.6);
    expect(low).toBeGreaterThan(5);
    expect(high).toBeGreaterThan(low * 3);
  });

  it('does not reschedule the bed level for per-frame setBed calls with the same intensity', () => {
    const { fs, ctx } = setup();
    const c = ctx();
    fs.setBed(1, true);
    const targets = () => c.log.filter((k) => k.m === 'target').length;
    const before = targets();
    for (let i = 0; i < 60; i++) fs.setBed(1 + i * 1e-5, true);
    expect(targets()).toBe(before);
    fs.setBed(0.5, true);
    expect(targets()).toBe(before + 1);
  });

  it(`keeps at most ${MAX_PENDING_CRACKLES} bed crackles in flight`, () => {
    const { fs, ctx } = setup();
    const c = ctx();
    fs.setBed(1.6, true);
    const bed = c.sources[0];
    for (let i = 0; i < 20; i++) {
      vi.advanceTimersByTime(100);
      c.currentTime += 0.1; // the clock moves but no onended fires
      const live = c.sources.filter((s) => s !== bed && !s.ended).length;
      expect(live).toBeLessThanOrEqual(MAX_PENDING_CRACKLES);
    }
    c.advance(1);
    vi.advanceTimersByTime(100);
    expect(c.sources.filter((s) => s !== bed && !s.ended).length).toBeGreaterThan(0);
  });

  it('stretches the lookahead after a late tick, up to its cap', () => {
    const { fs, ctx } = setup();
    const c = ctx();
    fs.setBed(1.6, true);
    vi.advanceTimersByTime(100);
    const latest = () => Math.max(...c.sources.slice(1).map((s) => s.startAt!));
    expect(latest()).toBeLessThan(c.currentTime + LOOKAHEAD + 1e-9);
    // Throttled timer: wall time jumps 2 s between ticks while the audio clock runs on.
    vi.setSystemTime(Date.now() + 2000);
    c.currentTime += 2;
    vi.advanceTimersByTime(100);
    expect(latest()).toBeGreaterThan(c.currentTime + LOOKAHEAD);
    expect(latest()).toBeLessThan(c.currentTime + MAX_LOOKAHEAD + 1e-9);
    // Skipped backlog: nothing was scheduled in the past.
    expect(c.sources.slice(1).filter((s) => s.startAt! < 1 && s.startAt! > 0.25)).toHaveLength(0);
  });

  it('starts the bed once a context exists if it was requested earlier', () => {
    const { fs, ctx } = setup({ unlock: false });
    fs.setBed(1, true);
    fs.unlock();
    expect(ctx().sources.some((s) => (s as FakeBufferSource).loop)).toBe(true);
  });

  it('dispose closes the context and turns everything into no-ops', () => {
    const { fs, ctx } = setup();
    const c = ctx();
    fs.setBed(1, true);
    fs.dispose();
    expect(c.close).toHaveBeenCalledTimes(1);
    expect(fs.state).toBe('closed');
    const n = c.nodes.length;
    fs.setEnabled(true);
    fs.boom();
    fs.unlock();
    vi.advanceTimersByTime(1000);
    expect(c.nodes.length).toBe(n);
    expect(vi.getTimerCount()).toBe(0);
  });

  it('dispose without a context stays at none and leaves no timers', () => {
    const { fs, makeContext } = setup({ unlock: false });
    fs.setBed(1, true);
    fs.dispose();
    fs.unlock();
    expect(makeContext).not.toHaveBeenCalled();
    expect(fs.state).toBe('none');
    expect(vi.getTimerCount()).toBe(0);
  });
});
