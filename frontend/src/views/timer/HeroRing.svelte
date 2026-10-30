<script lang="ts">
  import type { Snippet } from 'svelte';
  import { Spring } from 'svelte/motion';
  import { reduced } from '../../lib/motion';
  import { RING, hourTicks, ringPoint } from './timerLogic';

  /** Glowing progress ring toward the daily target. `progress` may exceed 1:
   *  the overtime lap is drawn on top in warm colours. */
  let {
    progress,
    running,
    hue,
    targetHours,
    overHue = null,
    rewind = false,
    children,
  }: {
    progress: number;
    running: boolean;
    hue: number;
    targetHours: number;
    /** Tint the overtime lap with this hue instead of the warm amber → pink (Lulz blue overtime). */
    overHue?: number | null;
    /** Start dial: the fill ends at 12 o'clock ("now") and reaches back
     *  anticlockwise to the picked start. Turning it off swings the arc
     *  forward into the running layout (start at 12, growing clockwise). */
    rewind?: boolean;
    children?: Snippet;
  } = $props();

  const uid = Math.random().toString(36).slice(2, 8);
  const { size, r, stroke } = RING;
  const c = size / 2;
  const shown = new Spring(0, { stiffness: 0.07, damping: 0.55 });
  const wind = new Spring(0, { stiffness: 0.08, damping: 0.6 });

  $effect(() => {
    const p = Math.max(0, progress);
    void shown.set(p, { instant: reduced() || Math.abs(p - shown.target) < 0.02 });
  });
  $effect(() => {
    // on at once (the dial was just grabbed); off swings the arc forward
    void wind.set(rewind ? 1 : 0, { instant: reduced() || rewind });
  });

  const lap1 = $derived(Math.min(1, Math.max(0, shown.current)));
  const lap2 = $derived(Math.min(1, Math.max(0, shown.current - 1)));
  const head = $derived(ringPoint(shown.current >= 1 ? 1 + lap2 : lap1));
  const ticks = $derived(hourTicks(targetHours));
  const hue2 = $derived(hue + 46);
  const spin = $derived(-wind.current * shown.current * 360);
</script>

<div class="ring" class:running style:--h={hue} style:--h2={hue2}>
  <div class="halo fx-anim" aria-hidden="true"></div>
  <svg viewBox="0 0 {size} {size}" aria-hidden="true">
    <defs>
      <linearGradient id="arc-{uid}" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stop-color="hsl({hue2} 95% 68%)" />
        <stop offset="1" stop-color="hsl({hue} 90% 60%)" />
      </linearGradient>
      <linearGradient id="over-{uid}" x1="0" y1="1" x2="1" y2="0">
        <stop offset="0" stop-color={overHue == null ? '#fbbf24' : `hsl(${overHue} 95% 82%)`} />
        <stop offset="1" stop-color={overHue == null ? '#f472b6' : `hsl(${overHue + 30} 90% 62%)`} />
      </linearGradient>
    </defs>

    <circle class="track" cx={c} cy={c} {r} stroke-width={stroke} />
    <circle class="track-inner" cx={c} cy={c} r={r - stroke / 2 - 9} />
    {#each ticks as a, i (i)}
      <line
        class="tick"
        class:major={i === 0}
        class:passed={a / 360 <= lap1 && running}
        x1={c}
        y1={c - r + stroke / 2 + 4}
        x2={c}
        y2={c - r + stroke / 2 + (i === 0 ? 11 : 8)}
        transform="rotate({a} {c} {c})"
      />
    {/each}

    <g transform="rotate({spin} {c} {c})">
      {#if lap1 > 0.001}
        <circle
          class="arc glow"
          cx={c}
          cy={c}
          {r}
          stroke="url(#arc-{uid})"
          stroke-width={stroke}
          pathLength="100"
          stroke-dasharray="{lap1 * 100} 100"
          transform="rotate(-90 {c} {c})"
        />
        <circle
          class="arc"
          cx={c}
          cy={c}
          {r}
          stroke="url(#arc-{uid})"
          stroke-width={stroke}
          pathLength="100"
          stroke-dasharray="{lap1 * 100} 100"
          transform="rotate(-90 {c} {c})"
        />
      {/if}
      {#if lap2 > 0.001}
        <circle
          class="arc over"
          class:tinted={overHue != null}
          style:--oh={overHue}
          cx={c}
          cy={c}
          {r}
          stroke="url(#over-{uid})"
          stroke-width={stroke - 4}
          pathLength="100"
          stroke-dasharray="{lap2 * 100} 100"
          transform="rotate(-90 {c} {c})"
        />
      {/if}
      {#if running && shown.current > 0.004}
        <circle class="head" cx={head.x} cy={head.y} r={stroke / 2 - 2.5} />
      {/if}
    </g>
  </svg>
  <div class="center">
    {@render children?.()}
  </div>
</div>

<style>
  .ring {
    position: relative;
    width: 100%;
    aspect-ratio: 1;
    display: grid;
    place-items: center;
  }
  svg {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    overflow: visible;
  }
  .halo {
    position: absolute;
    inset: 9%;
    border-radius: 50%;
    background: conic-gradient(
      from 0deg,
      hsl(var(--h) 90% 62% / 0.75),
      hsl(var(--h2) 95% 65% / 0.15),
      hsl(var(--h) 90% 62% / 0.6),
      hsl(var(--h2) 95% 65% / 0.1),
      hsl(var(--h) 90% 62% / 0.75)
    );
    filter: blur(34px);
    opacity: 0.18;
    transform: scale(0.92);
    transition:
      opacity var(--dur-slow) var(--ease-out),
      transform var(--dur-slow) var(--ease-out);
  }
  .running .halo {
    opacity: 0.55;
    transform: scale(1.04);
    animation: spin 14s linear infinite;
  }
  @keyframes spin {
    to {
      rotate: 360deg;
    }
  }
  .track {
    fill: none;
    stroke: var(--neutral-fill);
  }
  .track-inner {
    fill: color-mix(in srgb, var(--glass-solid) 55%, transparent);
    stroke: var(--divider);
    stroke-width: 1;
  }
  .tick {
    stroke: var(--text-subtle);
    stroke-width: 1.6;
    stroke-linecap: round;
    opacity: 0.45;
    transition:
      opacity var(--dur-med) var(--ease-out),
      stroke var(--dur-med) var(--ease-out);
  }
  .tick.major {
    stroke-width: 2.2;
    opacity: 0.7;
  }
  .tick.passed {
    stroke: hsl(var(--h2) 95% 75%);
    opacity: 0.95;
  }
  .arc {
    fill: none;
    stroke-linecap: round;
  }
  .arc.glow {
    filter: blur(7px);
    opacity: 0.7;
  }
  .arc.over {
    filter: drop-shadow(0 0 6px rgba(251, 191, 36, 0.7));
  }
  .arc.over.tinted {
    filter: drop-shadow(0 0 6px hsl(var(--oh) 95% 65% / 0.75));
  }
  .head {
    fill: #fff;
    filter: drop-shadow(0 0 5px hsl(var(--h2) 100% 75%)) drop-shadow(0 0 12px hsl(var(--h) 100% 60%));
  }
  .center {
    position: relative;
    z-index: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
    max-width: 74%;
  }
</style>
