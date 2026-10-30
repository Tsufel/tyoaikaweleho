// Fully synthesized Web Audio fire sounds for the Lulz effects (no audio files).
// The AudioContext is created lazily from a user gesture and only while enabled.
import type { Tier } from './fxBus';

export interface FireSound {
  /** Gates everything; off fades the master out and suspends the context. */
  setEnabled(on: boolean): void;
  /** Call from a user gesture: lazily creates (only if enabled) and resumes the context. */
  unlock(): void;
  /** Continuous crackle + low rumble bed while the ring fire burns (intensity 0…1.6). */
  setBed(intensity: number, on: boolean): void;
  ignite(): void;
  whoosh(power?: number): void;
  boom(power?: number): void;
  fizzle(): void;
  milestone(tier: Tier, blue: boolean): void;
  /** unlock() + a short whoosh, for the settings toggle. */
  soundcheck(): void;
  /** Stops the scheduler and closes the context; the engine is dead afterwards. */
  dispose(): void;
  /** 'none' before a context exists. */
  readonly state: 'none' | AudioContextState;
}

export interface Crackle {
  /** Start, context seconds. */
  t: number;
  /** Decay, seconds. */
  dur: number;
  gain: number;
  /** Bandpass centre, Hz. */
  freq: number;
  q: number;
  pop: boolean;
}

/** Master gain while enabled. */
export const MASTER_GAIN = 0.32;
/** Concurrent one-shot voices; extra one-shots are dropped. */
export const MAX_VOICES = 6;
/** Bed crackle sources allowed in flight before new ones are skipped. */
export const MAX_PENDING_CRACKLES = 40;
/** Scheduler tick and lookahead. */
export const TICK_MS = 100;
export const LOOKAHEAD = 0.15;
/** Upper bound for the lookahead after a late tick, seconds. */
export const MAX_LOOKAHEAD = 0.5;

const FLOOR = 0.0001;
const NOISE_SECONDS = 2;

/**
 * Poisson crackle events in [from, from + win): 6 + 40·intensity per second (intensity clamped 0…1.6),
 * one in 12 a lower, longer, louder 'pop'. Sorted by t.
 */
export function planCrackles(rand: () => number, intensity: number, from: number, win: number): Crackle[] {
  const out: Crackle[] = [];
  const i = Math.min(1.6, intensity);
  if (!(i > 0) || !(win > 0) || !Number.isFinite(from) || !Number.isFinite(win)) return out;
  const rate = 6 + 40 * i;
  const end = from + win;
  const cap = Math.ceil(rate * win * 4) + 32;
  let t = from;
  while (out.length < cap) {
    t += Math.max(1e-4, -Math.log(1 - Math.min(rand(), 0.999999)) / rate);
    if (t >= end) break;
    const pop = rand() < 1 / 12;
    out.push(
      pop
        ? {
            t,
            dur: 0.02 + 0.025 * rand(),
            gain: 0.3 + 0.3 * rand(),
            freq: 600 + 600 * rand(),
            q: 0.8 + 1.2 * rand(),
            pop,
          }
        : {
            t,
            dur: 0.003 + 0.017 * rand(),
            gain: 0.05 + 0.3 * rand(),
            freq: 1500 + 3500 * rand(),
            q: 0.8 + 2.2 * rand(),
            pop,
          },
    );
  }
  return out;
}

interface Voice {
  nodes: AudioNode[];
  live: number;
}

type ActivationNav = Navigator & { userActivation?: { hasBeenActive: boolean } };

function hasUserActivation(): boolean {
  if (typeof navigator === 'undefined') return false;
  return !!(navigator as ActivationNav).userActivation?.hasBeenActive;
}

function tanhCurve(n = 1024, k = 2.5): Float32Array<ArrayBuffer> {
  const c = new Float32Array(n);
  const norm = Math.tanh(k);
  for (let i = 0; i < n; i++) c[i] = Math.tanh(k * ((i / (n - 1)) * 2 - 1)) / norm;
  return c;
}

/** Re-anchor a param at its current value so the next ramp starts from where it is. */
function anchor(p: AudioParam, t: number): void {
  p.cancelScheduledValues(t);
  p.setValueAtTime(Math.max(FLOOR, p.value), t);
}

export function createFireSound(
  o: { makeContext?: () => AudioContext; rand?: () => number; now?: () => number } = {},
): FireSound {
  const makeContext = o.makeContext ?? (() => new AudioContext({ latencyHint: 'interactive' }));
  const rand = o.rand ?? Math.random;
  const now = o.now ?? (() => performance.now());

  let enabled = false;
  let disposed = false;
  let closed = false;
  let ctx: AudioContext | null = null;
  let master: GainNode | null = null;
  let white: AudioBuffer | null = null;
  let brown: AudioBuffer | null = null;
  let curve: Float32Array<ArrayBuffer> | null = null;
  let voices = 0;
  let suspendTimer: ReturnType<typeof setTimeout> | null = null;

  // Bed: desired state survives disable / no context so it resumes when sound comes back.
  let bedWanted = false;
  let bedLevel = 0;
  let bedSrc: AudioBufferSourceNode | null = null;
  let bedGain: GainNode | null = null;
  let timer: ReturnType<typeof setInterval> | null = null;
  let scheduledUntil = 0;
  let lastTick = 0;
  let pendingCrackles = 0;
  /** Last bed level target sent to the param; setBed may be called every frame. */
  let bedSet = -1;

  const bedTarget = () => 0.04 + 0.06 * bedLevel;

  function build(c: AudioContext): void {
    const comp = c.createDynamicsCompressor();
    comp.threshold.value = -18;
    comp.knee.value = 12;
    comp.ratio.value = 6;
    comp.attack.value = 0.003;
    comp.release.value = 0.25;
    master = c.createGain();
    master.gain.value = MASTER_GAIN;
    master.connect(comp);
    comp.connect(c.destination);
    const len = Math.max(1, Math.floor(c.sampleRate * NOISE_SECONDS));
    white = c.createBuffer(1, len, c.sampleRate);
    brown = c.createBuffer(1, len, c.sampleRate);
    const w = white.getChannelData(0);
    const b = brown.getChannelData(0);
    let last = 0;
    for (let i = 0; i < len; i++) {
      const r = rand() * 2 - 1;
      w[i] = r;
      last = (last + 0.02 * r) / 1.02;
      b[i] = last * 3.5;
    }
    // Detrend so the looping bed has no step (a low thump every 2 s) at the seam.
    const drift = (b[len - 1] - b[0]) / Math.max(1, len - 1);
    for (let i = 0; i < len; i++) b[i] -= drift * i;
    curve = tanhCurve();
  }

  // Unconditional (bar 'closed'): a suspend() still in flight reports 'running', and resume() queues behind it.
  function resume(c: AudioContext): void {
    if (c.state === 'closed') return;
    try {
      void c.resume().catch(() => {});
    } catch {
      /* ignore */
    }
  }

  /** The live context, creating it only while enabled and from (or after) a user gesture. */
  function ensure(gesture: boolean): AudioContext | null {
    if (!enabled || disposed) return null;
    if (ctx) return ctx;
    if (!gesture && !hasUserActivation()) return null;
    let c: AudioContext | null = null;
    try {
      c = makeContext();
      build(c);
      ctx = c;
    } catch {
      if (c) {
        try {
          void c.close().catch(() => {});
        } catch {
          /* ignore */
        }
      }
      ctx = null;
      master = null;
      return null;
    }
    if (bedWanted) startBed();
    return ctx;
  }

  // ---- bed ----

  function startBed(): void {
    const c = ctx;
    if (!c || !master || !brown || !enabled || !bedWanted) return;
    const t = c.currentTime;
    if (bedSrc && bedGain) {
      if (Math.abs(bedTarget() - bedSet) >= 0.002) {
        bedSet = bedTarget();
        anchor(bedGain.gain, t);
        bedGain.gain.setTargetAtTime(bedSet, t, 0.25);
      }
    } else {
      const src = c.createBufferSource();
      src.buffer = brown;
      src.loop = true;
      const lp = c.createBiquadFilter();
      lp.type = 'lowpass';
      lp.frequency.value = 220;
      const g = c.createGain();
      g.gain.value = FLOOR;
      g.gain.setValueAtTime(FLOOR, t);
      bedSet = bedTarget();
      g.gain.setTargetAtTime(bedSet, t, 0.4);
      src.connect(lp);
      lp.connect(g);
      g.connect(master);
      src.onended = () => {
        src.disconnect();
        lp.disconnect();
        g.disconnect();
      };
      src.start(t, rand() * (NOISE_SECONDS - 0.1));
      bedSrc = src;
      bedGain = g;
    }
    if (timer === null) {
      scheduledUntil = t;
      lastTick = now();
      timer = setInterval(tick, TICK_MS);
      tick();
    }
  }

  function stopBed(): void {
    if (timer !== null) {
      clearInterval(timer);
      timer = null;
    }
    bedSet = -1;
    const c = ctx;
    if (!c || !bedSrc || !bedGain) {
      bedSrc = null;
      bedGain = null;
      return;
    }
    const t = c.currentTime;
    anchor(bedGain.gain, t);
    bedGain.gain.exponentialRampToValueAtTime(FLOOR, t + 0.3);
    bedSrc.stop(t + 0.35);
    bedSrc = null;
    bedGain = null;
  }

  function tick(): void {
    const c = ctx;
    if (!c || !master || !enabled || !bedWanted) return;
    const t = c.currentTime;
    const n = now();
    // Late ticks (jitter, throttled timers) stretch the lookahead so the bed has no gaps; a backlog the audio clock
    // already passed is dropped rather than bunched up.
    const gap = (n - lastTick) / 1000;
    const ahead = Number.isFinite(gap) ? Math.min(MAX_LOOKAHEAD, Math.max(LOOKAHEAD, gap + 0.05)) : LOOKAHEAD;
    lastTick = n;
    const from = Math.max(scheduledUntil, t);
    const horizon = t + ahead;
    if (!(horizon > from)) return;
    for (const k of planCrackles(rand, bedLevel, from, horizon - from)) {
      if (pendingCrackles >= MAX_PENDING_CRACKLES) continue;
      pendingCrackles++;
      crackle(c, k, 1, null, () => pendingCrackles--);
    }
    scheduledUntil = horizon;
  }

  // ---- voices ----

  function newVoice(): Voice | null {
    if (voices >= MAX_VOICES) return null;
    voices++;
    return { nodes: [], live: 0 };
  }

  function add<T extends AudioNode>(v: Voice | null, n: T): T {
    v?.nodes.push(n);
    return n;
  }

  /** Start/stop a source; the voice ends (nodes disconnected) when its last source ends. */
  function play(v: Voice, src: AudioScheduledSourceNode, t0: number, t1: number, offset?: number): void {
    v.live++;
    src.onended = () => {
      if (--v.live > 0) return;
      for (const n of v.nodes) n.disconnect();
      v.nodes.length = 0;
      voices = Math.max(0, voices - 1);
    };
    if (offset !== undefined) (src as AudioBufferSourceNode).start(t0, offset);
    else src.start(t0);
    src.stop(t1);
  }

  function noise(c: AudioContext, v: Voice): AudioBufferSourceNode {
    const src = add(v, c.createBufferSource());
    src.buffer = white;
    src.loop = true;
    return src;
  }

  const offset = () => rand() * (NOISE_SECONDS - 0.1);

  /** Exponential env: FLOOR -> peak over `atk` (linear) -> FLOOR at `end`. */
  function env(p: AudioParam, t0: number, peak: number, atk: number, end: number): void {
    p.value = FLOOR;
    p.setValueAtTime(FLOOR, t0);
    p.linearRampToValueAtTime(Math.max(FLOOR * 2, peak), t0 + atk);
    p.exponentialRampToValueAtTime(FLOOR, end);
  }

  function crackle(c: AudioContext, k: Crackle, scale: number, v: Voice | null, done?: () => void): void {
    if (!master || !white) return;
    const src = c.createBufferSource();
    src.buffer = white;
    src.loop = true;
    const bp = c.createBiquadFilter();
    bp.type = 'bandpass';
    bp.frequency.value = k.freq;
    bp.Q.value = k.q;
    const g = c.createGain();
    env(g.gain, k.t, k.gain * scale, 0.002, k.t + 0.002 + k.dur);
    src.connect(bp);
    bp.connect(g);
    g.connect(master);
    if (v) {
      v.nodes.push(src, bp, g);
      play(v, src, k.t, k.t + k.dur + 0.02, offset());
      return;
    }
    src.onended = () => {
      src.disconnect();
      bp.disconnect();
      g.disconnect();
      done?.();
    };
    src.start(k.t, offset());
    src.stop(k.t + k.dur + 0.02);
  }

  function whooshAt(c: AudioContext, v: Voice, t0: number, power: number): void {
    const src = noise(c, v);
    const bp = add(v, c.createBiquadFilter());
    bp.type = 'bandpass';
    bp.Q.value = 1.2;
    bp.frequency.value = 250;
    bp.frequency.setValueAtTime(250, t0);
    bp.frequency.exponentialRampToValueAtTime(2800, t0 + 0.5);
    bp.frequency.exponentialRampToValueAtTime(600, t0 + 0.9);
    const g = add(v, c.createGain());
    env(g.gain, t0, 0.5 * power, 0.08, t0 + 1.0);
    src.connect(bp);
    bp.connect(g);
    g.connect(master!);
    play(v, src, t0, t0 + 1.05, offset());
  }

  function boomAt(c: AudioContext, v: Voice, t0: number, power: number): void {
    const osc = add(v, c.createOscillator());
    osc.type = 'sine';
    osc.frequency.value = 110;
    osc.frequency.setValueAtTime(110, t0);
    osc.frequency.exponentialRampToValueAtTime(32, t0 + 0.7);
    const og = add(v, c.createGain());
    env(og.gain, t0, 0.9 * power, 0.01, t0 + 1.2);
    osc.connect(og);
    og.connect(master!);
    play(v, osc, t0, t0 + 1.25);

    const src = noise(c, v);
    const lp = add(v, c.createBiquadFilter());
    lp.type = 'lowpass';
    lp.frequency.value = 1200;
    lp.frequency.setValueAtTime(1200, t0);
    lp.frequency.exponentialRampToValueAtTime(120, t0 + 0.8);
    const ws = add(v, c.createWaveShaper());
    ws.curve = curve;
    ws.oversample = '2x';
    const ng = add(v, c.createGain());
    env(ng.gain, t0, 0.6 * power, 0.005, t0 + 1.0);
    src.connect(lp);
    lp.connect(ws);
    ws.connect(ng);
    ng.connect(master!);
    play(v, src, t0, t0 + 1.05, offset());

    // Debris shower, thinning out as it falls.
    const from = t0 + 0.05;
    for (const k of planCrackles(rand, 1.6, from, 1.5)) crackle(c, k, power * (1 - (0.7 * (k.t - from)) / 1.5), v);
  }

  function igniteAt(c: AudioContext, v: Voice, t0: number): void {
    const src = noise(c, v);
    const hp = add(v, c.createBiquadFilter());
    hp.type = 'highpass';
    hp.frequency.value = 3500;
    // Fuse sizzle: a 23 Hz square LFO swings the gate gain between ~0 and 1.
    const gate = add(v, c.createGain());
    gate.gain.value = 0.5;
    gate.gain.setValueAtTime(0.5, t0);
    const lfo = add(v, c.createOscillator());
    lfo.type = 'square';
    lfo.frequency.value = 23;
    const depth = add(v, c.createGain());
    depth.gain.value = 0.5;
    lfo.connect(depth);
    depth.connect(gate.gain);
    const g = add(v, c.createGain());
    env(g.gain, t0, 0.22, 0.05, t0 + 0.8);
    src.connect(hp);
    hp.connect(gate);
    gate.connect(g);
    g.connect(master!);
    play(v, src, t0, t0 + 0.82, offset());
    play(v, lfo, t0, t0 + 0.82);
    whooshAt(c, v, t0 + 0.75, 0.8);
  }

  function fizzleAt(c: AudioContext, v: Voice, t0: number): void {
    const src = noise(c, v);
    const bp = add(v, c.createBiquadFilter());
    bp.type = 'bandpass';
    bp.Q.value = 2;
    bp.frequency.value = 3000;
    bp.frequency.setValueAtTime(3000, t0);
    bp.frequency.exponentialRampToValueAtTime(700, t0 + 0.9);
    const g = add(v, c.createGain());
    env(g.gain, t0, 0.25, 0.03, t0 + 0.95);
    src.connect(bp);
    bp.connect(g);
    g.connect(master!);
    play(v, src, t0, t0 + 1.0, offset());
  }

  function shimmerAt(c: AudioContext, v: Voice, t0: number, blue: boolean): void {
    const freqs = [1320, 1980, 2640];
    const parts = freqs.map((f, i) => ({ f, g: 0.07 / (i + 1), d: 0 }));
    if (blue) freqs.forEach((f, i) => parts.push({ f: f * 2, g: 0.035 / (i + 1), d: 0.06 * (i + 1) }));
    for (const p of parts) {
      const t = t0 + p.d;
      const osc = add(v, c.createOscillator());
      osc.type = 'sine';
      osc.frequency.value = p.f;
      osc.detune.value = (rand() - 0.5) * 12;
      const g = add(v, c.createGain());
      env(g.gain, t, p.g, 0.12, t + 1.32);
      osc.connect(g);
      g.connect(master!);
      play(v, osc, t, t + 1.36);
    }
  }

  /** Run a one-shot in a fresh voice; silently dropped when disabled, locked, or the voice cap is hit. */
  function oneShot(fn: (c: AudioContext, v: Voice, t0: number) => void): void {
    let v: Voice | null = null;
    try {
      const c = ensure(false);
      if (!c || !master || !white) return;
      resume(c);
      v = newVoice();
      if (v) fn(c, v, c.currentTime + 0.01);
    } catch (err) {
      console.error('fire sound failed', err);
    }
    // Nothing started (or it threw first): release the slot here, no onended will.
    if (!v || v.live > 0) return;
    for (const n of v.nodes) n.disconnect();
    voices--;
  }

  const pw = (p: number | undefined) => (p !== undefined && Number.isFinite(p) ? Math.min(2, Math.max(0.01, p)) : 1);

  function unlock(): void {
    const c = ensure(true);
    if (c) resume(c);
  }

  function whoosh(power?: number): void {
    oneShot((c, v, t0) => whooshAt(c, v, t0, pw(power)));
  }

  return {
    setEnabled(on) {
      if (disposed || on === enabled) return;
      enabled = on;
      const c = ctx;
      if (!c || !master) return;
      const t = c.currentTime;
      if (suspendTimer !== null) {
        clearTimeout(suspendTimer);
        suspendTimer = null;
      }
      if (on) {
        resume(c);
        anchor(master.gain, t);
        master.gain.exponentialRampToValueAtTime(MASTER_GAIN, t + 0.08);
        if (bedWanted) startBed();
      } else {
        stopBed();
        anchor(master.gain, t);
        master.gain.exponentialRampToValueAtTime(FLOOR, t + 0.12);
        suspendTimer = setTimeout(() => {
          suspendTimer = null;
          if (enabled || ctx !== c || c.state !== 'running') return;
          try {
            void c.suspend().catch(() => {});
          } catch {
            /* ignore */
          }
        }, 200);
      }
    },
    unlock,
    setBed(intensity, on) {
      if (disposed) return;
      bedLevel = Math.min(1.6, Math.max(0, Number.isFinite(intensity) ? intensity : 0));
      bedWanted = on && bedLevel > 0;
      if (!ctx || !enabled) return;
      if (bedWanted) startBed();
      else stopBed();
    },
    ignite() {
      oneShot(igniteAt);
    },
    whoosh,
    boom(power) {
      oneShot((c, v, t0) => boomAt(c, v, t0, pw(power)));
    },
    fizzle() {
      oneShot(fizzleAt);
    },
    milestone(tier, blue) {
      oneShot((c, v, t0) => {
        if (tier === 1) whooshAt(c, v, t0, 0.5);
        else if (tier === 2) whooshAt(c, v, t0, 0.8);
        else if (tier === 3) {
          boomAt(c, v, t0, 0.7);
          whooshAt(c, v, t0, 1);
        } else {
          boomAt(c, v, t0, 0.9);
          shimmerAt(c, v, t0 + 0.05, blue);
        }
      });
    },
    soundcheck() {
      unlock();
      whoosh(0.6);
    },
    dispose() {
      if (disposed) return;
      stopBed();
      if (suspendTimer !== null) clearTimeout(suspendTimer);
      suspendTimer = null;
      disposed = true;
      const c = ctx;
      ctx = null;
      master = null;
      voices = 0;
      if (!c) return;
      closed = true;
      try {
        void c.close().catch(() => {});
      } catch {
        /* ignore */
      }
    },
    get state() {
      if (ctx) return ctx.state;
      return closed ? 'closed' : 'none';
    },
  };
}
