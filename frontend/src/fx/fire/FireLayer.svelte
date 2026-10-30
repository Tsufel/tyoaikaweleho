<script lang="ts">
  import { onMount } from 'svelte';
  import { animationsActive, pageVisible } from '../../lib/stores/app';
  import { settings } from '../../lib/stores/settings';
  import { isDark } from '../../lib/theme/theme';
  import { RING, RING_INNER, fireIntensity, ringProgress } from '../../views/timer/timerLogic';
  import { IGNITE_MS, boostEnvelope, fuseProgress, gust } from './choreo';
  import { KIND_CORE, KIND_EMBER, KIND_FLAME, KIND_SMOKE, KIND_SPARK, MAX_INTENSITY, createFire } from './fireSim';
  import { onFx, setRingAnchor, type FxEvent } from './fxBus';
  import { createNoise } from './noise';
  import { createFramePacer, createGovernor } from './quality';
  import { STEPS, TONGUE_PIVOT, paletteSprites, smokeSprite, type PaletteSprites } from './sprites';

  /** Lulz: Canvas2D fire around the hero ring. The canvas fills the whole
   *  timer card (rounded clip) and finds the ring through `ring`'s rect, so
   *  flames are never cut off at a box around the ring. Up to 60 fps under an
   *  adaptive quality governor; the loop stops when idle with no live
   *  particles, hidden or unfocused (in-flight effects are dropped then, not
   *  replayed on return). The clock disc is always masked clean. */
  let { running, elapsedSeconds, ring }: { running: boolean; elapsedSeconds: number; ring: HTMLElement | undefined } =
    $props();

  const TAU = Math.PI * 2;
  /** Device px per CSS px for the glow pass (quarter res, blurred). */
  const GLOW_RES = 0.25;
  /** Feather the clock mask out to the inner edge of the ring stroke. */
  const MASK_OUTER = RING.r - RING.stroke / 2;

  const sim = createFire(1600);
  const gov = createGovernor();
  const pacer = createFramePacer();
  const noise = createNoise(11);
  let canvas = $state<HTMLCanvasElement>();
  let ctx: CanvasRenderingContext2D | null = null;
  const glowCv = document.createElement('canvas');
  const blurCv = document.createElement('canvas');
  const glowCtx = glowCv.getContext('2d');
  const blurCtx = blurCv.getContext('2d');
  let pals: PaletteSprites[] = [];
  let smoke: HTMLCanvasElement | null = null;
  let w = 0;
  let h = 0;
  let dpr = 1;
  let raf = 0;
  /** Inside frame(): resize()/kick() must not start a second rAF chain. */
  let inFrame = false;
  let destroyed = false;
  /** Ring centre / radius in canvas CSS px; ok=false while either box is 0×0. */
  const geo = { ok: false, cx: 0, cy: 0, r: 0, scale: 1 };
  /** performance.now() of the last ignite (0 = no fuse running). */
  let igniteAt = 0;
  /** Fuse head 0…1 this frame, -1 = none. */
  let fuse = -1;
  let boostAt = -Infinity;
  let boostPeak = 1;
  let boostMs = 1200;

  const target = $derived($settings.ui_prefs.target_hours);
  const base = $derived(fireIntensity(elapsedSeconds, target));
  const blue = $derived(ringProgress(elapsedSeconds, target) > 1 ? 1 : 0);

  function boost(peak: number, ms = 1200) {
    boostAt = performance.now();
    boostPeak = peak;
    boostMs = ms;
  }

  /** Ring geometry from the live rects (follows transforms such as the stage
   *  pop) and the anchor the full-window director aims at. */
  function measure(): boolean {
    geo.ok = false;
    if (!canvas || !ring) return false;
    const c = canvas.getBoundingClientRect();
    const rr = ring.getBoundingClientRect();
    if (c.width < 1 || c.height < 1 || rr.width < 1 || rr.height < 1) {
      setRingAnchor(null);
      return false;
    }
    const x = rr.left + rr.width / 2;
    const y = rr.top + rr.height / 2;
    geo.scale = Math.min(rr.width, rr.height) / RING.size;
    geo.r = RING.r * geo.scale;
    geo.cx = x - c.left;
    geo.cy = y - c.top;
    geo.ok = true;
    const onScreen = rr.bottom > 0 && rr.right > 0 && rr.top < innerHeight && rr.left < innerWidth;
    setRingAnchor($pageVisible && onScreen ? { x, y, r: geo.r, at: performance.now() } : null);
    return true;
  }

  function resize() {
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    dpr = Math.min(gov.config.dprCap, window.devicePixelRatio || 1);
    w = rect.width;
    h = rect.height;
    canvas.width = Math.max(1, Math.round(w * dpr));
    canvas.height = Math.max(1, Math.round(h * dpr));
    glowCv.width = blurCv.width = Math.max(1, Math.ceil(w * GLOW_RES));
    glowCv.height = blurCv.height = Math.max(1, Math.ceil(h * GLOW_RES));
    pals = [paletteSprites(0, dpr), paletteSprites(1, dpr)];
    smoke = smokeSprite($isDark, dpr);
    measure();
    if (running || sim.alive > 0) kick();
  }

  function applyLevel() {
    const cfg = gov.config;
    sim.setSmoke(cfg.smoke);
    if (Math.min(cfg.dprCap, window.devicePixelRatio || 1) !== dpr) resize();
  }

  function emit(t: number, dt: number) {
    const rate = gov.config.particleScale;
    const { cx, cy, r } = geo;
    const inten = base * gust(t / 1000, noise.n1) * boostEnvelope(t - boostAt, boostPeak, boostMs);
    fuse = -1;
    if (igniteAt) {
      const ms = Math.max(0, t - igniteAt);
      if (ms < IGNITE_MS) {
        // the fuse runs clockwise from 12 o'clock, lighting the arc behind it
        fuse = fuseProgress(ms);
        const a = fuse * TAU;
        if (a > 0.01) {
          sim.emitRing(cx, cy, r, Math.max(inten, 0.9), dt, { arcFrom: 0, arcTo: a, blue, rate });
          sim.emitRing(cx, cy, r, MAX_INTENSITY, dt, { arcFrom: Math.max(0, a - 0.4), arcTo: a, blue, rate });
        }
        return;
      }
      igniteAt = 0;
      sim.flare(cx, cy, r, 1.3 * Math.max(0.5, rate), blue);
      boost(2.2);
    }
    if (running) sim.emitRing(cx, cy, r, inten, dt, { blue, rate });
  }

  function draw(t: number) {
    const c = ctx;
    if (!c) return;
    c.setTransform(dpr, 0, 0, dpr, 0, 0);
    c.globalCompositeOperation = 'source-over';
    c.globalAlpha = 1;
    c.clearRect(0, 0, w, h);
    if (!geo.ok || !pals.length) return;
    const cfg = gov.config;
    const n = sim.alive;
    const top = STEPS - 1;
    const { x, y, vx, vy, size, kind, pal } = sim;
    const step = (i: number) => Math.min(top, Math.floor(sim.heat(i) * STEPS));

    // 1. smoke, behind everything (normal blending so it reads on light themes)
    if (cfg.smoke && smoke) {
      for (let i = 0; i < n; i++) {
        if (kind[i] !== KIND_SMOKE) continue;
        const a = sim.alpha(i);
        if (a <= 0.01) continue;
        const d = size[i] * 2.6;
        c.globalAlpha = a;
        c.drawImage(smoke, x[i] - d / 2, y[i] - d / 2, d, d);
      }
    }

    c.globalCompositeOperation = 'lighter';
    // 2. hot line hugging the ring's outer edge (just the lit arc while the fuse runs)
    const lit = fuse >= 0 ? fuse : running ? 1 : 0;
    const rOut = geo.r + (RING.stroke / 2) * geo.scale;
    if (lit > 0.005) {
      const p = pals[blue];
      c.globalAlpha = Math.min(0.85, 0.3 + 0.35 * base) * (0.85 + 0.15 * noise.n1(t / 90));
      c.strokeStyle = p.color[2];
      c.lineWidth = 2.5 * geo.scale + 1;
      c.beginPath();
      c.arc(geo.cx, geo.cy, rOut, -Math.PI / 2, -Math.PI / 2 + lit * TAU);
      c.stroke();
    }

    // 3. flame tongues, stretched along their velocity, flickering
    for (let i = 0; i < n; i++) {
      if (kind[i] !== KIND_FLAME) continue;
      const fl = sim.flicker(i);
      const a = sim.alpha(i) * fl;
      if (a <= 0.01) continue;
      const s = Math.hypot(vx[i], vy[i]);
      // unit direction; still flames point straight up
      const ux = s > 1 ? vx[i] / s : 0;
      const uy = s > 1 ? vy[i] / s : -1;
      const len = size[i] * (2 + Math.min(2.4, s / 80)) * (0.75 + 0.25 * fl);
      const wid = size[i] * 1.25;
      c.globalAlpha = a;
      // rotate local "up" onto (ux, uy)
      c.setTransform(-uy * dpr, ux * dpr, -ux * dpr, -uy * dpr, x[i] * dpr, y[i] * dpr);
      c.drawImage(pals[pal[i]].tongue[step(i)], -wid / 2, -len * TONGUE_PIVOT, wid, len);
    }
    c.setTransform(dpr, 0, 0, dpr, 0, 0);

    // 4. white-hot cores and embers
    for (let i = 0; i < n; i++) {
      const k = kind[i];
      if (k !== KIND_CORE && k !== KIND_EMBER) continue;
      const a = sim.alpha(i);
      if (a <= 0.01) continue;
      const d = k === KIND_EMBER ? size[i] * 4.5 : size[i] * 2.4;
      c.globalAlpha = a;
      c.drawImage(pals[pal[i]].glow[step(i)], x[i] - d / 2, y[i] - d / 2, d, d);
    }
    if (fuse >= 0) {
      // the fuse spark itself
      const a = fuse * TAU;
      const fx = geo.cx + Math.sin(a) * rOut;
      const fy = geo.cy - Math.cos(a) * rOut;
      const d = geo.r * 0.45;
      c.globalAlpha = 1;
      c.drawImage(pals[blue].glow[0], fx - d / 2, fy - d / 2, d, d);
      c.drawImage(pals[blue].glow[0], fx - d / 4, fy - d / 4, d / 2, d / 2);
    }

    // 5. spark streaks: one path per palette and alpha band
    c.lineCap = 'round';
    c.lineWidth = 1.3;
    for (let p = 0; p < 2; p++) {
      for (let band = 0; band < 3; band++) {
        c.beginPath();
        let any = false;
        for (let i = 0; i < n; i++) {
          if (kind[i] !== KIND_SPARK || pal[i] !== p) continue;
          const a = sim.alpha(i);
          if (a <= 0.02 || Math.min(2, Math.floor(a * 3)) !== band) continue;
          c.moveTo(x[i], y[i]);
          c.lineTo(x[i] - vx[i] * 0.035, y[i] - vy[i] * 0.035);
          any = true;
        }
        if (!any) continue;
        c.globalAlpha = (band + 1) / 3;
        c.strokeStyle = pals[p].color[1];
        c.stroke();
      }
    }

    // 6. quarter-res bloom: flames, cores and the ring band, blurred and added back
    if (cfg.glow > 0 && glowCtx && blurCtx) {
      const g = glowCtx;
      g.setTransform(1, 0, 0, 1, 0, 0);
      g.globalCompositeOperation = 'source-over';
      g.globalAlpha = 1;
      g.clearRect(0, 0, glowCv.width, glowCv.height);
      g.setTransform(GLOW_RES, 0, 0, GLOW_RES, 0, 0);
      g.globalCompositeOperation = 'lighter';
      if (lit > 0.005) {
        g.globalAlpha = Math.min(0.6, 0.18 + 0.25 * base);
        g.strokeStyle = pals[blue].color[4];
        g.lineWidth = geo.r * 0.22;
        g.beginPath();
        g.arc(geo.cx, geo.cy, rOut, -Math.PI / 2, -Math.PI / 2 + lit * TAU);
        g.stroke();
      }
      for (let i = 0; i < n; i++) {
        const k = kind[i];
        if (k === KIND_SMOKE || k === KIND_SPARK) continue;
        const a = sim.alpha(i);
        if (a <= 0.02) continue;
        const d = (k === KIND_FLAME ? size[i] * 3.2 : k === KIND_CORE ? size[i] * 4 : size[i] * 8) + 4;
        g.globalAlpha = a * 0.35;
        g.drawImage(pals[pal[i]].glow[step(i)], x[i] - d / 2, y[i] - d / 2, d, d);
      }
      let src = glowCv;
      if (cfg.glow > 1) {
        blurCtx.clearRect(0, 0, blurCv.width, blurCv.height);
        blurCtx.filter = 'blur(3px)';
        blurCtx.drawImage(glowCv, 0, 0);
        blurCtx.filter = 'none';
        src = blurCv;
      }
      c.globalAlpha = cfg.glow > 1 ? 0.9 : 0.6;
      c.drawImage(src, 0, 0, glowCv.width / GLOW_RES, glowCv.height / GLOW_RES);
    }

    // 7. last: punch the clock disc out so nothing ever covers the digits
    const r0 = RING_INNER * geo.scale;
    const r1 = MASK_OUTER * geo.scale;
    const m = c.createRadialGradient(geo.cx, geo.cy, 0, geo.cx, geo.cy, r1);
    m.addColorStop(0, '#000');
    m.addColorStop(r0 / r1, '#000');
    m.addColorStop(1, 'rgba(0,0,0,0)');
    c.globalCompositeOperation = 'destination-out';
    c.globalAlpha = 1;
    c.fillStyle = m;
    c.fillRect(geo.cx - r1, geo.cy - r1, r1 * 2, r1 * 2);
    c.globalCompositeOperation = 'source-over';
  }

  function live(t: number): boolean {
    return running || sim.alive > 0 || (igniteAt > 0 && t - igniteAt < IGNITE_MS + 500);
  }

  function frame(t: number) {
    raf = 0;
    if (destroyed) return;
    if (!canRun()) {
      pacer.reset();
      return;
    }
    const interval = pacer.tick(t, gov.config.fps);
    if (interval < 0) {
      raf = requestAnimationFrame(frame);
      return;
    }
    inFrame = true;
    const t0 = performance.now();
    if (measure() && interval) emit(t, interval / 1000);
    sim.step(interval / 1000);
    draw(t);
    if (interval) {
      const before = gov.level;
      gov.sample(performance.now() - t0, interval);
      if (gov.level !== before) applyLevel();
    }
    inFrame = false;
    if (live(t)) {
      if (!raf) raf = requestAnimationFrame(frame);
    } else {
      pacer.reset();
      draw(t);
    }
  }

  /** Window shown and focused, canvas laid out (the pane can be display:none). */
  function canRun(): boolean {
    return $animationsActive && w > 0 && h > 0;
  }

  function kick() {
    if (raf || inFrame || destroyed || !ctx || !canRun()) return;
    pacer.reset();
    raf = requestAnimationFrame(frame);
  }

  /** Drop everything in flight (fuse, flares, bursts, boost) and blank the canvas. */
  function halt() {
    if (raf) cancelAnimationFrame(raf);
    raf = 0;
    pacer.reset();
    sim.clear();
    igniteAt = 0;
    fuse = -1;
    boostAt = -Infinity;
    if (ctx && canvas) {
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.clearRect(0, 0, canvas.width, canvas.height);
    }
  }

  function onEvent(e: FxEvent) {
    // hidden pane / minimised: no geometry to aim at, and nothing would play
    if (!canRun() || !measure()) return;
    const { cx, cy, r } = geo;
    const scale = Math.max(0.5, gov.config.particleScale);
    switch (e.kind) {
      case 'ignite':
        igniteAt = performance.now();
        break;
      case 'milestone': {
        const tier = e.m.tier;
        sim.flare(cx, cy, r, (0.7 + 0.35 * tier) * scale, e.m.blue ? 1 : 0);
        boost(1.5 + 0.25 * tier, 900 + 250 * tier);
        break;
      }
      case 'blast':
        // the shift has already stopped (blue is 0 by now): judge overtime from the saved length, like the director
        sim.burst(cx, cy, r, Math.round(260 * scale), e.minutes != null && e.minutes > target * 60 ? 1 : 0);
        break;
      case 'fizzle':
        igniteAt = 0;
        boostAt = -Infinity;
        sim.douse();
        break;
      default:
        return;
    }
    kick();
  }

  $effect(() => {
    if ((running || sim.alive > 0) && $animationsActive) kick();
  });

  // Hidden / unfocused: a frozen fuse or burst would replay late on return; a running shift just re-emits.
  $effect(() => {
    if (!$animationsActive) halt();
  });

  // ring element arrives / changes after mount
  $effect(() => {
    if (!ring) return;
    const ro = new ResizeObserver(() => {
      measure();
      kick();
    });
    ro.observe(ring);
    return () => ro.disconnect();
  });

  $effect(() => {
    smoke = smokeSprite($isDark, dpr);
  });

  // keep the director's anchor fresh while the loop is idle; drop it when hidden
  $effect(() => {
    if (!$pageVisible) {
      setRingAnchor(null);
      return;
    }
    measure();
    const id = setInterval(() => {
      if (!raf) measure();
    }, 1000);
    return () => clearInterval(id);
  });

  onMount(() => {
    ctx = canvas?.getContext('2d') ?? null;
    if (!ctx || !canvas) return;
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(canvas);
    // devicePixelRatio changes (zoom, moving to another monitor) don't resize the box
    let mq: MediaQueryList | null = null;
    const watchDpr = () => {
      mq?.removeEventListener('change', onDpr);
      mq = matchMedia(`(resolution: ${window.devicePixelRatio || 1}dppx)`);
      mq.addEventListener('change', onDpr);
    };
    const onDpr = () => {
      watchDpr();
      resize();
    };
    watchDpr();
    const off = onFx(onEvent);
    kick();
    return () => {
      off();
      ro.disconnect();
      mq?.removeEventListener('change', onDpr);
      destroyed = true;
      halt();
      setRingAnchor(null);
    };
  });
</script>

<canvas bind:this={canvas} class="fire" aria-hidden="true"></canvas>

<style>
  .fire {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    pointer-events: none;
  }
</style>
