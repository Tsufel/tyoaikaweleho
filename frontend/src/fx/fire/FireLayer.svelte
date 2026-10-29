<script lang="ts">
  import { onMount } from 'svelte';
  import { animationsActive } from '../../lib/stores/app';
  import { lulz, motion } from '../../lib/stores/motion';
  import { settings } from '../../lib/stores/settings';
  import { FIRE } from '../../lib/theme/tokens';
  import { FIRE_OVERHANG, RING, fireIntensity } from '../../views/timer/timerLogic';
  import { KIND_EMBER, createFire } from './fireSim';
  import WizardPop from './WizardPop.svelte';
  import { shouldPopWizard } from './wizardPop';

  /** Lulz: additive Canvas2D fire around the hero ring. Fills its positioned
   *  parent, which overhangs the ring box by FIRE_OVERHANG on every side.
   *  30 fps cap; the loop stops when idle with no live particles or hidden. */
  let { running, elapsedSeconds, burst }: { running: boolean; elapsedSeconds: number; burst: number } = $props();

  const FRAME_MS = 1000 / 30;
  const sim = createFire(900);
  let canvas = $state<HTMLCanvasElement>();
  let ctx: CanvasRenderingContext2D | null = null;
  let sprites: HTMLCanvasElement[] = [];
  let w = 0;
  let h = 0;
  let raf = 0;
  let last = 0;
  let lastFrame = 0;
  /** Bumped per clock-out; keys a fresh wizard pop (0 = none showing). */
  let wizardRun = $state(0);

  const intensity = $derived(fireIntensity(elapsedSeconds, $settings.ui_prefs.target_hours));

  function makeSprites() {
    sprites = FIRE.map((c) => {
      const s = document.createElement('canvas');
      s.width = s.height = 64;
      const g = s.getContext('2d');
      if (!g) return s;
      const grad = g.createRadialGradient(32, 32, 0, 32, 32, 32);
      grad.addColorStop(0, c);
      grad.addColorStop(0.35, c + 'aa');
      grad.addColorStop(1, c + '00');
      g.fillStyle = grad;
      g.fillRect(0, 0, 64, 64);
      return s;
    });
  }

  function geometry() {
    const box = Math.min(w, h) / (1 + 2 * FIRE_OVERHANG);
    return { cx: w / 2, cy: h / 2, r: (box * RING.r) / RING.size };
  }

  function resize() {
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    w = rect.width;
    h = rect.height;
    canvas.width = Math.max(1, Math.round(w * dpr));
    canvas.height = Math.max(1, Math.round(h * dpr));
    ctx?.setTransform(dpr, 0, 0, dpr, 0, 0);
    if (running || sim.alive > 0) kick();
  }

  function draw() {
    if (!ctx) return;
    ctx.globalCompositeOperation = 'source-over';
    ctx.clearRect(0, 0, w, h);
    ctx.globalCompositeOperation = 'lighter';
    const n = sim.alive;
    const top = sprites.length - 1;
    for (let i = 0; i < n; i++) {
      const a = sim.alpha(i);
      if (a <= 0.01) continue;
      const sprite = sprites[Math.min(top, Math.floor(sim.heat(i) * sprites.length))];
      const d = sim.kind[i] === KIND_EMBER ? sim.size[i] * 5 : sim.size[i] * 2;
      ctx.globalAlpha = a;
      ctx.drawImage(sprite, sim.x[i] - d / 2, sim.y[i] - d / 2, d, d);
    }
    ctx.globalAlpha = 1;
  }

  function frame(t: number) {
    raf = 0;
    if (t - lastFrame >= FRAME_MS - 1) {
      const dt = last ? (t - last) / 1000 : 0;
      last = t;
      lastFrame = t;
      const g = geometry();
      if (running) sim.emitRing(g.cx, g.cy, g.r, intensity, dt);
      sim.step(dt);
      draw();
    }
    if ((running || sim.alive > 0) && canRun()) raf = requestAnimationFrame(frame);
    else {
      last = 0;
      if (!sim.alive) draw();
    }
  }

  /** Window shown and focused, canvas laid out (the pane can be display:none). */
  function canRun(): boolean {
    return $animationsActive && w > 0 && h > 0;
  }

  function kick() {
    if (raf || !ctx || !canRun()) return;
    last = 0;
    raf = requestAnimationFrame(frame);
  }

  let seenBurst = -1;
  $effect(() => {
    const b = burst;
    if (seenBurst === -1) {
      seenBurst = b;
      return;
    }
    if (b === seenBurst) return;
    seenBurst = b;
    const g = geometry();
    sim.burst(g.cx, g.cy, g.r);
    kick();
    if (shouldPopWizard($lulz, $motion)) wizardRun = b + 1;
  });

  $effect(() => {
    if ((running || sim.alive > 0) && $animationsActive) kick();
  });

  onMount(() => {
    ctx = canvas?.getContext('2d') ?? null;
    if (!ctx || !canvas) return;
    makeSprites();
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(canvas);
    kick();
    return () => {
      ro.disconnect();
      if (raf) cancelAnimationFrame(raf);
      raf = 0;
      sim.clear();
    };
  });
</script>

<canvas bind:this={canvas} class="fire" aria-hidden="true"></canvas>
{#if wizardRun && shouldPopWizard($lulz, $motion)}
  {#key wizardRun}
    <WizardPop ondone={() => (wizardRun = 0)} />
  {/key}
{/if}

<style>
  .fire {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    pointer-events: none;
  }
</style>
