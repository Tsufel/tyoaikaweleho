<script lang="ts">
  // Liquid glass refraction filters: one <filter> per lens, mounted only in
  // the 'refract' tier. Elements reference them as backdrop-filter: url(#id)
  // via the liquidGlass action, and only once the filter exists here.
  import { onDestroy, onMount, untrack } from 'svelte';
  import { animationsActive } from '../stores/app';
  import { glassLive, refractBroken } from '../stores/glass';
  import { lensLoad, startFrameGuard } from './frameGuard';
  import { lightDriver } from './light';
  import { glassRegistry } from './registry.svelte';

  /** Dispersion channels: [suffix, scale factor, colour matrix]. */
  const CHANNELS: [string, number, string][] = [
    ['r', 0.94, '1 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 1 0'],
    ['g', 1, '0 0 0 0 0  0 1 0 0 0  0 0 0 0 0  0 0 0 1 0'],
    ['b', 1.06, '0 0 0 0 0  0 0 0 0 0  0 0 1 0 0  0 0 0 1 0'],
  ];

  const ready = $derived(glassRegistry.lenses.filter((l) => l.url));

  // Frame guard: sampled at start, then again whenever the lens load climbs
  // past anything sampled so far (a modal over the topbar, stacked toasts)
  // and when a scroller holding a lens (the sticky Settings header) scrolls.
  const SCROLL_RESAMPLE_MS = 15000;
  const load = $derived(lensLoad(glassRegistry.lenses));
  let stopGuard: (() => void) | null = null;
  let guardEnds = 0;
  let peak = 1;
  let mountedAt = 0;
  let lastScrollSample = -Infinity;

  function trip() {
    console.warn('liquid glass: frames too slow with refraction, using the CSS tier');
    refractBroken.set(true);
  }

  function arm(delayMs: number, sampleMs: number) {
    stopGuard?.();
    stopGuard = startFrameGuard(trip, delayMs, sampleMs);
    guardEnds = performance.now() + delayMs + sampleMs;
  }

  function onScroll(e: Event) {
    const now = performance.now();
    if (now < guardEnds || now - lastScrollSample < SCROLL_RESAMPLE_MS) return;
    const t = e.target instanceof Element ? e.target : document.documentElement;
    if (!t.querySelector('[style*="--lg-filter"]')) return;
    lastScrollSample = now;
    arm(0, 1000);
  }

  onMount(() => {
    mountedAt = performance.now();
    arm(1000, 2000);
    peak = Math.max(1, load);
    window.addEventListener('scroll', onScroll, { passive: true, capture: true });
    return () => {
      window.removeEventListener('scroll', onScroll, { capture: true });
      stopGuard?.();
      stopGuard = null;
    };
  });

  $effect(() => {
    const n = load;
    untrack(() => {
      if (!stopGuard || n <= peak) return;
      peak = n;
      // never sooner than the startup delay
      arm(Math.max(300, 1000 - (performance.now() - mountedAt)), 1000);
    });
  });

  onDestroy(() => glassRegistry.clear());

  // pointer light only while motion is full and the window is in use
  $effect(() => {
    if ($glassLive && $animationsActive) return lightDriver.start();
  });
</script>

<svg class="lg-defs" width="0" height="0" aria-hidden="true" focusable="false">
  {#each ready as l (l.id)}
    <filter
      id={l.id}
      x="0"
      y="0"
      width={l.w}
      height={l.h}
      filterUnits="userSpaceOnUse"
      primitiveUnits="userSpaceOnUse"
      color-interpolation-filters="sRGB"
    >
      <feImage href={l.url} x="0" y="0" width={l.w} height={l.h} preserveAspectRatio="none" result="map" />
      <feGaussianBlur in="SourceGraphic" stdDeviation="0.5" result="s0" />
      <feComponentTransfer in="s0" result="s1"><feFuncA type="table" tableValues="1 1" /></feComponentTransfer>
      <!-- back to the backdrop's own coverage: a no-op over an opaque backdrop,
           but inside a nested backdrop root (the Segmented thumb in a glass bar)
           or a fading page, transparent stays transparent instead of black -->
      <feComposite in="s1" in2="SourceGraphic" operator="in" result="soft" />
      {#if l.dispersion}
        {#each CHANNELS as [c, f, m] (c)}
          <feDisplacementMap
            id="{l.id}-d{c}"
            data-f={f}
            in="soft"
            in2="map"
            scale={l.scale * f}
            xChannelSelector="R"
            yChannelSelector="G"
            result="d{c}"
          />
          <feColorMatrix in="d{c}" type="matrix" values={m} result="c{c}" />
        {/each}
        <feComposite in="cr" in2="cg" operator="arithmetic" k2="1" k3="1" result="rg" />
        <feComposite in="rg" in2="cb" operator="arithmetic" k2="1" k3="1" result="lens" />
      {:else}
        <feDisplacementMap
          id="{l.id}-d"
          in="soft"
          in2="map"
          scale={l.scale}
          xChannelSelector="R"
          yChannelSelector="G"
          result="lens"
        />
      {/if}
      {#if l.mask === 'rim'}
        <!-- frosted interior, edge-renormalised (premultiplied blur, alpha forced
             to 1, then back to the backdrop's coverage) -->
        <feGaussianBlur in="SourceGraphic" stdDeviation={l.frost} result="f0" />
        <feComponentTransfer in="f0" result="f1"><feFuncA type="table" tableValues="1 1" /></feComponentTransfer>
        <feComposite in="f1" in2="SourceGraphic" operator="in" result="frost" />
        <feColorMatrix in="map" type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 1 0 0" result="rim" />
        <feComposite in="lens" in2="rim" operator="in" result="lensRim" />
        <feComposite in="lensRim" in2="frost" operator="over" />
      {/if}
    </filter>
  {/each}
</svg>

<style>
  /* never display:none, or the filters can stop resolving */
  .lg-defs {
    position: absolute;
    left: 0;
    top: 0;
    width: 0;
    height: 0;
    overflow: hidden;
    pointer-events: none;
  }
</style>
