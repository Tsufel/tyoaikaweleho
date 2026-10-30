<script module lang="ts">
  export interface OverlayStats {
    alive: number;
    active: boolean;
    /** rAF loop running. */
    running: boolean;
    /** Governor level, 0 best … LEVELS.length - 1 cheapest. */
    level: number;
    /** Frames drawn and their summed work time (ms) since mount. */
    frames: number;
    workMs: number;
  }
</script>

<script lang="ts">
  import { onMount } from 'svelte';
  import { animationsActive } from '../../lib/stores/app';
  import { FIRE_BLUE, FIRE_HOT, cssVar } from '../../lib/theme/tokens';
  import { portal } from '../../lib/ui/actions';
  import type { Tier } from './fxBus';
  import { O_CONFETTI, O_EMBER, O_PUFF, O_SMOKE, O_SPARK, createOverlaySim } from './overlaySim';
  import { hexToRgb, mixRgb, type Rgb } from './palette';
  import { LEVELS, createFramePacer, createGovernor } from './quality';

  /** Lulz: whole-window blast / milestone / fizzle effects on one fixed canvas,
   *  portalled to <body> above modals and toasts (z 240) but below the wizard.
   *  Hidden with no rAF while the sim is idle; the backing store shrinks to 1×1. */

  /** Overlay backing store never exceeds this DPR (the governor may lower it further). */
  const MAX_DPR = 1.25;
  /** Heat steps per palette for puff sprites and spark colours. */
  const HEAT_STEPS = 6;
  const PUFF_STEPS = 8;
  /** Puffs cool only this far along the palette: 'lighter' stacks on a transparent
   *  canvas, so the dark red/black tail turns into an opaque maroon blob on light pages. */
  const PUFF_COOLEST = 0.55;
  /** Spark alpha buckets (strokes are batched per colour × alpha × width). */
  const ALPHA_STEPS = 4;
  const STYLES = 2 * HEAT_STEPS * ALPHA_STEPS;
  /** STYLES × two stroke widths. */
  const BUCKETS = STYLES * 2;
  /** Spark streak = velocity × this many seconds, capped at STREAK_CAP·S px. */
  const STREAK_S = 0.022;
  const STREAK_CAP = 48;
  const SPRITE = 64;
  const PALS = [FIRE_HOT, FIRE_BLUE] as const;
  const SHOCK_RGB: Rgb[] = [hexToRgb('#ffd166'), hexToRgb('#7dd3fc')];
  const FLASH_RGB: [Rgb, Rgb][] = [
    [hexToRgb('#fff7d6'), hexToRgb('#ff9f1c')],
    [hexToRgb('#ffffff'), hexToRgb('#38bdf8')],
  ];

  const sim = createOverlaySim(3000);
  const gov = createGovernor();
  const pacer = createFramePacer();
  let canvas = $state<HTMLCanvasElement>();
  let ctx: CanvasRenderingContext2D | null = null;
  let W = 0;
  let H = 0;
  let dpr = 1;
  let raf = 0;
  let frames = 0;
  let workMs = 0;
  let font = 'system-ui, sans-serif';
  let bannerFit: { text: string; size: number } | null = null;

  // Built on mount: puff glow sprites per palette × heat, one smoke sprite, batched spark styles.
  let puffSprites: HTMLCanvasElement[][] = [];
  let smokeSprite: HTMLCanvasElement | null = null;
  const sparkStyle: string[] = [];
  const confettiFill: string[][] = [];
  const bucketOf = new Uint8Array(sim.capacity);
  const order = new Int32Array(sim.capacity);
  const counts = new Int32Array(BUCKETS + 1);
  const cursor = new Int32Array(BUCKETS);

  /** Colour at t (0 hot … 1 cool) across a palette as an RGB triple. */
  function rgbAt(stops: readonly string[], t: number): Rgb {
    const seg = Math.min(1, Math.max(0, t)) * (stops.length - 1);
    const i = Math.min(Math.floor(seg), stops.length - 2);
    return mixRgb(hexToRgb(stops[i]), hexToRgb(stops[i + 1]), seg - i);
  }
  const rgba = (c: Rgb, a: number) => `rgba(${c[0] | 0},${c[1] | 0},${c[2] | 0},${Math.round(a * 1000) / 1000})`;

  function sprite(paint: (g: CanvasRenderingContext2D) => void): HTMLCanvasElement {
    const s = document.createElement('canvas');
    s.width = s.height = SPRITE;
    const g = s.getContext('2d');
    if (g) paint(g);
    return s;
  }

  function radialSprite(stops: [number, string][]): HTMLCanvasElement {
    return sprite((g) => {
      const h = SPRITE / 2;
      const grad = g.createRadialGradient(h, h, 0, h, h, h);
      for (const [o, c] of stops) grad.addColorStop(o, c);
      g.fillStyle = grad;
      g.fillRect(0, 0, SPRITE, SPRITE);
    });
  }

  function buildStyles() {
    puffSprites = PALS.map((pal) =>
      Array.from({ length: PUFF_STEPS }, (_, k) => {
        const c = rgbAt(pal, (k / (PUFF_STEPS - 1)) * PUFF_COOLEST);
        return radialSprite([
          [0, rgba(c, 1)],
          [0.35, rgba(c, 0.55)],
          [0.7, rgba(c, 0.15)],
          [1, rgba(c, 0)],
        ]);
      }),
    );
    smokeSprite = radialSprite([
      [0, 'rgba(96,92,100,0.55)'],
      [0.6, 'rgba(96,92,100,0.2)'],
      [1, 'rgba(96,92,100,0)'],
    ]);
    sparkStyle.length = 0;
    for (let b = 0; b < STYLES; b++) {
      const a = b % ALPHA_STEPS;
      const h = Math.floor(b / ALPHA_STEPS) % HEAT_STEPS;
      const p = Math.floor(b / (ALPHA_STEPS * HEAT_STEPS));
      sparkStyle.push(rgba(rgbAt(PALS[p], (h / (HEAT_STEPS - 1)) * 0.85), (a + 1) / ALPHA_STEPS));
    }
    confettiFill.length = 0;
    for (const pal of PALS) confettiFill.push(pal.slice(1, 5)); // skip the near-black tail
  }

  /** Match the window, the DPR and the governor's DPR cap. */
  function fit() {
    if (!canvas || !ctx) return;
    const w = window.innerWidth;
    const h = window.innerHeight;
    const d = Math.min(window.devicePixelRatio || 1, MAX_DPR, gov.config.dprCap);
    if (w === W && h === H && d === dpr && canvas.width > 1) return;
    W = w;
    H = h;
    dpr = d;
    canvas.width = Math.max(1, Math.round(w * d));
    canvas.height = Math.max(1, Math.round(h * d));
  }

  function drawFlash(g: CanvasRenderingContext2D) {
    const f = sim.flash;
    if (f <= 0.01) return;
    const [core, mid] = FLASH_RGB[sim.flashPal];
    const R = Math.hypot(W, H) * 0.8;
    const grad = g.createRadialGradient(sim.flashX, sim.flashY, 0, sim.flashX, sim.flashY, R);
    grad.addColorStop(0, rgba(core, 0.95 * f));
    grad.addColorStop(0.18, rgba(mid, 0.55 * f));
    grad.addColorStop(0.55, rgba(mid, 0.12 * f));
    grad.addColorStop(1, rgba(mid, 0));
    g.fillStyle = grad;
    g.fillRect(0, 0, W, H);
  }

  function drawShocks(g: CanvasRenderingContext2D, glow: number) {
    for (const s of sim.shocks) {
      if (!s.alive || s.r <= 0) continue;
      const k = s.life / s.max;
      const c = SHOCK_RGB[s.pal];
      g.beginPath();
      g.arc(s.x, s.y, s.r, 0, Math.PI * 2);
      if (glow > 0) {
        g.lineWidth = s.width * (0.6 + 1.4 * k);
        g.strokeStyle = rgba(c, 0.18 * k);
        g.stroke();
      }
      g.lineWidth = Math.max(1, s.width * 0.35 * k);
      g.strokeStyle = rgba(c, 0.85 * k * k);
      g.stroke();
    }
  }

  function drawSmoke(g: CanvasRenderingContext2D) {
    if (!smokeSprite) return;
    for (let i = 0; i < sim.alive; i++) {
      if (sim.kind[i] !== O_SMOKE) continue;
      const a = sim.alpha(i);
      if (a <= 0.01) continue;
      const d = sim.size[i] * 2;
      g.globalAlpha = Math.min(1, a * 1.6);
      g.drawImage(smokeSprite, sim.x[i] - d / 2, sim.y[i] - d / 2, d, d);
    }
    g.globalAlpha = 1;
  }

  function drawPuffs(g: CanvasRenderingContext2D) {
    const top = PUFF_STEPS - 1;
    for (let i = 0; i < sim.alive; i++) {
      if (sim.kind[i] !== O_PUFF) continue;
      const a = sim.alpha(i);
      if (a <= 0.01) continue;
      const set = puffSprites[sim.pal[i]];
      if (!set) continue;
      const d = sim.size[i] * 2;
      g.globalAlpha = a;
      g.drawImage(set[Math.min(top, Math.floor(sim.heat(i) * PUFF_STEPS))], sim.x[i] - d / 2, sim.y[i] - d / 2, d, d);
    }
    g.globalAlpha = 1;
  }

  /** Sparks and embers as velocity streaks, counting-sorted into colour × alpha × width buckets: one stroke each. */
  function drawSparks(g: CanvasRenderingContext2D, S: number, glow: number) {
    const n = sim.alive;
    counts.fill(0);
    const thick = 2.4 * S;
    for (let i = 0; i < n; i++) {
      const k = sim.kind[i];
      if (k !== O_SPARK && k !== O_EMBER) {
        bucketOf[i] = 255;
        continue;
      }
      const a = sim.alpha(i);
      if (a <= 0.03) {
        bucketOf[i] = 255;
        continue;
      }
      const h = Math.min(HEAT_STEPS - 1, Math.floor(sim.heat(i) * HEAT_STEPS));
      const al = Math.min(ALPHA_STEPS - 1, Math.floor(a * ALPHA_STEPS));
      const w = sim.size[i] > thick ? 1 : 0;
      const b = ((w * 2 + sim.pal[i]) * HEAT_STEPS + h) * ALPHA_STEPS + al;
      bucketOf[i] = b;
      counts[b + 1]++;
    }
    for (let b = 0; b < BUCKETS; b++) counts[b + 1] += counts[b];
    cursor.set(counts.subarray(0, BUCKETS));
    for (let i = 0; i < n; i++) {
      const b = bucketOf[i];
      if (b !== 255) order[cursor[b]++] = i;
    }
    const cap = STREAK_CAP * S;
    g.lineCap = 'round';
    for (let b = 0; b < BUCKETS; b++) {
      const from = counts[b];
      const to = counts[b + 1];
      if (from === to) continue;
      g.beginPath();
      for (let j = from; j < to; j++) {
        const i = order[j];
        let dx = sim.vx[i] * STREAK_S;
        let dy = sim.vy[i] * STREAK_S;
        const len = Math.hypot(dx, dy);
        if (len > cap) {
          dx *= cap / len;
          dy *= cap / len;
        } else if (len < 0.5) {
          dy = -0.5; // a dot (round caps) for slow embers
        }
        g.moveTo(sim.x[i], sim.y[i]);
        g.lineTo(sim.x[i] - dx, sim.y[i] - dy);
      }
      const base = b >= STYLES ? 3 * S : 1.8 * S;
      g.strokeStyle = sparkStyle[b % STYLES];
      if (glow >= 2) {
        g.globalAlpha = 0.22;
        g.lineWidth = base * 3.2;
        g.stroke();
        g.globalAlpha = 1;
      }
      g.lineWidth = Math.max(1, base);
      g.stroke();
    }
  }

  function drawConfetti(g: CanvasRenderingContext2D) {
    for (let i = 0; i < sim.alive; i++) {
      if (sim.kind[i] !== O_CONFETTI) continue;
      const a = sim.alpha(i);
      if (a <= 0.02) continue;
      const fills = confettiFill[sim.pal[i]];
      const r = sim.rot[i];
      const c = Math.cos(r) * dpr;
      const s = Math.sin(r) * dpr;
      // flip about the long axis so the pieces tumble
      const flip = Math.cos(r * 1.7 + sim.seed[i] * 6.28);
      const w = sim.size[i];
      const h = w * 0.5 * (0.25 + 0.75 * Math.abs(flip));
      g.setTransform(c, s, -s, c, sim.x[i] * dpr, sim.y[i] * dpr);
      g.globalAlpha = a;
      g.fillStyle = fills[Math.floor(sim.seed[i] * fills.length) % fills.length];
      g.fillRect(-w / 2, -h / 2, w, h);
    }
    g.globalAlpha = 1;
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  function drawBanner(g: CanvasRenderingContext2D, glow: number) {
    const b = sim.banner;
    if (!b) return;
    const t = 1 - b.life / b.max;
    const inT = Math.min(1, t / 0.14);
    // easeOutBack pop-in, fade over the last 30%
    const c1 = 1.9;
    const pop = 1 + (c1 + 1) * (inT - 1) ** 3 + c1 * (inT - 1) ** 2;
    const alpha = Math.min(1, inT * 2, b.life / (b.max * 0.3));
    if (alpha <= 0.01) return;
    if (!bannerFit || bannerFit.text !== b.text) {
      let size = Math.min(110, Math.max(34, Math.min(W, H) * 0.11));
      g.font = `900 ${size}px ${font}`;
      const w = g.measureText(b.text).width;
      if (w > W * 0.88) size *= (W * 0.88) / w;
      bannerFit = { text: b.text, size };
    }
    const size = bannerFit.size;
    const x = W / 2;
    const y = H * 0.3 - t * size * 0.35; // drifts up a little
    g.save();
    g.translate(x, y);
    g.scale(pop, pop);
    g.globalAlpha = alpha;
    g.font = `900 ${size}px ${font}`;
    g.textAlign = 'center';
    g.textBaseline = 'middle';
    g.lineJoin = 'round';
    const pal = PALS[b.pal];
    if (glow > 0) {
      g.shadowColor = rgba(rgbAt(pal, 0.55), 0.9);
      g.shadowBlur = size * 0.45 * dpr;
    }
    g.lineWidth = Math.max(2, size * 0.09);
    g.strokeStyle = b.pal ? 'rgba(15,12,60,0.85)' : 'rgba(60,8,0,0.85)';
    g.strokeText(b.text, 0, 0);
    g.shadowBlur = 0;
    const grad = g.createLinearGradient(0, -size / 2, 0, size / 2);
    grad.addColorStop(0, pal[0]);
    grad.addColorStop(0.45, pal[2]);
    grad.addColorStop(1, pal[4]);
    g.fillStyle = grad;
    g.fillText(b.text, 0, 0);
    g.restore();
  }

  function draw() {
    const g = ctx;
    if (!g) return;
    const glow = gov.config.glow;
    const S = Math.max(0.2, Math.min(W, H) / 700);
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    g.globalCompositeOperation = 'source-over';
    g.globalAlpha = 1;
    g.clearRect(0, 0, W, H);
    g.globalCompositeOperation = 'lighter';
    drawFlash(g);
    drawShocks(g, glow);
    g.globalCompositeOperation = 'source-over';
    drawSmoke(g);
    g.globalCompositeOperation = 'lighter';
    drawPuffs(g);
    drawSparks(g, S, glow);
    g.globalCompositeOperation = 'source-over';
    drawConfetti(g);
    drawBanner(g, glow);
  }

  function frame(t: number) {
    raf = 0;
    if (!ctx) return;
    const interval = pacer.tick(t, gov.config.fps);
    if (interval < 0) {
      raf = requestAnimationFrame(frame);
      return;
    }
    const t0 = performance.now();
    fit();
    sim.step(interval ? interval / 1000 : 1 / 60, W, H);
    draw();
    const work = performance.now() - t0;
    frames++;
    workMs += work;
    if (interval) gov.sample(work, interval);
    if (sim.active && $animationsActive) raf = requestAnimationFrame(frame);
    else stop();
  }

  function start() {
    if (raf || !ctx || !canvas) return;
    fit();
    canvas.hidden = false;
    pacer.reset();
    raf = requestAnimationFrame(frame);
  }

  /** Idle: no rAF, hidden, and the full-window backing store released. */
  function stop() {
    if (raf) cancelAnimationFrame(raf);
    raf = 0;
    pacer.reset();
    bannerFit = null;
    if (!canvas) return;
    canvas.hidden = true;
    canvas.width = canvas.height = 1;
    W = H = 0;
  }

  const spawnOpts = () => ({ W: window.innerWidth, H: window.innerHeight, scale: gov.config.particleScale });
  const canSpawn = () => !!ctx && $animationsActive;

  /** Clock-out explosion at client (x, y); returns particles spawned. */
  export function blast(x: number, y: number, opts: { power?: number; pal?: 0 | 1 } = {}): number {
    if (!canSpawn()) return 0;
    const n = sim.blast(x, y, { ...spawnOpts(), ...opts });
    start();
    return n;
  }

  /** Milestone flare at client (x, y); tier >= 2 shows the banner. */
  export function flare(x: number, y: number, tier: Tier, opts: { pal?: 0 | 1; label?: string } = {}): number {
    if (!canSpawn()) return 0;
    const n = sim.flare(x, y, tier, { ...spawnOpts(), ...opts });
    start();
    return n;
  }

  /** Discarded shift: a sad puff of smoke. */
  export function fizzle(x: number, y: number): number {
    if (!canSpawn()) return 0;
    const n = sim.fizzle(x, y, spawnOpts());
    start();
    return n;
  }

  /** Governor level (0 best … LEVELS.length - 1 cheapest). */
  export function level(): number {
    return gov.level;
  }

  export function lowestQuality(): boolean {
    return gov.level >= LEVELS.length - 1;
  }

  export function stats(): OverlayStats {
    return { alive: sim.alive, active: sim.active, running: raf !== 0, level: gov.level, frames, workMs };
  }

  // Hidden / unfocused: drop whatever is in flight rather than replaying it on return.
  $effect(() => {
    if (!$animationsActive) {
      sim.clear();
      stop();
    }
  });

  onMount(() => {
    ctx = canvas?.getContext('2d') ?? null;
    if (!ctx) return;
    font = cssVar('--font-ui') || font;
    buildStyles();
    stop();
    return () => {
      stop();
      sim.clear();
      ctx = null;
    };
  });
</script>

<canvas bind:this={canvas} class="fx-overlay" aria-hidden="true" hidden use:portal></canvas>

<style>
  .fx-overlay {
    position: fixed;
    inset: 0;
    width: 100vw;
    height: 100vh;
    z-index: 240;
    pointer-events: none;
  }
  .fx-overlay[hidden] {
    display: none;
  }
</style>
